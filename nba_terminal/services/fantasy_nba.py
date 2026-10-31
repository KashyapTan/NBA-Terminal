"""Public NBA batch enrichment; no ESPN credentials or per-player HTTP calls."""

from __future__ import annotations

import copy
import json
import math
import threading
import time
import unicodedata
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import requests
from nba_api.stats.endpoints import leaguedashplayerstats, scheduleleaguev2
from nba_api.stats.static import players, teams

NY = ZoneInfo("America/New_York")
SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
# ESPN IDs are not NBA IDs. ESPN aliases PHL/PHO normalize to NBA PHI/PHX.
ESPN_TEAMS = dict(
    enumerate(
        [
            "FA",
            "ATL",
            "BOS",
            "NOP",
            "CHI",
            "CLE",
            "DAL",
            "DEN",
            "DET",
            "GSW",
            "HOU",
            "IND",
            "LAC",
            "LAL",
            "MIA",
            "MIL",
            "MIN",
            "BKN",
            "NYK",
            "ORL",
            "PHI",
            "PHX",
            "POR",
            "SAC",
            "SAS",
            "OKC",
            "UTA",
            "WAS",
            "TOR",
            "MEM",
            "CHA",
        ]
    )
)
NBA_TO_ESPN = {
    team["id"]: next(k for k, v in ESPN_TEAMS.items() if v == team["abbreviation"]) for team in teams.get_teams()
}
FIELDS = {
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
    "STL": "stl",
    "BLK": "blk",
    "FG3M": "threes",
    "TOV": "to",
    "FGM": "fgm",
    "FGA": "fga",
    "FTM": "ftm",
    "FTA": "fta",
    "MIN": "minutes",
    "FG_PCT": "fg_pct",
    "FT_PCT": "ft_pct",
}
_CACHE: dict[tuple, tuple[float, object, float, bool]] = {}
_LOCK = threading.Lock()


def season_name(ending_year: int) -> str:
    return f"{ending_year - 1}-{str(ending_year)[-2:]}"


def finite(value):
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        else None
    )


def cached(key: tuple, fetch: Callable, ttl: int = 900) -> tuple[object | None, str]:
    """Single-flight, bounded cache; failures back off, usable stale data lasts six hours."""
    with _LOCK:
        clock = time.monotonic()
        old = _CACHE.get(key)
        if old and old[0] > clock:
            return copy.deepcopy(old[1]), "unavailable" if old[1] is None else "stale" if old[3] else "cached"
        if len(_CACHE) >= 12 and key not in _CACHE:
            _CACHE.pop(next(iter(_CACHE)))
        try:
            value = fetch()
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError, StopIteration):
            value = None
        if value is None:
            stale = old[1] if old and clock - old[2] < 21600 else None
            _CACHE[key] = (clock + 60, stale, old[2] if old else clock, True)
            return copy.deepcopy(stale), "stale" if stale is not None else "unavailable"
        _CACHE[key] = (clock + ttl, value, clock, False)
        return copy.deepcopy(value), "fresh"


def fetch_rates(year: int) -> list[dict]:
    data = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season_name(year),
        per_mode_detailed="PerGame",
        season_type_all_star="Regular Season",
        timeout=6,
    ).get_dict()
    table = next(t for t in data.get("resultSets", []) if t.get("name") == "LeagueDashPlayerStats")
    if not table.get("rowSet"):
        raise ValueError("NBA current-season sample unavailable")
    headers = table["headers"]
    if not {"PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "MIN", "PTS"}.issubset(headers):
        raise ValueError("NBA stats schema changed")
    return [dict(zip(headers, row, strict=True)) for row in table["rowSet"]]


def fetch_schedule(year: int) -> dict:
    try:
        with requests.get(SCHEDULE_URL, timeout=(3.05, 6), allow_redirects=False, stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError("NBA schedule too large")
                chunks.append(chunk)
            data = json.loads(b"".join(chunks))
            if data.get("leagueSchedule", {}).get("seasonYear") != season_name(year) or not data.get(
                "leagueSchedule", {}
            ).get("gameDates"):
                raise ValueError("NBA schedule season mismatch")
            return data
    except (requests.RequestException, ValueError, KeyError):
        # Stats endpoint accepts an explicit season; the CDN only serves its current season.
        data = scheduleleaguev2.ScheduleLeagueV2(season=season_name(year), timeout=6).get_dict()
        if data.get("leagueSchedule", {}).get("seasonYear") != season_name(year) or not data.get(
            "leagueSchedule", {}
        ).get("gameDates"):
            raise ValueError("NBA schedule season mismatch")
        return data


def load(year: int, *, need_schedule: bool = True) -> dict:
    rates, rate_status = cached(("rates", year), lambda: fetch_rates(year))
    schedule, schedule_status = (
        cached(("schedule", year), lambda: fetch_schedule(year), 3600) if need_schedule else (None, "not_needed")
    )
    return {
        "rates": rates or [],
        "schedule": schedule,
        "rates_status": rate_status,
        "schedule_status": schedule_status,
        "season": season_name(year),
    }


def schedule_games(data: dict | None, year: int, now: datetime) -> dict[int, list[dict]]:
    league = (data or {}).get("leagueSchedule", {})
    if league.get("seasonYear") != season_name(year):
        return {}
    parsed = []
    for day in league.get("gameDates", []):
        for game in day.get("games", []):
            # Regular-season NBA/Cup games only; cup final, exhibitions and playoffs excluded.
            if not str(game.get("gameId", "")).startswith("002"):
                continue
            postponed = game.get("postponedStatus")
            if postponed not in (None, False, 0, "", "N", "0") or "PPD" in str(game.get("gameStatusText", "")).upper():
                continue
            try:
                start = datetime.fromisoformat(game["gameDateTimeUTC"].replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                home, away = (NBA_TO_ESPN[game[key]["teamId"]] for key in ("homeTeam", "awayTeam"))
            except (ValueError, KeyError, TypeError):
                continue
            parsed.append((game, start, home, away))
    if not parsed:
        return {}
    first = min(start.astimezone(NY).date() for _, start, _, _ in parsed)
    result = {key: [] for key in ESPN_TEAMS if key}
    for game, start, home, away in parsed:
        date = start.astimezone(NY).date()
        for team, opponent in ((home, away), (away, home)):
            result[team].append(
                {
                    "game_id": game["gameId"],
                    "scoring_period_id": (date - first).days + 1,
                    "date": date.isoformat(),
                    "start_at": start.isoformat(),
                    "started": start <= now or game.get("gameStatus") in (2, 3),
                    "opponent_pro_team_id": opponent,
                    "source": "nba_schedule",
                }
            )
    return {team: sorted(games, key=lambda g: g["start_at"]) for team, games in result.items()}


def name_key(name: str | None) -> str:
    # Keep suffix letters: Gary Payton and Gary Payton II must never collapse.
    return "".join(c for c in unicodedata.normalize("NFKD", name or "").casefold() if c.isalnum())


def match_player(player: dict, rows: list[dict]) -> tuple[dict | None, dict]:
    key = name_key(player.get("name"))
    found = [row for row in rows if key and name_key(row.get("PLAYER_NAME")) == key]
    team = ESPN_TEAMS.get(player.get("pro_team_id"))
    if team and team != "FA":
        found = [r for r in found if r.get("TEAM_ABBREVIATION") == team]
    ids = {r.get("PLAYER_ID") for r in found}
    if len(ids) == 1 and len(found) == 1:
        return found[0], {"nba_player_id": found[0]["PLAYER_ID"], "status": "matched", "source": "nba_stats_name_team"}
    if len(found) > 1:
        return None, {"nba_player_id": None, "status": "ambiguous", "source": None}
    # Static official-client identities help rookies before their first regular-season game.
    static = [p for p in players.get_players() if key and name_key(p["full_name"]) == key]
    return None, {
        "nba_player_id": static[0]["id"] if len(static) == 1 else None,
        "status": "matched" if len(static) == 1 else "ambiguous" if static else "unresolved",
        "source": "nba_static_unique_name" if len(static) == 1 else None,
    }


def enrich_players(snapshot: dict, bundle: dict) -> None:
    all_players = [p for team in snapshot["teams"] for p in team["roster"]] + snapshot["free_agents"]
    for player in all_players:
        row, identity = match_player(player, bundle.get("rates", []))
        player["identity"] = identity
        if row is None or (finite(row.get("GP")) or 0) <= 0:
            continue
        rates = {key: finite(row.get(field)) for field, key in FIELDS.items()}
        current = player["current_rates"] or {}
        filled = [key for key, value in rates.items() if current.get(key) is None and value is not None]
        if filled:
            player["current_rates"] = rates | {k: v for k, v in current.items() if v is not None}
            player["current_rates_source"] = "nba_stats" if not current else "espn_with_nba_stats"
            player["nba_filled_rate_fields"] = filled
        if player["current_games"] is None:
            player["current_games"] = finite(row.get("GP"))
            player["current_games_source"] = "nba_stats"
    snapshot["enrichment"] = {k: v for k, v in bundle.items() if k not in ("rates", "schedule")}
    if bundle.get("rates_status") in ("unavailable", "stale"):
        snapshot["data_gaps"].append(f"NBA current-season batch stats {bundle['rates_status']}; ESPN samples retained.")
    if bundle.get("schedule_status") in ("unavailable", "stale"):
        snapshot["data_gaps"].append(f"NBA schedule {bundle['schedule_status']}; usable ESPN schedule retained.")
    # Recompute after fallback: do not retain a gap that has actually been filled.
    if all(p["current_rates"] is not None and p["prior_rates"] is not None for p in all_players):
        snapshot["data_gaps"] = [
            g for g in snapshot["data_gaps"] if g != "Some current/prior season average samples are unavailable."
        ]

    if all(
        (p["current_rates"] or {}).get(key) is not None for p in all_players for key in ("fgm", "fga", "ftm", "fta")
    ):
        snapshot["data_gaps"] = [g for g in snapshot["data_gaps"] if not g.startswith("Some shooting attempts/makes")]
