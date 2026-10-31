"""Read-only, unofficial ESPN basketball transport and honest normalization.

No credentials, network work, or persistent state are created at import time.
The HTTP facade owns short-lived per-browser sessions; clients must run in workers.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba"
STAT_IDS = {
    "0": "pts",
    "1": "blk",
    "2": "stl",
    "3": "ast",
    "6": "reb",
    "11": "to",
    "13": "fgm",
    "14": "fga",
    "15": "ftm",
    "16": "fta",
    "17": "threes",
    "19": "fg_pct",
    "20": "ft_pct",
    "40": "minutes",
    "42": "games",
}
CATEGORIES = ("pts", "reb", "ast", "stl", "blk", "threes", "to", "fg_pct", "ft_pct")
SLOTS = {
    0: "PG",
    1: "SG",
    2: "SF",
    3: "PF",
    4: "C",
    5: "G",
    6: "F",
    7: "SG/SF",
    8: "G/F",
    9: "PF/C",
    10: "F/C",
    11: "UTIL",
    12: "BENCH",
    13: "IR",
    15: "Rookie",
}
NY = ZoneInfo("America/New_York")


class EspnError(Exception):
    """Only static safe messages; never wrap upstream bodies/headers/exceptions."""

    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) else None


def stats(raw: dict | None) -> dict[str, float | None] | None:
    if raw is None:
        return None
    result = {key: number(raw.get(stat_id)) for stat_id, key in STAT_IDS.items()}
    for prefix in ("fg", "ft"):
        made, attempts = result[f"{prefix}m"], result[f"{prefix}a"]
        if made is not None and attempts is not None:
            result[f"{prefix}_pct"] = made / attempts if attempts > 0 else None
    return result


def total_stats(side: dict) -> dict | None:
    values = side.get("cumulativeScore", {}).get("scoreByStat")
    if not isinstance(values, dict):
        return None
    return stats({key: value.get("score") for key, value in values.items() if isinstance(value, dict)})


def _owner(value: str) -> str:
    return value.strip("{}").casefold()


def team_choices(raw: dict, swid: str | None) -> list[dict]:
    return [
        {
            "id": team["id"],
            "name": team.get("name")
            or " ".join(filter(None, [team.get("location"), team.get("nickname")]))
            or f"Team {team['id']}",
            "selectable": swid is None or any(_owner(owner) == _owner(swid) for owner in team.get("owners", [])),
            "ownership_verified": swid is not None
            and any(_owner(owner) == _owner(swid) for owner in team.get("owners", [])),
        }
        for team in raw.get("teams", [])
    ]


def validate_team(raw: dict, team_id: int, swid: str | None) -> None:
    team = next((team for team in team_choices(raw, swid) if team["id"] == team_id), None)
    if team is None:
        raise EspnError("team_not_found", "Choose a team returned by this league.", 400)
    if not team["selectable"]:
        raise EspnError("team_not_owned", "The supplied ESPN session does not own this team.", 403)


class EspnClient:
    """Fixed-host HTTP GETs only, bounded payloads and explicit transport failures."""

    def __init__(self, league_id: int, season_id: int, swid: str | None = None, espn_s2: str | None = None):
        self.league_id, self.season_id = league_id, season_id
        self.swid, self.espn_s2 = swid, espn_s2

    def __repr__(self) -> str:
        return f"EspnClient(league_id={self.league_id}, season_id={self.season_id})"

    def clear(self) -> None:
        self.swid = self.espn_s2 = None

    def get(
        self, views: list[str], filters: dict | None = None, *, season: bool = False, scoring_period: int | None = None
    ) -> dict:
        url = f"{BASE}/seasons/{self.season_id}"
        if not season:
            url += f"/segments/0/leagues/{self.league_id}"
        params: dict[str, Any] = {"view": views}
        if scoring_period is not None:
            params["scoringPeriodId"] = scoring_period
        cookies = {"SWID": self.swid, "espn_s2": self.espn_s2} if self.swid else {}
        headers = {"x-fantasy-filter": json.dumps(filters)} if filters else {}
        try:
            # No redirects: credentials must never be forwarded to another host.
            with requests.get(
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                timeout=(3.05, 12),
                allow_redirects=False,
                stream=True,
            ) as response:
                status = response.status_code
                if status in (401, 403):
                    raise EspnError(
                        "access_denied", "ESPN denied access. Check league visibility or renew cookies.", 401
                    )
                if status == 404:
                    raise EspnError("league_not_found", "ESPN could not find this league and season.", 404)
                if status == 429:
                    raise EspnError("rate_limited", "ESPN rate limited this request. Try again later.", 429)
                if status != 200:
                    raise EspnError("upstream_error", "ESPN could not return league data.")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 8_000_000:
                        raise EspnError("response_too_large", "ESPN response exceeded the safe size limit.")
                    chunks.append(chunk)
                data = json.loads(b"".join(chunks))
        except requests.Timeout:
            raise EspnError("timeout", "ESPN did not respond within the request timeout.", 504) from None
        except requests.RequestException:
            raise EspnError("network_error", "ESPN is unreachable. Try again later.") from None
        except (ValueError, UnicodeError):
            raise EspnError("invalid_response", "ESPN returned an invalid data response.") from None
        if not isinstance(data, dict):
            raise EspnError("schema_changed", "ESPN returned an unsupported response structure.")
        return data

    def league(self) -> dict:
        raw = self.get(["mSettings", "mTeam", "mRoster", "mMatchup", "mMatchupScore", "mScoreboard"])
        if (
            raw.get("id") != self.league_id
            or raw.get("seasonId") != self.season_id
            or not isinstance(raw.get("teams"), list)
            or not raw["teams"]
            or not isinstance(raw.get("settings"), dict)
        ):
            raise EspnError("schema_changed", "ESPN league identity or required fields were missing.")
        return raw

    def snapshot(self, raw: dict, selected: int, comparison: int | None = None) -> dict:
        gaps = []

        def optional(label: str, function: Any) -> dict:
            try:
                return function()
            except EspnError as exc:
                gaps.append(f"{label} unavailable ({exc.code}).")
                return {}

        period = raw.get("scoringPeriodId")
        schedule = optional("Professional schedule", lambda: self.get(["proTeamSchedules_wl"], season=True))
        pool = optional(
            "Free agents",
            lambda: self.get(
                ["kona_player_info"],
                {
                    "players": {
                        "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                        "limit": 100,
                        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                    },
                },
                scoring_period=period,
            ),
        )
        # One batched card request for selected rosters and bounded FA sample, not per-player calls.
        ids = {player_id(entry) for team in raw["teams"] for entry in team.get("roster", {}).get("entries", [])}
        ids.update(player_id(entry) for entry in pool.get("players", []))
        ids.discard(None)
        if len(ids) > 1000:
            raise EspnError("league_too_large", "This league exceeds the supported player batch size.")
        cards = (
            optional(
                "Player season samples",
                lambda: self.get(
                    ["kona_playercard"],
                    {
                        "players": {
                            "filterIds": {"value": sorted(ids)},
                            "filterStatsForTopScoringPeriodIds": {
                                "value": 0,
                                "additionalValue": [f"00{self.season_id}", f"00{self.season_id - 1}"],
                            },
                        }
                    },
                ),
            )
            if ids
            else {}
        )
        transactions = optional(
            "Transactions",
            lambda: self.get(
                ["mTransactions2"],
                {
                    "transactions": {"filterType": {"value": ["FREEAGENT", "WAIVER"]}},
                },
                scoring_period=period,
            ),
        )
        return normalize(raw, schedule, pool, cards, transactions, selected, comparison, self.swid, gaps=gaps)


def player_body(entry: dict) -> dict:
    return entry.get("playerPoolEntry", entry).get("player", {})


def player_id(entry: dict) -> int | None:
    return player_body(entry).get("id")


def samples(player: dict, year: int) -> tuple[dict | None, float | None]:
    split = next(
        (
            split
            for split in player.get("stats", [])
            if split.get("seasonId") == year
            and split.get("statSourceId") == 0
            and split.get("statSplitTypeId") == 0
            and split.get("scoringPeriodId") == 0
        ),
        None,
    )
    if split is None:
        return None, None
    totals = stats(split.get("stats"))
    games = totals.get("games") if totals else None
    averages = stats(split.get("averageStats"))
    if averages is None and totals and games and games > 0:
        averages = {key: value / games if value is not None else None for key, value in totals.items()}
        for key in ("fg_pct", "ft_pct"):
            averages[key] = totals[key]
    return averages, games


def normalize_schedule(raw: dict, now: datetime) -> dict[int, list[dict]]:
    result = {}
    for team in raw.get("settings", {}).get("proTeams", []):
        if "proGamesByScoringPeriod" not in team:
            continue
        games = []
        for period, entries in team["proGamesByScoringPeriod"].items():
            for game in entries:
                timestamp = number(game.get("date"))
                if timestamp is None:
                    continue
                start = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                games.append(
                    {
                        "scoring_period_id": int(period),
                        "date": start.astimezone(NY).date().isoformat(),
                        "start_at": start.isoformat(),
                        "started": start <= now,
                        "opponent_pro_team_id": game.get("awayProTeamId")
                        if game.get("homeProTeamId") == team["id"]
                        else game.get("homeProTeamId"),
                    }
                )
        result[team["id"]] = games
    return result


def normalize_player(
    entry: dict, cards: dict, schedules: dict, year: int, periods: list[int], now: datetime, *, rostered: bool = False
) -> dict:
    pool = entry.get("playerPoolEntry", entry)
    original = player_body(entry)
    player = original | cards.get(original.get("id"), {})
    current, games = samples(player, year)
    prior, prior_games = samples(player, year - 1)
    schedule = schedules.get(player.get("proTeamId")) if periods else None
    schedule = [game for game in schedule if game["scoring_period_id"] in periods] if schedule is not None else None
    availability = "ONTEAM" if rostered else pool.get("status", "UNKNOWN")
    positions = [SLOTS.get(slot, f"UNKNOWN_{slot}") for slot in player.get("eligibleSlots", [])]
    # ESPN's inspected read API does not establish drop-lock semantics. Never infer unlocked.
    return {
        "id": str(player.get("id", original.get("id"))),
        "name": player.get("fullName"),
        "pro_team_id": player.get("proTeamId"),
        "positions": positions,
        "lineup_slot": SLOTS.get(entry.get("lineupSlotId")),
        "injury_status": player.get("injuryStatus"),
        "injured": player.get("injured"),
        "locked": None,
        "availability": availability,
        "eligible": availability == "FREEAGENT"
        and any(position in set(SLOTS.values()) - {"BENCH", "IR", "Rookie"} for position in positions),
        "current_rates": current,
        "current_games": games,
        "prior_rates": prior,
        "prior_games": prior_games,
        "schedule": schedule,
        "today": any(game["date"] == now.astimezone(NY).date().isoformat() for game in schedule)
        if schedule is not None
        else None,
        "remaining_games": sum(not game["started"] for game in schedule) if schedule is not None else None,
    }


def compare_categories(user: dict | None, opponent: dict | None, categories: list[dict], team_id: int | None) -> dict:
    rows = []
    for category in categories:
        key = category["key"]
        a, b = (user or {}).get(key), (opponent or {}).get(key)
        state = "unknown"
        if a is not None and b is not None:
            margin = (a - b) * (-1 if category["lower_is_better"] else 1)
            state = "winning" if margin > 0 else "losing" if margin < 0 else "tied"
        rows.append({"key": key, "user": a, "opponent": b, "state": state})
    return {
        "team_id": team_id,
        "categories": rows,
        "wins": sum(row["state"] == "winning" for row in rows),
        "ties": sum(row["state"] == "tied" for row in rows),
        "losses": sum(row["state"] == "losing" for row in rows),
    }


def normalize(
    raw: dict,
    schedule: dict,
    pool: dict,
    cards: dict,
    transactions: dict,
    selected: int,
    comparison: int | None = None,
    swid: str | None = None,
    *,
    now: datetime | None = None,
    gaps: list[str] | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    gaps = list(gaps or [])
    validate_team(raw, selected, swid)
    if comparison is not None and comparison not in [team["id"] for team in raw["teams"]]:
        raise EspnError("team_not_found", "Comparison team is not in this league.", 400)
    settings = raw["settings"]
    scoring = settings.get("scoringSettings", {})
    categories = [
        {
            "key": STAT_IDS.get(str(item.get("statId")), f"unknown_{item.get('statId')}"),
            "stat_id": item.get("statId"),
            "lower_is_better": item.get("statId") == 11,
        }
        for item in scoring.get("scoringItems", [])
    ]
    supported = (
        scoring.get("scoringType") in {"H2H_CATEGORY", "H2H_MOST_CATEGORIES"}
        and len(categories) == 9
        and {item["key"] for item in categories} == set(CATEGORIES)
    )
    matchup = raw.get("status", {}).get("currentMatchupPeriod")
    periods = settings.get("scheduleSettings", {}).get("matchupPeriods", {}).get(str(matchup), [])
    periods = [int(period) for period in periods]
    schedules = normalize_schedule(schedule, now)
    dates = sorted(
        {game["date"] for games in schedules.values() for game in games if game["scoring_period_id"] in periods}
    )
    remaining = sorted(
        {
            game["date"]
            for games in schedules.values()
            for game in games
            if game["scoring_period_id"] in periods and not game["started"]
        }
    )
    card_map = {player_id(entry): player_body(entry) for entry in cards.get("players", [])}
    totals, opponent, history = {}, None, []
    for match in raw.get("schedule", []):
        home, away = match.get("home", {}), match.get("away", {})
        if match.get("matchupPeriodId") == matchup:
            for side in (home, away):
                if side.get("teamId") is not None:
                    totals[side["teamId"]] = total_stats(side)
            if home.get("teamId") == selected:
                opponent = away.get("teamId")
            elif away.get("teamId") == selected:
                opponent = home.get("teamId")
        elif (
            isinstance(match.get("matchupPeriodId"), int) and matchup is not None and match["matchupPeriodId"] < matchup
        ):
            history.append(
                {
                    "matchup_period_id": match["matchupPeriodId"],
                    "home_team_id": home.get("teamId"),
                    "away_team_id": away.get("teamId"),
                    "home_totals": total_stats(home),
                    "away_totals": total_stats(away),
                }
            )
    choices = {team["id"]: team for team in team_choices(raw, swid)}
    teams, roster_ids = [], set()
    for team in raw["teams"]:
        roster = [
            normalize_player(entry, card_map, schedules, raw["seasonId"], periods, now, rostered=True)
            for entry in team.get("roster", {}).get("entries", [])
            if player_id(entry) is not None
        ]
        roster_ids.update(player["id"] for player in roster)
        teams.append(
            {
                "id": team["id"],
                "name": choices[team["id"]]["name"],
                "ownership_verified": choices[team["id"]]["ownership_verified"],
                "roster": roster,
                "totals": totals.get(team["id"]),
                "season_acquisitions": team.get("transactionCounter", {}).get("acquisitions"),
                "weekly_used_adds": None,
                "remaining_adds": None,
            }
        )
    free_agents, seen = [], set(roster_ids)
    for entry in pool.get("players", []):
        if player_id(entry) is None or str(player_id(entry)) in seen:
            continue
        seen.add(str(player_id(entry)))
        player = normalize_player(entry, card_map, schedules, raw["seasonId"], periods, now)
        if player["availability"] in {"FREEAGENT", "WAIVERS"}:
            free_agents.append(player)
    acquisition = settings.get("acquisitionSettings", {})
    cap = acquisition.get("matchupAcquisitionLimit")
    per_day = acquisition.get("matchupLimitPerScoringPeriod")
    cap = cap if isinstance(cap, int) and not isinstance(cap, bool) and cap >= 0 and per_day is False else None
    lineup_counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {})
    lineup = [
        SLOTS.get(int(slot), f"UNKNOWN_{slot}")
        for slot, count in lineup_counts.items()
        if int(slot) not in (12, 13)
        for _ in range(min(max(int(count), 0), 50))
    ]
    gaps.extend(
        [
            "Weekly used/remaining adds are unverified; season acquisitions are not weekly usage. Confirm in ESPN.",
            "Droppable/transaction locks are unavailable; confirm each proposed drop and add in ESPN.",
            "Transaction rows cover only the current scoring day; complete weekly accounting is not established.",
            "Prior-season samples and injury status may be absent; future minutes are not supplied.",
        ]
    )
    if not periods or not dates:
        gaps.append("Matchup date coverage is unavailable; no dates were inferred from a nominal week.")
    all_players = [p for team in teams for p in team["roster"]] + free_agents
    if any(p["schedule"] is None for p in all_players):
        gaps.append("Some professional team schedules are unavailable; missing schedules are not zero games.")
    if any(p["current_rates"] is None or p["prior_rates"] is None for p in all_players):
        gaps.append("Some current/prior season average samples are unavailable.")
    if any((p["current_rates"] or {}).get(key) is None for p in all_players for key in ("fgm", "fga", "ftm", "fta")):
        gaps.append("Some shooting attempts/makes are unavailable; percentage gains cannot be weighted safely.")
    if not swid:
        gaps.append("Public league team selection does not verify ownership.")
    compare_id = comparison if comparison is not None else opponent
    return {
        "schema_version": 1,
        "source": "espn_unofficial",
        "fetched_at": now.isoformat(),
        "league": {
            "id": raw["id"],
            "season_id": raw["seasonId"],
            "name": settings.get("name"),
            "team_count": len(teams),
            "scoring_type": scoring.get("scoringType"),
            "categories": categories,
            "supported": supported,
            "unsupported_reason": None
            if supported
            else "Only head-to-head standard nine-category scoring is supported.",
            "lineup_slots": lineup,
            "acquisition_settings": {
                "weekly_add_limit": cap,
                "limit_per_scoring_period": per_day,
                "season_add_limit": acquisition.get("acquisitionLimit"),
            },
        },
        "period": {
            "matchup_period_id": matchup,
            "scoring_period_id": raw.get("scoringPeriodId"),
            "scoring_period_ids": periods,
            "dates": dates,
            "remaining_dates": remaining,
        },
        "selected_team_id": selected,
        "opponent_team_id": opponent,
        "teams": teams,
        "comparison": compare_categories(totals.get(selected), totals.get(compare_id), categories, compare_id),
        "matchup_history": history,
        "free_agents": free_agents,
        "free_agents_truncated": len(pool.get("players", [])) >= 100,
        "transactions": [
            {key: row.get(key) for key in ("id", "type", "status")}
            | {
                "team_id": row.get("teamId"),
                "scoring_period_id": row.get("scoringPeriodId"),
                "date": row.get("processDate") or row.get("acceptedDate"),
            }
            for row in transactions["transactions"]
        ]
        if "transactions" in transactions
        else None,
        "data_gaps": gaps,
        "optimizer": {"status": "unavailable", "reason": "Waiver optimizer integration is not installed."},
    }
