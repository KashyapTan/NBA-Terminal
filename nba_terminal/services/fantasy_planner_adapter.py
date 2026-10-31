"""Translate a server-owned ESPN snapshot into a constrained, read-only plan.

No network or authentication lives here. The authenticated route must supply its
own snapshot and run this CPU work in a bounded worker, never the event loop.
"""

from datetime import date, datetime, timezone
from math import isfinite
from statistics import stdev
from zoneinfo import ZoneInfo

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, plan_waivers

ACTIVE_SLOTS = {"PG", "SG", "SF", "PF", "C", "G", "F", "SG/SF", "G/F", "PF/C", "F/C", "UTIL"}


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100


def _totals(values):
    if not isinstance(values, dict) or any(
        isinstance(values.get(k), bool)
        or not isinstance(values.get(k), (int, float))
        or not isfinite(values[k])
        or values[k] < 0
        for k in TOTALS
    ):
        return None
    if values["fgm"] > values["fga"] or values["ftm"] > values["fta"]:
        return None
    return {key: values[key] for key in TOTALS}


def _values(values):
    totals = _totals(values)
    if totals is None or not totals["fga"] or not totals["fta"]:
        return None
    return {**totals, "fg_pct": totals["fgm"] / totals["fga"], "ft_pct": totals["ftm"] / totals["fta"]}


def _history(snapshot, user_id, target_id):
    periods = {}
    for row in snapshot.get("matchup_history", []):
        period = row.get("matchup_period_id")
        if not isinstance(period, int) or period >= snapshot["period"]["matchup_period_id"]:
            continue
        teams = periods.setdefault(period, {})
        for side in ("home", "away"):
            teams[row.get(f"{side}_team_id")] = _values(row.get(f"{side}_totals"))
    margins = []
    for teams in periods.values():
        ours, theirs = teams.get(user_id), teams.get(target_id)
        if ours is not None and theirs is not None:
            margins.append({k: (ours[k] - theirs[k]) * (-1 if k == "to" else 1) for k in CATEGORIES})
    if len(margins) < 3 or any(stdev(row[k] for row in margins) <= 0 for k in CATEGORIES):
        return None
    return margins


def _forecast_view(forecast):
    if forecast is None:
        return None
    return {
        "basis": "forecast",
        "totals": forecast["user_totals"],
        "games": forecast["games"]["user"],
        "minutes": forecast["minutes"]["user"],
        "probability_five_wins": forecast["win_at_least_five_probability"],
        "categories": forecast["categories"],
        "opponent_totals": forecast["opponent_totals"],
    }


def plan_snapshot_waivers(snapshot, preferences, now=None):
    """Use only server snapshot facts and explicit context-bound user confirmations."""
    now = now or datetime.now(timezone.utc)
    gaps, provenance = [], {}
    user_id, target_id = snapshot["selected_team_id"], snapshot.get("opponent_team_id")
    teams = {team["id"]: team for team in snapshot["teams"]}
    user, target = teams.get(user_id), teams.get(target_id)
    result = {
        "status": "unavailable",
        "reasons": [],
        "actions": [],
        "baseline": None,
        "projected": None,
        "remaining_adds": None,
        "assumptions": [],
        "limitations": [],
        "data_gaps": gaps,
        "provenance": provenance,
    }
    expected = {
        "league_id": snapshot["league"]["id"],
        "team_id": user_id,
        "matchup_period_id": snapshot["period"]["matchup_period_id"],
        "fetched_at": snapshot["fetched_at"],
    }
    if preferences.get("context") != expected:
        result["reasons"] = ["Snapshot changed. Refresh and reconfirm inputs for this league, team and matchup."]
        return result
    if not snapshot["league"].get("supported") or user is None or target is None or target_id == user_id:
        result["reasons"] = ["A supported nine-category league and an actual current opponent are required."]
        return result
    # Preserve actuals as a useful comparison when future inputs cannot be validated.
    result["baseline"] = {
        "basis": "recorded",
        "totals": user.get("totals") or {},
        "games": None,
        "minutes": None,
        "probability_five_wins": None,
    }
    provenance["context"] = expected
    provenance["snapshot_data_gaps"] = snapshot.get("data_gaps", [])
    settings = snapshot["league"].get("acquisition_settings", {})
    if settings.get("limit_per_scoring_period") is True:
        gaps.append("This league has per-day acquisition rules; daily acquisition budgets are not modeled.")
    if preferences.get("user_confirmed_counts") is True:
        counts = [preferences.get(k) for k in ("weekly_add_limit", "used_adds", "available_adds")]
        provenance["counts"] = "user_confirmed for this snapshot and matchup"
    elif settings.get("limit_per_scoring_period") is False:
        # ESPN scoring periods are days; a matchup cap is usable only when this is explicitly false.
        counts = [settings.get("weekly_add_limit"), user.get("weekly_used_adds"), user.get("remaining_adds")]
        provenance["counts"] = "ESPN complete matchup counts"
    else:
        counts = [None, None, None]
    if not all(_integer(n) for n in counts) or counts[1] + counts[2] > counts[0]:
        gaps.append(
            "Confirm weekly cap, adds used and adds remaining; nonnegative integers with used + remaining <= cap."
        )
    else:
        result["remaining_adds"] = counts[2]
    candidates, drops = preferences.get("candidate_ids", []), preferences.get("droppable_ids", [])
    if (
        not isinstance(candidates, list)
        or not isinstance(drops, list)
        or any(not isinstance(pid, str) for pid in [*candidates, *drops])
        or len(candidates) != len(set(candidates))
        or len(drops) != len(set(drops))
    ):
        result["reasons"] = ["Shortlist and drop choices must contain unique player IDs."]
        return result
    rostered = {p["id"] for team in teams.values() for p in team["roster"]}
    market = {
        p["id"]: p
        for p in snapshot.get("free_agents", [])
        if p.get("eligible") is True and p.get("availability") == "FREEAGENT" and p["id"] not in rostered
    }
    roster = {p["id"]: p for p in user["roster"]}
    if (
        not candidates
        or not drops
        or any(pid not in market for pid in candidates)
        or any(
            pid not in roster or roster[pid].get("locked") is True or roster[pid].get("lineup_slot") in {"IR", "IR+"}
            for pid in drops
        )
    ):
        result["reasons"] = ["Choose eligible unrostered free agents and unlocked user roster players to stream."]
        return result
    if preferences.get("user_confirmed_eligibility") is not True:
        gaps.append("Confirm that each selected add and drop is available now in ESPN for this matchup.")
    slots = preferences.get("max_stream_slots")
    if not _integer(slots) or not 1 <= slots <= 4:
        gaps.append("Maximum stream slots must be an integer from one to four.")
    remaining = preferences.get("remaining_dates", snapshot["period"].get("remaining_dates"))
    if "remaining_dates" in preferences:
        try:
            today = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
            period_dates = snapshot["period"].get("dates", [])
            if (
                not isinstance(remaining, list)
                or not 1 <= len(remaining) <= 14
                or len(set(remaining)) != len(remaining)
                or any(date.fromisoformat(d).isoformat() != d or d < today for d in remaining)
                or (period_dates and any(d not in period_dates for d in remaining))
            ):
                raise ValueError
            remaining = sorted(remaining)
            provenance["remaining_dates"] = "user_confirmed remaining matchup dates"
        except (TypeError, ValueError):
            gaps.append("Confirm one to fourteen unique remaining ISO dates in the current matchup, not past dates.")
            remaining = []
    if not isinstance(remaining, list) or not remaining:
        gaps.append("No verified remaining matchup dates. Refresh the snapshot or wait for the next matchup.")
        remaining = []
    lineup = [s for s in snapshot["league"].get("lineup_slots", []) if s not in ("BENCH", "IR", "IR+")]
    if not lineup or any(slot not in ACTIVE_SLOTS for slot in lineup):
        gaps.append("Active lineup slot rules are missing or unsupported in ESPN.")
    overrides = preferences.get("player_overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}
        gaps.append("Player corrections must be keyed by player ID.")
    players = []
    relevant = [(p, "user") for p in user["roster"]] + [(p, "opponent") for p in target["roster"]]
    relevant += [(market[pid], "free") for pid in candidates]
    if not user["roster"] or not target["roster"]:
        gaps.append("Complete user and opponent rosters are required.")
    for player, owner in relevant:
        pid, name = player["id"], player["name"]
        if player.get("lineup_slot") in {"IR", "IR+"}:
            provenance[f"inactive:{pid}"] = "IR player excluded; moves out of IR are not modeled"
            continue
        override = overrides.get(pid, {})
        if not isinstance(override, dict):
            override = {}
        schedule = player.get("schedule")
        if "schedule" in override:
            dates = override["schedule"]
            try:
                if (
                    not isinstance(dates, list)
                    or any(date.fromisoformat(d).isoformat() != d for d in dates)
                    or len(set(dates)) != len(dates)
                    or any(d not in remaining for d in dates)
                ):
                    raise ValueError
                # User corrections cannot resurrect a known already-started game today.
                started = {g["date"] for g in schedule or [] if g.get("started") is True}
                if any(d in started for d in dates):
                    raise ValueError
                provenance[f"schedule:{pid}"] = "user_confirmed unstarted, transaction-effective remaining games"
            except (ValueError, TypeError):
                gaps.append(f"{name}: confirm unique remaining unstarted ISO game dates.")
                dates = None
        elif schedule is None:
            dates = None
            gaps.append(f"{name}: remaining schedule is unknown; enter verified unstarted game dates.")
        else:
            dates = []
            for game in schedule:
                try:
                    start = datetime.fromisoformat(game["start_at"].replace("Z", "+00:00"))
                    if start.tzinfo is None or not isinstance(game.get("started"), bool):
                        raise ValueError
                    if not game["started"] and start > now and game["date"] in remaining:
                        dates.append(game["date"])
                except (ValueError, TypeError, KeyError):
                    gaps.append(f"{name}: game start/lock timing is unknown.")
            provenance[f"schedule:{pid}"] = "ESPN unstarted games checked against server time"
        injured = override.get("injured", player.get("injured"))
        if "injured" not in override and str(player.get("injury_status", "")).upper() in {
            "OUT",
            "O",
            "INACTIVE",
            "SUSPENDED",
            "SUSPENSION",
        }:
            injured = True
        if "injured" in override and isinstance(injured, bool):
            provenance[f"availability:{pid}"] = "user_confirmed availability for the modeled remaining dates"
        if not isinstance(injured, bool):
            gaps.append(f"{name}: availability is unknown; confirm available or out for modeled dates.")
        sample = player.get("current_games")
        if isinstance(sample, (int, float)) and not isinstance(sample, bool) and isfinite(sample) and sample >= 0:
            sample = int(sample) if sample == int(sample) else None
        elif player.get("current_rates") is None and player.get("prior_rates") is not None:
            sample = 0  # explicitly prior-only, no current sample is asserted
        else:
            sample = None
        if sample is None:
            gaps.append(f"{name}: integral observed season sample count is missing.")
        positions = [position for position in player.get("positions") or [] if position in ACTIVE_SLOTS]
        if not positions:
            gaps.append(f"{name}: active lineup eligibility is unknown or unsupported.")
        if player.get("current_rates") is None and player.get("prior_rates") is None:
            gaps.append(f"{name}: current and prior season rates are unavailable.")
        for season in ("current_rates", "prior_rates"):
            rates = player.get(season)
            if rates is not None and (
                _totals(rates) is None
                or isinstance(rates.get("minutes"), bool)
                or not isinstance(rates.get("minutes"), (int, float))
                or not isfinite(rates["minutes"])
                or rates["minutes"] < 0
            ):
                gaps.append(f"{name}: {season} needs complete valid category makes/attempts and observed minutes.")
        # Locked here means planner cannot transact; it does not assert ESPN's unknown lock is true.
        allowed_move = owner == "free" or (owner == "user" and pid in drops)
        locked = (
            not allowed_move
            or player.get("locked") is True
            or preferences.get("user_confirmed_eligibility") is not True
        )
        players.append(
            {
                "id": pid,
                "owner": owner,
                "positions": positions,
                "eligible": True,
                "locked": locked,
                "schedule": dates,
                "injury_status": "out" if injured is True else "active",
                "current_rates": player.get("current_rates"),
                "prior_rates": player.get("prior_rates"),
                "current_games": sample,
            }
        )
    provenance["transactions"] = "user_confirmed selected adds/drops; all unselected roster slots protected"
    provenance["candidate_ids"] = candidates
    provenance["droppable_ids"] = drops
    history = _history(snapshot, user_id, target_id)
    payload = {
        "dates": remaining,
        "current_totals": user.get("totals"),
        "opponent_totals": target.get("totals"),
        "players": players,
        "lineup_slots": lineup,
        "weekly_add_limit": counts[0],
        "used_adds": counts[1],
        "available_adds": counts[2],
        "max_stream_slots": slots,
        "candidate_limit": min(40, max(1, len(candidates))),
        "evaluation_limit": 500,
    }
    if preferences.get("uncertainty_mode") not in (None, "history", "sensitivity"):
        gaps.append("Choose historical evidence or explicitly opt into sensitivity mode.")
    if preferences.get("uncertainty_mode") == "sensitivity":
        deviations = preferences.get("margin_sd")
        if not isinstance(deviations, dict) or any(
            isinstance(deviations.get(k), bool)
            or not isinstance(deviations.get(k), (int, float))
            or not isfinite(deviations[k])
            or deviations[k] <= 0
            for k in CATEGORIES
        ):
            gaps.append("Sensitivity mode requires a positive margin standard deviation for each of nine categories.")
        else:
            payload["margin_sd"] = deviations
            provenance["uncertainty"] = "user_selected sensitivity assumptions; not historical/calibrated probabilities"
    elif history:
        payload["prior_week_margins"] = history
        provenance["uncertainty"] = f"{len(history)} complete prior same-period team comparisons; uncalibrated"
    else:
        gaps.append(
            "Insufficient historical variance. Use baseline comparisons or explicitly enter sensitivity assumptions."
        )
    if gaps:
        result.update(status="incomplete", reasons=list(gaps))
        result["assumptions"] = ["Baseline contains recorded matchup totals only; a future forecast is withheld."]
        return result
    planned = plan_waivers(payload)
    result.update(
        {k: planned[k] for k in ("status", "reasons", "actions", "remaining_adds", "assumptions", "limitations")}
    )
    result["baseline"] = _forecast_view(planned["baseline"]) or result["baseline"]
    result["projected"] = _forecast_view(planned["projected"])
    result["provenance"]["rates"] = planned["provenance"]
    result["search"] = planned["search"]
    result["assumptions"].append(
        "Sensitivity mode uses your nine entered margin standard deviations, not measured historical uncertainty."
        if preferences.get("uncertainty_mode") == "sensitivity"
        else f"Uncertainty uses {len(history)} complete prior weekly comparisons between these teams."
    )
    result["assumptions"].append(
        "Weekly counts and selected add/drop availability are user-confirmed for this snapshot."
        if preferences.get("user_confirmed_counts") is True
        else "Weekly counts come from ESPN; selected add/drop availability is user-confirmed for this snapshot."
    )
    if overrides:
        result["assumptions"].append(
            "Schedule or availability corrections are user-confirmed inputs for this snapshot."
        )
    if planned["search"]["evaluation_limit_reached"]:
        result["limitations"].append("Search reached its 500-evaluation production limit; a better plan may exist.")
    # Human-readable stream slot ordinal, while retaining the actual roster ancestry identifier.
    for action in result["actions"]:
        action["stream_roster_id"] = action["stream_slot"]
        action["stream_slot"] = drops.index(action["stream_slot"]) + 1
    return result
