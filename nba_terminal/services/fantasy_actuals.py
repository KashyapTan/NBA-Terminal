"""NBA production joined only to ESPN's explicit daily scoring rosters.

Synchronous worker service. Never reconstruct historical ownership from current teams.
Missing game rows (including DNP without a box-score row) remain unknown.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from nba_api.live.nba.endpoints import boxscore
from nba_api.stats.endpoints import playergamelogs

from nba_terminal.services import fantasy_nba as nba

PRIMITIVES = ("pts", "reb", "ast", "stl", "blk", "threes", "to", "fgm", "fga", "ftm", "fta")
ACTIVE = frozenset(range(12))
LIVE_FIELDS = {
    "points": "pts",
    "reboundsTotal": "reb",
    "assists": "ast",
    "steals": "stl",
    "blocks": "blk",
    "threePointersMade": "threes",
    "turnovers": "to",
    "fieldGoalsMade": "fgm",
    "fieldGoalsAttempted": "fga",
    "freeThrowsMade": "ftm",
    "freeThrowsAttempted": "fta",
}


def complete(values):
    return (
        isinstance(values, dict)
        and all(nba.finite(values.get(k)) is not None and values[k] >= 0 for k in PRIMITIVES)
        and values["fgm"] <= values["fga"]
        and values["ftm"] <= values["fta"]
    )


def percentages(totals):
    return totals | {
        f"{prefix}_pct": totals[prefix + "m"] / totals[prefix + "a"] if totals[prefix + "a"] else None
        for prefix in ("fg", "ft")
    }


def fetch_logs(year, first, last):
    data = playergamelogs.PlayerGameLogs(
        season_nullable=nba.season_name(year),
        season_type_nullable="Regular Season",
        per_mode_simple="Totals",
        date_from_nullable=date.fromisoformat(first).strftime("%m/%d/%Y"),
        date_to_nullable=date.fromisoformat(last).strftime("%m/%d/%Y"),
        timeout=6,
    ).get_dict()
    table = next(t for t in data["resultSets"] if t["name"] == "PlayerGameLogs")
    if not {"PLAYER_ID", "GAME_ID", "GAME_DATE", *nba.FIELDS}.issubset(table["headers"]):
        raise ValueError("NBA game log schema changed")
    return {
        "rows": [dict(zip(table["headers"], row, strict=True)) for row in table["rowSet"]],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_live(game_id):
    game = boxscore.BoxScore(game_id=game_id, timeout=6).get_dict()["game"]
    if str(game["gameId"]) != str(game_id):
        raise ValueError("NBA game identity mismatch")
    rows = []
    for side in ("homeTeam", "awayTeam"):
        for player in game[side]["players"]:
            # An explicit not-played row is a verified zero; missing rows never are.
            values = {key: nba.finite(player.get("statistics", {}).get(field)) for field, key in LIVE_FIELDS.items()}
            if player.get("played") is False or player.get("played") == "0":
                values = dict.fromkeys(PRIMITIVES, 0.0)
            rows.append({"game_id": str(game_id), "nba_player_id": player["personId"], "totals": values})
    return {
        "rows": rows,
        "source_updated_at": None,  # Feed exposes game time, not a verified source update timestamp.
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "final": game.get("gameStatus") == 3,
    }


def production(year, dates, schedules):
    """One league-wide log batch plus at most 16 live/missing game requests, never N players."""
    rows, sources = {}, []
    if not dates:
        return rows, sources
    logs, status = nba.cached(
        ("actual_logs", year, min(dates), max(dates)), lambda: fetch_logs(year, min(dates), max(dates)), 60
    )
    sources.append(
        {"source": "nba_player_game_logs", "status": status, "fetched_at": logs.get("fetched_at") if logs else None}
    )
    game_states = {str(g["game_id"]): g.get("final") for items in schedules.values() for g in items}
    for row in (logs or {}).get("rows", []):
        key = (str(row["GAME_ID"]), str(row["PLAYER_ID"]))
        rows[key] = {
            "totals": {key: nba.finite(row.get(field)) for field, key in nba.FIELDS.items() if key in PRIMITIVES},
            "final": game_states.get(str(row["GAME_ID"])) is True,
            "status": status,
            "fetched_at": logs["fetched_at"],
            "source": "nba_player_game_logs",
        }
    games = {str(g["game_id"]): g for items in schedules.values() for g in items if g["date"] in dates and g["started"]}
    live_requests = 0
    for game_id, game in sorted(games.items()):
        # Logs cover finalized games. Today's games need live polling/corrections.
        if game["date"] < datetime.now(nba.NY).date().isoformat() and any(k[0] == game_id for k in rows):
            continue
        if live_requests >= 16:
            break
        live_requests += 1
        data, status = nba.cached(("actual_game", game_id), lambda: fetch_live(game_id), 30)
        sources.append(
            {
                "source": "nba_live_boxscore",
                "game_id": game_id,
                "status": status,
                "fetched_at": data.get("fetched_at") if data else None,
                "source_updated_at": data.get("source_updated_at") if data else None,
            }
        )
        if data:
            for row in data["rows"]:
                rows[(game_id, str(row["nba_player_id"]))] = row | {
                    "final": data["final"],
                    "status": status,
                    "source": "nba_live_boxscore",
                    "fetched_at": data["fetched_at"],
                }
    return rows, sources


def daily_lineups(raw, period, matchup, team_ids):
    """Require the explicit daily roster field and echoed scoring scope; reject current-roster proxies."""
    result = {}
    if raw.get("scoringPeriodId") != period:
        return result
    for match in raw.get("schedule", []):
        if match.get("matchupPeriodId") != matchup:
            continue
        for side in (match.get("home", {}), match.get("away", {})):
            roster = side.get("rosterForCurrentScoringPeriod")
            team = side.get("teamId")
            if team in team_ids and isinstance(roster, dict) and isinstance(roster.get("entries"), list):
                result[team] = roster["entries"]
    # Conflicting ownership or duplicate daily entries invalidate the whole day.
    ids = [
        entry.get("playerPoolEntry", {}).get("player", {}).get("id") for entries in result.values() for entry in entries
    ]
    if None in ids or len(set(ids)) != len(ids):
        return {}
    return result


def reconstruct(team_id, days, lineups, schedules, rows, official, fetched_at, *, history_complete=True):
    totals = dict.fromkeys(PRIMITIVES, 0.0)
    gaps, credited = [], set()
    expected, covered = 0, 0
    fresh, finalized = True, True
    for period, day in sorted(days.items()):
        entries = lineups.get(period, {}).get(team_id)
        if entries is None:
            gaps.append({"period": period, "reason": "historical_daily_lineup_missing"})
            continue
        for entry in entries:
            slot = entry.get("lineupSlotId")
            player = entry.get("playerPoolEntry", {}).get("player", {})
            eligible = player.get("eligibleSlots")
            if slot in (12, 13, 14, 15):
                continue
            if (
                isinstance(slot, bool)
                or slot not in ACTIVE
                or not isinstance(eligible, list)
                or slot not in eligible
                or entry.get("playerPoolEntry", {}).get("teamId", team_id) != team_id
            ):
                gaps.append({"period": period, "player_id": player.get("id"), "reason": "active_eligibility_unknown"})
                continue
            games = schedules.get(player.get("proTeamId"))
            if games is None:
                gaps.append({"period": period, "player_id": player.get("id"), "reason": "schedule_missing"})
                continue
            _, identity = nba.match_player({"name": player.get("fullName"), "pro_team_id": player.get("proTeamId")}, [])
            for game in games:
                if game["date"] != day or not game["started"]:
                    continue
                expected += 1
                key = (str(game["game_id"]), str(identity["nba_player_id"]))
                row = rows.get(key)
                if identity["nba_player_id"] is None or row is None or not complete(row.get("totals")):
                    gaps.append(
                        {
                            "period": period,
                            "player_id": player.get("id"),
                            "game_id": game["game_id"],
                            "reason": "nba_player_game_missing",
                        }
                    )
                    continue
                if key in credited:
                    gaps.append({"period": period, "reason": "duplicate_credit"})
                    continue
                credited.add(key)
                covered += 1
                fresh &= row.get("status") in ("fresh", "cached")
                finalized &= row.get("final") is True
                for key in PRIMITIVES:
                    totals[key] += row["totals"][key]
    is_complete = bool(days) and history_complete and not gaps and covered == expected and fresh
    derived = percentages(totals) if days and (covered or not gaps) else None
    # Prefer the independently reconstructed NBA basis only when every required fact is present/fresh.
    source = "nba_derived" if is_complete else "espn_official" if complete(official) else None
    return {
        "official": {"source": "espn_official", "totals": official, "fetched_at": fetched_at},
        "nba_derived": {
            "source": "nba_derived",
            "totals": derived,
            "complete": is_complete,
            "provisional": not is_complete or not finalized,
            "expected_player_games": expected,
            "covered_player_games": covered,
            "gaps": gaps,
            "fetched_at": fetched_at,
        },
        "forecast_source": source,
        "forecast_totals": derived if source == "nba_derived" else official if source else None,
        "forecast_complete": source is not None,
        "discrepancy": {k: derived[k] - official[k] for k in PRIMITIVES}
        if is_complete and derived is not None and complete(official)
        else None,
        "started_game_policy": "banked_only_no_projected_remainder",
    }


def enrich_snapshot(client, raw, snapshot, schedules):
    """Bounded private-history reads; callers already execute in the backend worker pool."""
    from nba_terminal.services.espn_fantasy import EspnError

    matchup = snapshot["period"]["matchup_period_id"]
    current = raw.get("scoringPeriodId")
    # Only ESPN-aligned calendar anchors establish the daily scoring-period/date join.
    anchors = {
        date.fromisoformat(g["date"]) - timedelta(days=g["scoring_period_id"])
        for team in snapshot["teams"]
        for p in team["roster"]
        for g in p.get("schedule") or []
    }
    periods = snapshot["period"]["scoring_period_ids"]
    days = {
        p: (next(iter(anchors)) + timedelta(days=p)).isoformat()
        for p in periods
        if len(anchors) == 1 and isinstance(current, int) and p <= current
    }
    team_ids = {snapshot["selected_team_id"], snapshot["opponent_team_id"]}
    lineups, failures = {}, []
    for period in sorted(days)[:14]:
        try:
            daily = client.get(
                ["mMatchupScore", "mScoreboard"],
                {"schedule": {"filterMatchupPeriodIds": {"value": [matchup]}}},
                scoring_period=period,
            )
            lineups[period] = daily_lineups(daily, period, matchup, team_ids)
        except EspnError as exc:
            failures.append({"period": period, "reason": exc.code})
    rows, sources = production(client.season_id, list(days.values()), schedules) if any(lineups.values()) else ({}, [])
    for team in snapshot["teams"]:
        if team["id"] in team_ids:
            team["actuals"] = reconstruct(
                team["id"],
                days,
                lineups,
                schedules,
                rows,
                team["totals"],
                snapshot["fetched_at"],
                history_complete=snapshot.get("enrichment", {}).get("schedule_status") != "stale"
                and len(days) <= 14
                and len(days) == len([p for p in periods if isinstance(current, int) and p <= current])
                and snapshot["period"].get("calendar_verified", False)
                and not snapshot["period"]["source"].endswith("partial"),
            )
            team["actuals"]["sources"] = sources
    snapshot.setdefault("projection_metadata", {}).update(
        {
            f"actuals_team_{team['id']}": {
                "complete": team["actuals"]["forecast_complete"],
                "source": team["actuals"]["forecast_source"],
                "as_of": snapshot["fetched_at"],
                "reason": "Completeness-gated banked production; started games have no projected remainder.",
            }
            for team in snapshot["teams"]
            if team["id"] in team_ids
        }
    )
    snapshot["actuals_coverage"] = {
        "history_day_limit": 14,
        "live_game_limit": 16,
        "history_failures": failures,
        "requested_days": sorted(days),
        "source": "espn_daily_scoring_rosters_join_nba",
    }
