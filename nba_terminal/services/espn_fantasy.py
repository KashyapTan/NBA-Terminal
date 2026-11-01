"""Read-only, unofficial ESPN basketball transport and honest normalization.

No credentials, network work, or persistent state are created at import time.
The HTTP facade owns short-lived per-browser sessions; clients must run in workers.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from nba_terminal.services import fantasy_actuals, fantasy_nba

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
    14: "IR+",
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
        raw = self.get(["mSettings", "mTeam", "mRoster", "mMatchup", "mMatchupScore", "mScoreboard", "mDraftDetail"])
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
        matchup = raw.get("status", {}).get("currentMatchupPeriod")
        selected_team = next((team for team in raw["teams"] if team["id"] == selected), {})
        ledger = selected_team.get("transactionCounter", {}).get("matchupAcquisitionTotals")
        used = count(ledger.get(str(matchup))) if isinstance(ledger, dict) else None
        if used is None:
            refreshed = optional("Current matchup acquisition ledger", lambda: self.get(["mTeam"]))
            if (
                refreshed.get("id") == raw["id"]
                and refreshed.get("seasonId") == raw["seasonId"]
                and refreshed.get("status", {}).get("currentMatchupPeriod") == matchup
            ):
                fresh_team = next((team for team in refreshed.get("teams", []) if team.get("id") == selected), {})
                counter = fresh_team.get("transactionCounter", {})
                values = counter.get("matchupAcquisitionTotals")
                if isinstance(values, dict) and count(values.get(str(matchup))) is not None:
                    raw = raw | {
                        "teams": [
                            team | {"transactionCounter": counter} if team["id"] == selected else team
                            for team in raw["teams"]
                        ],
                        "_matchup_counter_refreshed": selected,
                    }
            elif refreshed:
                gaps.append("Current matchup acquisition refresh rejected: league, season or matchup context mismatch.")
        schedule = optional("Professional schedule", lambda: self.get(["proTeamSchedules_wl"], season=True))
        pool = optional("Free agents", lambda: self.market(period))
        # Bounded card batches for roster and market IDs; never one request per player.
        ids = {player_id(entry) for team in raw["teams"] for entry in team.get("roster", {}).get("entries", [])}
        ids.update(player_id(entry) for entry in pool.get("players", []))
        ids.discard(None)
        if len(ids) > 5000:
            raise EspnError("league_too_large", "This league exceeds the supported player batch size.")
        card_rows = []
        for offset in range(0, len(ids), 250):
            card_batch = optional(
                "Player season samples",
                lambda offset=offset: self.get(
                    ["kona_playercard"],
                    {
                        "players": {
                            "filterIds": {"value": sorted(ids)[offset : offset + 250]},
                            "filterStatsForTopScoringPeriodIds": {
                                "value": period or 0,
                                "additionalValue": [f"00{self.season_id}", f"00{self.season_id - 1}"],
                            },
                        }
                    },
                ),
            )
            card_rows.extend(card_batch.get("players", []))
        cards = {"players": card_rows}
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
        # One prior-period batch repairs missing cumulative history for every team together.
        previous = (count(raw.get("status", {}).get("currentMatchupPeriod")) or 1) - 1
        previous_rows = [m for m in raw.get("schedule", []) if m.get("matchupPeriodId") == previous]
        covered = {
            side.get("teamId")
            for match in previous_rows
            for side in (match.get("home", {}), match.get("away", {}))
            if total_stats(side) is not None
        }
        if previous > 0 and covered != {team["id"] for team in raw["teams"]}:
            previous_raw = raw | {"status": raw.get("status", {}) | {"currentMatchupPeriod": previous}}
            previous_days, _ = matchup_scoring_periods(
                previous_raw, normalize_schedule(schedule, datetime.now(timezone.utc))
            )
            history = optional(
                "Prior matchup totals",
                lambda: self.get(
                    ["mMatchupScore", "mScoreboard"],
                    {"schedule": {"filterMatchupPeriodIds": {"value": [previous]}}},
                    scoring_period=max(previous_days) if previous_days else None,
                ),
            )
            replacements = [m for m in history.get("schedule", []) if m.get("matchupPeriodId") == previous]
            if replacements:
                raw = raw | {"schedule": merge_history(raw.get("schedule", []), replacements)}
        bundle = fantasy_nba.load(self.season_id)
        result = normalize(
            raw, schedule, pool, cards, transactions, selected, comparison, self.swid, gaps=gaps, nba=bundle
        )
        if any(
            p.get("season_rates") is None
            for team in result["teams"]
            for p in team["roster"]
            if team["id"] in {selected, result["opponent_team_id"]}
        ) or any(p.get("eligible") and p.get("season_rates") is None for p in result["free_agents"]):
            bundle |= fantasy_nba.load_prior_rates(self.season_id)
            fantasy_nba.enrich_players(result, bundle)
            update_rate_coverage(result)
        nba_schedule = fantasy_nba.schedule_games(bundle.get("schedule"), self.season_id, datetime.now(timezone.utc))
        # NBA game IDs are required for production; ESPN IDs must never be passed to NBA endpoints.
        fantasy_actuals.enrich_snapshot(self, raw, result, nba_schedule)
        return result

    def market(self, period: int | None) -> dict:
        """Enumerate observed league status pages with independent row/request bounds."""
        entries, seen, pages = [], set(), []
        total, offset, duplicates = None, 0, 0
        complete, stopped = False, "application_bound"
        page_size, market_limit, page_limit = 500, 2000, 8
        while offset < market_limit and len(pages) < page_limit:
            requested = min(page_size, market_limit - offset)
            try:
                page = self.get(
                    ["kona_player_info"],
                    {
                        "players": {
                            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
                            "limit": requested,
                            "offset": offset,
                            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                        }
                    },
                    scoring_period=period,
                )
            except EspnError as exc:
                if not entries:
                    raise
                stopped = "request_timeout" if exc.code == "timeout" else "upstream_error"
                break
            rows = page.get("players")
            pages.append(
                {"offset": offset, "requested": requested, "returned": len(rows) if isinstance(rows, list) else None}
            )
            if not isinstance(rows, list):
                stopped = "invalid_response"
                break
            reported_total = count(page.get("totalPlayers"))
            if reported_total is not None:
                if total is not None and total != reported_total:
                    stopped = "unstable_total"
                    break
                total = reported_total
            added = 0
            for entry in rows[:requested]:
                pid = player_id(entry)
                if pid is not None and pid not in seen:
                    seen.add(pid)
                    entries.append(entry)
                    added += 1
            duplicates += len(rows[:requested]) - added
            if added < len(rows[:requested]):
                stopped = "repeated_or_invalid_page"
                break
            if not rows:
                complete = total is None or len(entries) >= total
                stopped = "terminal_page" if complete else "empty_before_reported_total"
                break
            if total is not None and len(entries) >= total:
                complete, stopped = True, "provider_total"
                break
            # Confirm exhaustion with an empty page when no total is reported.
            # Advancing by returned size also handles a server's smaller page cap.
            offset += len(rows)
        return {
            "players": entries,
            "coverage": {
                "complete": complete,
                "observed": len(entries),
                "provider_total": total,
                "limit": market_limit,
                "page_size": page_size,
                "page_limit": page_limit,
                "page_count": len(pages),
                "pages": pages,
                "duplicate_count": duplicates,
                "terminal_observed": complete,
                "stopped_reason": stopped,
                "enumeration_filter": ["FREEAGENT", "WAIVERS"],
                "season_id": self.season_id,
                "scoring_period_id": period,
                "source": "espn_paginated_market",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        }


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
    if totals and games and games > 0:
        averages = {key: value / games if value is not None else None for key, value in totals.items()}
        for key in ("fg_pct", "ft_pct"):
            averages[key] = totals[key]
        # Preserve explicit averages for fields absent from cumulative stats.
        supplied = stats(split.get("averageStats")) or {}
        averages = {key: value if value is not None else supplied.get(key) for key, value in averages.items()}
    return averages, games


def normalize_schedule(raw: dict, now: datetime, *, periods=None, anchors_only=False) -> dict[int, list[dict]]:
    result = {}
    for team in raw.get("settings", {}).get("proTeams", []):
        if "proGamesByScoringPeriod" not in team:
            continue
        games, unknown = [], False
        for period, entries in team["proGamesByScoringPeriod"].items():
            try:
                scoring_id = int(period)
            except (ValueError, TypeError):
                unknown = True
                continue
            if periods is not None and scoring_id not in periods:
                unknown |= any(count(g.get("scoringPeriodId")) in periods for g in entries)
                continue
            for game in entries:
                if "scoringPeriodId" in game and count(game["scoringPeriodId"]) != scoring_id:
                    unknown = True
                    continue
                timestamp = number(game.get("date"))
                if timestamp is None:
                    unknown = True
                    continue
                try:
                    start = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
                    scoring_id = int(period)
                except (ValueError, OverflowError, OSError):
                    unknown = True
                    continue
                if game.get("validForLocking") is False:
                    continue
                if game.get("startTimeTBD"):
                    unknown = True
                    continue
                games.append(
                    {
                        "game_id": game.get("id"),
                        "source": "espn_schedule",
                        "scoring_period_id": scoring_id,
                        "date": start.astimezone(NY).date().isoformat(),
                        "start_at": start.isoformat(),
                        "started": start <= now,
                        "opponent_pro_team_id": game.get("awayProTeamId")
                        if game.get("homeProTeamId") == team["id"]
                        else game.get("homeProTeamId"),
                    }
                )
        if not unknown or anchors_only:
            result[team["id"]] = sorted(games, key=lambda game: game["start_at"])
    return result


def normalize_player(
    entry: dict, cards: dict, schedules: dict, year: int, periods: list[int], now: datetime, *, rostered: bool = False
) -> dict:
    pool = entry.get("playerPoolEntry", entry)
    original = player_body(entry)
    card = cards.get(original.get("id"), {})
    player = original | card
    # A sparse card response must not erase usable actual samples already in the roster/pool.
    splits = {}
    for split in original.get("stats", []) + card.get("stats", []):
        key = tuple(split.get(field) for field in ("seasonId", "statSourceId", "statSplitTypeId", "scoringPeriodId"))
        old = splits.get(key, {})
        splits[key] = old | split
        for field in ("stats", "averageStats"):
            if field in old or field in split:
                splits[key][field] = (old.get(field) or {}) | (split.get(field) or {})
    player["stats"] = list(splits.values())
    current, games = samples(player, year)
    prior, prior_games = samples(player, year - 1)
    schedule = schedules.get(player.get("proTeamId")) if periods else None
    schedule = [game for game in schedule if game["scoring_period_id"] in periods] if schedule is not None else None
    availability = "ONTEAM" if rostered else pool.get("status", "UNKNOWN")
    positions = [SLOTS.get(slot, f"UNKNOWN_{slot}") for slot in player.get("eligibleSlots", [])]
    injury = player.get("injuryStatus")
    out = str(injury or "").upper() in {
        "OUT",
        "O",
        "INACTIVE",
        "INJURY_RESERVE",
        "SUSPENDED",
        "SUSPENSION",
        "RESERVE_RETIRED",
    }
    droppable = player.get("droppable") if isinstance(player.get("droppable"), bool) else None
    return {
        "id": str(player.get("id", original.get("id"))),
        "name": player.get("fullName"),
        "pro_team_id": player.get("proTeamId"),
        "positions": positions,
        "lineup_slot": SLOTS.get(entry.get("lineupSlotId")),
        "active": entry.get("lineupSlotId") not in (13, 14),
        "injury_status": injury,
        "health_status": "out" if out else "available",
        "health_source": "espn" if out or injury == "ACTIVE" else "assumed_available",
        "droppable": droppable,
        "undroppable": not droppable if droppable is not None else None,
        "lock_source": None,
        "undroppable_source": "espn_player_droppable" if droppable is not None else None,
        "draft_rank": number(player.get("draftRanksByRankType", {}).get("STANDARD", {}).get("rank")),
        "draft_pick": None,
        "draft_round": None,
        "injured": player.get("injured"),
        "locked": None,
        "provider_locks": {
            key: pool.get(key)
            for key in ("lineupLocked", "rosterLocked", "tradeLocked")
            if isinstance(pool.get(key), bool)
        },
        "lock_semantics": "Provider flags retained separately; they do not by themselves establish drop legality.",
        "on_team_id": pool.get("onTeamId"),
        "availability": availability,
        "eligible": availability == "FREEAGENT"
        and pool.get("onTeamId") in (None, 0)
        and any(position in set(SLOTS.values()) - {"BENCH", "IR", "IR+", "Rookie"} for position in positions),
        "current_rates": current,
        "current_rates_source": "espn_actual_season" if current is not None else None,
        "schedule_source": schedule[0].get("source") if schedule else None,
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


def merge_history(existing: list[dict], incoming: list[dict]) -> list[dict]:
    def key(match):
        return match.get("matchupPeriodId"), match.get("home", {}).get("teamId"), match.get("away", {}).get("teamId")

    rows = {key(match): match for match in existing}
    for match in incoming:
        old = rows.get(key(match), {})
        merged = old | match
        for side in ("home", "away"):
            if total_stats(match.get(side, {})) is None and total_stats(old.get(side, {})) is not None:
                merged[side] = old[side]
        rows[key(match)] = merged
    return list(rows.values())


def count(value: Any) -> int | None:
    value = number(value)
    return int(value) if value is not None and value >= 0 and value.is_integer() else None


def scoring_date_anchors(schedules: dict) -> set[date]:
    return {
        date.fromisoformat(game["date"]) - timedelta(days=game["scoring_period_id"])
        for games in schedules.values()
        for game in games
    }


def matchup_scoring_periods(raw: dict, schedules: dict) -> tuple[list[int], str]:
    settings = raw["settings"].get("scheduleSettings", {})
    matchup = raw.get("status", {}).get("currentMatchupPeriod")
    values = settings.get("matchupPeriods", {}).get(str(matchup), [])
    if settings.get("periodTypeId") != 2:
        return [int(period) for period in values], "espn_scoring_periods"
    # WEEKLY maps matchup IDs to week indices, not to daily scoring IDs. Week 1 can be short.
    anchors = scoring_date_anchors(schedules)
    if len(anchors) == 1 and values:
        day_zero = next(iter(anchors))
        first = day_zero + timedelta(days=1)
        monday = first - timedelta(days=first.weekday())
        days = []
        for week in values:
            start = max(first, monday + timedelta(weeks=int(week) - 1))
            end = monday + timedelta(weeks=int(week), days=-1)
            days.extend(range((start - day_zero).days, (end - day_zero).days + 1))
        # Reject calendar drift instead of silently assigning a different live matchup.
        observed = {
            int(key)
            for match in raw.get("schedule", [])
            if match.get("matchupPeriodId") == matchup
            for side in (match.get("home", {}), match.get("away", {}))
            for key in side.get("pointsByScoringPeriod", {})
        }
        if observed.issubset(days):
            return days, "espn_weekly_calendar"
    observed = sorted(
        {
            int(key)
            for match in raw.get("schedule", [])
            if match.get("matchupPeriodId") == matchup
            for side in (match.get("home", {}), match.get("away", {}))
            for key in side.get("pointsByScoringPeriod", {})
        }
    )
    return observed, "espn_observed_scoring_periods_partial"


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
    nba: dict | None = None,
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
    anchor_schedules = normalize_schedule(schedule, now, anchors_only=True)
    scoped_periods, scoped_source = matchup_scoring_periods(raw, anchor_schedules)
    schedules = normalize_schedule(schedule, now, periods=set(scoped_periods) if scoped_periods else None)
    schedule_sources = {team: "espn_schedule" for team in schedules}
    calendar_verified = len(scoring_date_anchors(anchor_schedules)) == 1
    if nba is not None:
        fallback = fantasy_nba.schedule_games(nba.get("schedule"), raw["seasonId"], now)
        anchors = scoring_date_anchors(anchor_schedules)
        if len(anchors) == 1:
            anchor = next(iter(anchors))
            for games in fallback.values():
                for game in games:
                    game["scoring_period_id"] = (date.fromisoformat(game["date"]) - anchor).days
        for team in fallback:
            if nba.get("schedule_status") in ("fresh", "cached") or team not in schedules:
                schedule_sources[team] = "nba_schedule"
        # Fresh NBA schedule is primary; stale NBA never displaces a usable ESPN schedule.
        schedules = (
            (schedules | fallback) if nba.get("schedule_status") in ("fresh", "cached") else (fallback | schedules)
        )
    periods, period_source = (
        (scoped_periods, scoped_source) if calendar_verified else matchup_scoring_periods(raw, schedules)
    )
    dates = sorted(
        {game["date"] for games in schedules.values() for game in games if game["scoring_period_id"] in periods}
    )
    if period_source == "espn_weekly_calendar" and periods:
        anchors = scoring_date_anchors(anchor_schedules) if calendar_verified else scoring_date_anchors(schedules)
        if len(anchors) == 1:
            anchor = next(iter(anchors))
            dates = [(anchor + timedelta(days=period)).isoformat() for period in periods]
    remaining = sorted(
        {
            game["date"]
            for games in schedules.values()
            for game in games
            if game["scoring_period_id"] in periods and not game["started"]
        }
    )
    # Calendar remaining dates include off days; per-player schedules still count only real games.
    if dates:
        today = now.astimezone(NY).date().isoformat()
        remaining = [day for day in dates if day >= today]
    card_map = {player_id(entry): player_body(entry) for entry in cards.get("players", [])}
    draft = {pick.get("playerId"): pick for pick in raw.get("draftDetail", {}).get("picks", [])}
    acquisition = settings.get("acquisitionSettings", {})
    raw_cap = count(acquisition.get("matchupAcquisitionLimit"))
    per_day = acquisition.get("matchupLimitPerScoringPeriod")
    absent_cap = "matchupAcquisitionLimit" not in acquisition or acquisition["matchupAcquisitionLimit"] is None
    fallback_cap = (
        raw["id"] == 604550749
        and raw["seasonId"] == 2027
        and acquisition.get("matchupAcquisitionLimit") != -1
        and (absent_cap or per_day is not False)
    )
    cap = 7 if fallback_cap else raw_cap if per_day is False else None
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
        for player in roster:
            if settings.get("rosterSettings", {}).get("isUsingUndroppableList") is False:
                player["undroppable"] = False
                player["undroppable_source"] = "espn_league_undroppable_disabled"
            pick = draft.get(int(player["id"]), {})
            player["draft_pick"] = count(pick.get("overallPickNumber"))
            player["draft_round"] = count(pick.get("roundId"))
            player["draft_source"] = "espn_draft_detail" if pick else None
            if team.get("isTransactionLocked") is True:
                player["locked"], player["lock_source"] = True, "espn_team_transaction_lock"
        counter = team.get("transactionCounter", {})
        matchup_counts = counter.get("matchupAcquisitionTotals")
        used = count(matchup_counts.get(str(matchup))) if isinstance(matchup_counts, dict) else None
        roster_ids.update(player["id"] for player in roster)
        teams.append(
            {
                "id": team["id"],
                "name": choices[team["id"]]["name"],
                "ownership_verified": choices[team["id"]]["ownership_verified"],
                "roster": roster,
                "totals": totals.get(team["id"]),
                "actuals": fantasy_actuals.reconstruct(
                    team["id"], {}, {}, {}, {}, totals.get(team["id"]), now.isoformat()
                ),
                "season_acquisitions": team.get("transactionCounter", {}).get("acquisitions"),
                "weekly_used_adds": used,
                "weekly_usage_source": (
                    "espn_matchup_acquisition_totals_targeted_refresh"
                    if raw.get("_matchup_counter_refreshed") == team["id"]
                    else "espn_matchup_acquisition_totals"
                    if used is not None
                    else None
                ),
                "weekly_usage_complete": used is not None,
                "remaining_adds": max(0, cap - used) if cap is not None and used is not None else None,
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
    lineup_counts = settings.get("rosterSettings", {}).get("lineupSlotCounts", {})
    lineup = [
        SLOTS.get(int(slot), f"UNKNOWN_{slot}")
        for slot, count in lineup_counts.items()
        if int(slot) not in (12, 13, 14, 15)
        for _ in range(min(max(int(count), 0), 50))
    ]
    if next(team for team in teams if team["id"] == selected)["weekly_used_adds"] is None:
        gaps.append("Selected matchup acquisition usage is unavailable; season/day counts are not matchup usage.")
    if not periods or not dates:
        gaps.append("Matchup date coverage is unavailable; no dates were inferred from a nominal week.")
    all_players = [p for team in teams for p in team["roster"]] + free_agents
    required_players = [p for team in teams if team["id"] in {selected, opponent} for p in team["roster"]]
    for player in all_players:
        player["schedule_source"] = (
            schedule_sources.get(player["pro_team_id"]) if player["schedule"] is not None else None
        )
    if any(p["schedule"] is None and p["active"] and p["health_status"] != "out" for p in required_players):
        gaps.append("Selected-roster professional schedules are unavailable; missing schedules are not zero games.")
    if not swid:
        gaps.append("Public league team selection does not verify ownership.")
    compare_id = comparison if comparison is not None else opponent
    result = {
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
                "matchup_add_limit": cap,
                "reported_add_limit": raw_cap,
                "reported_limit_scope": "day" if per_day is True else "matchup" if per_day is False else "unknown",
                "daily_add_limit": raw_cap if per_day is True else None,
                "cap_source": "league_fallback_7"
                if fallback_cap
                else "espn_acquisition_settings"
                if raw_cap is not None
                else None,
                "unlimited": acquisition.get("matchupAcquisitionLimit") == -1,
                "season_add_limit": acquisition.get("acquisitionLimit"),
            },
        },
        "period": {
            "matchup_period_id": matchup,
            "scoring_period_id": raw.get("scoringPeriodId"),
            "scoring_period_ids": periods,
            "dates": dates,
            "remaining_dates": remaining,
            "source": period_source,
            "calendar_verified": calendar_verified,
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
        },
        "projection_metadata": {
            "matchup_calendar": {
                "complete": calendar_verified,
                "source": "espn_scoring_date_anchors",
                "reason": (
                    "Verified ESPN scoring-date anchor"
                    if calendar_verified
                    else "ESPN scoring-date anchor unavailable or conflicting; NBA dates alone cannot verify matchup"
                ),
            }
        },
        "selected_team_id": selected,
        "opponent_team_id": opponent,
        "teams": teams,
        "comparison": compare_categories(totals.get(selected), totals.get(compare_id), categories, compare_id),
        "matchup_history": history,
        "history_coverage": [
            {
                "team_id": team["id"],
                "prior_periods": sorted(
                    {
                        row["matchup_period_id"]
                        for row in history
                        if (row["home_team_id"] == team["id"] and row["home_totals"] is not None)
                        or (row["away_team_id"] == team["id"] and row["away_totals"] is not None)
                    }
                ),
            }
            for team in teams
        ],
        "free_agents": free_agents,
        "free_agents_truncated": not pool.get("coverage", {}).get("complete", False),
        "market_complete": pool.get("coverage", {}).get("complete"),
        "market_coverage": pool.get(
            "coverage",
            {"complete": False, "observed": len(pool.get("players", [])), "source": "espn_unverified_single_page"},
        ),
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
        "modeling_notes": [
            "Provider lineup/roster/trade lock flags are retained; their drop semantics are unverified. "
            "ESPN transaction validation remains authoritative.",
            "Transaction rows cover the requested scoring day; matchup usage uses ESPN's separate matchup counter.",
        ],
        "optimizer": {
            "status": "requires_inputs",
            "reason": "Submit snapshot-bound confirmed constraints to the read-only planner.",
            "endpoint": "/api/fantasy/espn/plan",
        },
    }

    if nba is not None:
        fantasy_nba.enrich_players(result, nba)
    update_rate_coverage(result)
    return result


def update_rate_coverage(snapshot):
    """Scope required gaps to the selected forecast; retain separate market exclusion counts."""
    required = [
        p
        for team in snapshot["teams"]
        if team["id"] in {snapshot["selected_team_id"], snapshot["opponent_team_id"]}
        for p in team["roster"]
    ]

    def basis(p):
        if "season_rates" in p:
            return p["season_rates"]
        current = p.get("current_rates")
        return current if fantasy_nba.usable_rates(current) else p.get("prior_rates")

    missing = [p for p in required if not fantasy_nba.usable_rates(basis(p))]
    snapshot["data_gaps"] = [
        g
        for g in snapshot["data_gaps"]
        if not g.startswith(
            (
                "Selected-roster rate samples",
                "Selected-roster shooting",
                "Some current/prior season average samples",
                "Some shooting attempts/makes",
            )
        )
    ]
    if missing:
        snapshot["data_gaps"].append(
            f"Selected-roster rate samples unavailable for {len(missing)} players after source fallbacks."
        )
    if any((basis(p) or {}).get(k) is None for p in required for k in ("fgm", "fga", "ftm", "fta")):
        snapshot["data_gaps"].append(
            "Selected-roster shooting pairs unavailable; percentage gains cannot be weighted safely."
        )
    market = snapshot["free_agents"]
    snapshot["market_coverage"].update(
        {
            "eligible_freeagent_count": sum(p["eligible"] for p in market),
            "waiver_count": sum(p["availability"] == "WAIVERS" for p in market),
            "roster_conflict_count": sum(p.get("on_team_id") not in (None, 0) for p in market),
            "no_sample_count": sum(not fantasy_nba.usable_rates(basis(p)) for p in market),
            "no_schedule_count": sum(p["schedule"] is None for p in market),
        }
    )
    snapshot["data_gaps"] = list(dict.fromkeys(snapshot["data_gaps"]))
