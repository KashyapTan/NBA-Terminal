"""Public NBA batch enrichment; no ESPN credentials or per-player HTTP calls."""

from __future__ import annotations

import copy
import json
import math
import threading
import time
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from typing import Callable
from zoneinfo import ZoneInfo

import requests
from nba_api.stats.endpoints import commonallplayers, leaguedashplayerstats, scheduleleaguev2
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
_FLIGHTS: dict[tuple, threading.Event] = {}


def season_name(ending_year: int) -> str:
    return f"{ending_year - 1}-{str(ending_year)[-2:]}"


def finite(value):
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        else None
    )


def usable_rates(values):
    """Require a coherent sampled basis before replacing another provider's rates."""
    return not rate_errors(values)


def rate_errors(values):
    if not isinstance(values, dict):
        return ["sample_missing"]
    errors = [
        f"{key}:missing_or_invalid"
        for key in sorted(set(FIELDS.values()) - {"fg_pct", "ft_pct"})
        if finite(values.get(key)) is None or values[key] < 0
    ]
    if not errors:
        errors.extend(
            f"{prefix}:makes_exceed_attempts" for prefix in ("fg", "ft") if values[prefix + "m"] > values[prefix + "a"]
        )
    return errors


def cached(key: tuple, fetch: Callable, ttl: int = 900) -> tuple[object | None, str]:
    """Single-flight, bounded cache; failures back off, usable stale data lasts six hours."""
    while True:
        with _LOCK:
            clock = time.monotonic()
            old = _CACHE.get(key)
            if old and old[0] > clock:
                status = "unavailable" if old[1] is None else "stale" if old[3] else "cached"
                return copy.deepcopy(old[1]), status
            flight = _FLIGHTS.get(key)
            if flight is None:
                flight = _FLIGHTS[key] = threading.Event()
                break
        flight.wait()  # Only identical resource keys wait; callers run in bounded workers.
    try:
        try:
            value = fetch()
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError, StopIteration):
            value = None
        if value is None:
            stale = old[1] if old and clock - old[2] < 21600 else None
            entry = (clock + 60, stale, old[2] if old else clock, True)
            status = "stale" if stale is not None else "unavailable"
        else:
            entry = (clock + ttl, value, clock, False)
            status = "fresh"
        with _LOCK:
            if len(_CACHE) >= 64 and key not in _CACHE:
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[key] = entry
        return copy.deepcopy(entry[1]), status
    finally:
        with _LOCK:
            _FLIGHTS.pop(key).set()


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
    required = {field for field, key in FIELDS.items() if key not in {"fg_pct", "ft_pct"}}
    if not {"PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", *required}.issubset(headers):
        raise ValueError("NBA stats schema changed")
    rows = [dict(zip(headers, row, strict=True)) for row in table["rowSet"]]
    for row in rows:
        games = finite(row.get("GP"))
        rates = {key: finite(row.get(field)) for field, key in FIELDS.items()}
        if games is None or games < 0 or not games.is_integer() or not usable_rates(rates):
            raise ValueError("NBA game count or primitive rate sample invalid")
        if games == 0 and any(value != 0 for key, value in rates.items() if key not in {"fg_pct", "ft_pct"}):
            raise ValueError("NBA zero-game sample has nonzero production")
    return rows


def fetch_identities(year: int) -> list[dict]:
    data = commonallplayers.CommonAllPlayers(season=season_name(year), is_only_current_season=1, timeout=6).get_dict()
    table = next(t for t in data.get("resultSets", []) if t.get("name") == "CommonAllPlayers")
    if not {"PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID", "ROSTERSTATUS"}.issubset(table["headers"]):
        raise ValueError("NBA identity schema changed")
    return [dict(zip(table["headers"], row, strict=True)) for row in table["rowSet"]]


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
    rates, rate_status = cached(
        ("rates", year), lambda: {"rows": fetch_rates(year), "fetched_at": datetime.now(timezone.utc).isoformat()}
    )
    identities, identity_status = cached(("identities", year), lambda: fetch_identities(year), 3600)
    schedule, schedule_status = (
        cached(
            ("schedule", year),
            lambda: {"data": fetch_schedule(year), "fetched_at": datetime.now(timezone.utc).isoformat()},
            3600,
        )
        if need_schedule
        else (None, "not_needed")
    )
    return {
        "rates": rates["rows"] if rates else [],
        "identities": identities or [],
        "identities_status": identity_status,
        "rates_fetched_at": rates["fetched_at"] if rates else None,
        "schedule": schedule["data"] if schedule else None,
        "schedule_fetched_at": schedule["fetched_at"] if schedule else None,
        "rates_status": rate_status,
        "schedule_status": schedule_status,
        "season": season_name(year),
    }


def load_prior_rates(year: int) -> dict:
    sample, status = cached(
        ("rates", year - 1),
        lambda: {"rows": fetch_rates(year - 1), "fetched_at": datetime.now(timezone.utc).isoformat()},
    )
    return {
        "prior_rates": sample["rows"] if sample else [],
        "prior_rates_status": status,
        "prior_rates_fetched_at": sample["fetched_at"] if sample else None,
    }


def schedule_games(data: dict | None, year: int, now: datetime) -> dict[int, list[dict]]:
    league = (data or {}).get("leagueSchedule", {})
    if league.get("seasonYear") != season_name(year):
        return {}
    parsed, unknown_teams = [], set()
    for day in league.get("gameDates", []):
        for game in day.get("games", []):
            # Regular-season NBA/Cup games only; cup final, exhibitions and playoffs excluded.
            if not str(game.get("gameId", "")).startswith("002"):
                continue
            # ScheduleLeagueV2 uses A for active, including completed games; it is
            # not a postponed flag. Inactive/original postponed rows must not add starts.
            postponed = game.get("postponedStatus")
            status = str(postponed).strip().upper() if postponed is not None else ""
            text = str(game.get("gameStatusText", "")).upper()
            if status not in ("", "FALSE", "0", "N", "A") or "PPD" in text or "POSTPONED" in text:
                continue
            try:
                start = datetime.fromisoformat(game["gameDateTimeUTC"].replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                home, away = (NBA_TO_ESPN[game[key]["teamId"]] for key in ("homeTeam", "awayTeam"))
            except (ValueError, KeyError, TypeError):
                affected = [NBA_TO_ESPN.get(game.get(key, {}).get("teamId")) for key in ("homeTeam", "awayTeam")]
                if None in affected:
                    return {}  # Unknown affected team: cannot certify any team's empty schedule.
                unknown_teams.update(affected)
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
                    "final": game.get("gameStatus") == 3,
                    "opponent_pro_team_id": opponent,
                    "source": "nba_schedule",
                }
            )
    return {
        team: sorted(games, key=lambda g: g["start_at"]) for team, games in result.items() if team not in unknown_teams
    }


def name_key(name: str | None) -> str:
    # Keep suffix letters: Gary Payton and Gary Payton II must never collapse.
    return "".join(c for c in unicodedata.normalize("NFKD", name or "").casefold() if c.isalnum())


@lru_cache(maxsize=4)
def _static_names(get_players):
    names = {}
    for player in get_players():
        names.setdefault(name_key(player["full_name"]), []).append(player)
    return names


def match_player(player: dict, rows: list[dict], identities: list[dict] | None = None) -> tuple[dict | None, dict]:
    key = name_key(player.get("name"))
    found = [row for row in rows if key and name_key(row.get("PLAYER_NAME")) == key]
    team = ESPN_TEAMS.get(player.get("pro_team_id"))
    # A season aggregate can span a trade; do not reject it just because its team
    # differs from today's ESPN team. Names/suffixes must still identify one NBA ID.
    ids = {r.get("PLAYER_ID") for r in found}
    if len(ids) == 1 and len(found) > 1:
        aggregate = [r for r in found if r.get("TEAM_ID") == 0 or r.get("TEAM_ABBREVIATION") in {"TOT", "TOTAL"}]
        if len(aggregate) == 1:
            return aggregate[0], {
                "nba_player_id": aggregate[0]["PLAYER_ID"],
                "status": "matched",
                "source": "nba_stats_season_aggregate",
            }
        team_keys = {r.get("TEAM_ID", r.get("TEAM_ABBREVIATION")) for r in found}
        if len(team_keys) == len(found) and all(
            finite(r.get("GP")) is not None
            and r["GP"] > 0
            and usable_rates({key: finite(r.get(field)) for field, key in FIELDS.items()})
            for r in found
        ):
            games = sum(r["GP"] for r in found)
            combined = found[0] | {
                field: sum(r[field] * r["GP"] for r in found) / games
                for field, key in FIELDS.items()
                if key not in {"fg_pct", "ft_pct"}
            }
            combined.update(GP=games, TEAM_ID=0, TEAM_ABBREVIATION="TOT")
            return combined, {
                "nba_player_id": combined["PLAYER_ID"],
                "status": "matched",
                "source": "nba_stats_team_splits_weighted_by_games",
            }
    same_team = [r for r in found if r.get("TEAM_ABBREVIATION") == team] if team and team != "FA" else found
    if len(ids) == 1 and len(same_team) == 1:
        found = same_team
    if len(ids) == 1 and len(found) == 1:
        if team and team != "FA" and not same_team:
            catalog_ids = {p["PERSON_ID"] for p in identities or [] if name_key(p.get("DISPLAY_FIRST_LAST")) == key}
            catalog_ids.update(p["id"] for p in _static_names(players.get_players).get(key, []))
            if catalog_ids != ids:
                return None, {"nba_player_id": None, "status": "unresolved", "source": "team_mismatch_unverified"}
        source = "nba_stats_name_team" if found[0] in same_team else "nba_stats_unique_name_season_team_changed"
        return found[0], {"nba_player_id": found[0]["PLAYER_ID"], "status": "matched", "source": source}
    if len(found) > 1:
        return None, {"nba_player_id": None, "status": "ambiguous", "source": None}
    current = [p for p in identities or [] if key and name_key(p.get("DISPLAY_FIRST_LAST")) == key]
    if len(current) == 1:
        return None, {
            "nba_player_id": current[0]["PERSON_ID"],
            "status": "matched",
            "source": "nba_current_season_inventory",
            "current_season_roster": current[0].get("ROSTERSTATUS") == 1,
        }
    # Static official-client identities help when the current identity endpoint is unavailable.
    static = _static_names(players.get_players).get(key, []) if key else []
    return None, {
        "nba_player_id": static[0]["id"] if len(static) == 1 else None,
        "status": "matched" if len(static) == 1 else "ambiguous" if static else "unresolved",
        "source": "nba_static_unique_name" if len(static) == 1 else None,
    }


def enrich_players(snapshot: dict, bundle: dict) -> None:
    all_players = [p for team in snapshot["teams"] for p in team["roster"]] + snapshot["free_agents"]
    ending_year = snapshot.get("league", {}).get("season_id")
    season = bundle.get("season") or (season_name(ending_year) if ending_year else None)

    def by_name(rows, field):
        grouped = {}
        for row in rows:
            grouped.setdefault(name_key(row.get(field)), []).append(row)
        return grouped

    current_rows = by_name(bundle.get("rates", []), "PLAYER_NAME")
    prior_rows = by_name(bundle.get("prior_rates", []), "PLAYER_NAME")
    identity_rows = by_name(bundle.get("identities", []), "DISPLAY_FIRST_LAST")
    for player in all_players:
        key = name_key(player.get("name"))
        row, identity = match_player(player, current_rows.get(key, []), identity_rows.get(key, []))
        player["identity"] = identity
        current = player.get("current_rates")
        player.setdefault("espn_current_rates", copy.deepcopy(current))
        games = finite(row.get("GP")) if row else None
        if row is not None and games is not None and games > 0:
            rates = {key: finite(row.get(field)) for field, key in FIELDS.items()}
            # Shooting pairs always come from the same sample; do not mix vendor denominators.
            for prefix in ("fg", "ft"):
                made, attempts = rates[prefix + "m"], rates[prefix + "a"]
                rates[prefix + "_pct"] = made / attempts if made is not None and attempts else None
            player["nba_rates"] = copy.deepcopy(rates)
            player["nba_rates_usable"] = usable_rates(rates)
            player["nba_rates_rejection_codes"] = rate_errors(rates)
            if player["nba_rates_usable"] and (bundle.get("rates_status") != "stale" or not usable_rates(current)):
                player["current_rates"] = rates
                player["current_rates_source"] = "nba_stats"
                player["current_games"] = games
                player["current_games_source"] = "nba_stats"
        source = player.get("current_rates_source")
        chosen = player.get("current_rates")
        if not usable_rates(chosen) or not (player.get("current_games") or 0) > 0:
            chosen = player.get("prior_rates")
            source = player.get("prior_rates_source", "espn_prior_season") if chosen is not None else None
        if not usable_rates(chosen):
            chosen, source = None, None
        prior_row, _ = match_player(player, prior_rows.get(key, []), identity_rows.get(key, []))
        if chosen is None and prior_row and finite(prior_row.get("GP")) and prior_row["GP"] > 0:
            fallback = {key: finite(prior_row.get(field)) for field, key in FIELDS.items()}
            if usable_rates(fallback):
                for prefix in ("fg", "ft"):
                    attempts = fallback[prefix + "a"]
                    fallback[prefix + "_pct"] = fallback[prefix + "m"] / attempts if attempts else None
                chosen, source = fallback, "nba_prior_season"
                player["prior_games"] = prior_row["GP"]
                player["prior_rates"] = copy.deepcopy(fallback)
                player["prior_rates_source"] = source
        prior_basis = source in {"espn_prior_season", "nba_prior_season"}
        player["rate_provenance"] = {
            "source": source,
            "season": season if not prior_basis else season_name(ending_year - 1) if ending_year else None,
            "games": player.get("prior_games") if prior_basis else player.get("current_games"),
            "small_sample": bool(not prior_basis and 0 < (player.get("current_games") or 0) < 3),
            "fallback": source != "nba_stats",
            "reason": (
                "Current-season rates unavailable; complete prior NBA season sample selected"
                if source == "nba_prior_season"
                else "NBA sample has missing or invalid primitive rates; usable ESPN sample retained"
                if player.get("nba_rates_usable") is False and source
                else "NBA batch unavailable, stale, or identity/sample missing"
                if source != "nba_stats"
                else None
            ),
            "status": bundle.get("prior_rates_status")
            if source == "nba_prior_season"
            else bundle.get("rates_status")
            if source == "nba_stats"
            else "fallback"
            if source
            else "missing",
            "fetched_at": bundle.get("prior_rates_fetched_at")
            if source == "nba_prior_season"
            else bundle.get("rates_fetched_at")
            if source == "nba_stats"
            else snapshot.get("fetched_at"),
        }
        player["season_rates"] = copy.deepcopy(chosen)
    snapshot["enrichment"] = {
        k: v for k, v in bundle.items() if k not in ("rates", "schedule", "identities", "prior_rates")
    }
    required_teams = {snapshot.get("selected_team_id"), snapshot.get("opponent_team_id")}
    for team in snapshot["teams"]:
        if team.get("id") is None or team.get("id") not in required_teams:
            continue
        stale = any(
            p.get("rate_provenance", {}).get("status") == "stale"
            for p in team["roster"]
            if p.get("active") is not False
        )
        stale_schedule = bundle.get("schedule_status") == "stale" and any(
            p.get("schedule_source") == "nba_schedule" for p in team["roster"] if p.get("active") is not False
        )
        snapshot.setdefault("projection_metadata", {})[f"schedule_freshness_team_{team['id']}"] = {
            "complete": not stale_schedule,
            "source": "per_player_schedule_source",
            "reason": "Stale NBA schedule selected" if stale_schedule else "No stale schedules selected",
        }
        snapshot.setdefault("projection_metadata", {})[f"rate_freshness_team_{team['id']}"] = {
            "complete": not stale,
            "source": "per_player_rate_provenance",
            "reason": "Stale NBA rates lack a usable ESPN current sample" if stale else "No stale rates selected",
        }
    selected_players = [p for team in snapshot["teams"] if team.get("id") in required_teams for p in team["roster"]]
    notes = snapshot.setdefault("modeling_notes", [])
    for collection in (snapshot["data_gaps"], notes):
        collection[:] = [g for g in collection if not g.startswith(("NBA current-season batch stats", "NBA schedule"))]
    if bundle.get("rates_status") in ("unavailable", "stale"):
        target = notes if all(usable_rates(p.get("season_rates")) for p in selected_players) else snapshot["data_gaps"]
        target.append(
            f"NBA current-season batch stats {bundle['rates_status']}; usable selected source samples retained."
        )
    if bundle.get("schedule_status") in ("unavailable", "stale"):
        target = (
            notes
            if all(
                p.get("schedule") is not None or p.get("active") is False or p.get("health_status") == "out"
                for p in selected_players
            )
            else snapshot["data_gaps"]
        )
        target.append(f"NBA schedule {bundle['schedule_status']}; usable ESPN schedule retained when available.")
    # Recompute after fallback: do not retain a gap that has actually been filled.
    if all(p["current_rates"] is not None and p["prior_rates"] is not None for p in all_players):
        snapshot["data_gaps"] = [
            g for g in snapshot["data_gaps"] if g != "Some current/prior season average samples are unavailable."
        ]

    if all(
        (p["current_rates"] or {}).get(key) is not None for p in all_players for key in ("fgm", "fga", "ftm", "fta")
    ):
        snapshot["data_gaps"] = [g for g in snapshot["data_gaps"] if not g.startswith("Some shooting attempts/makes")]
