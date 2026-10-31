"""Translate server-owned league facts into pure, read-only waiver recommendations.

No network, authentication or transactions live here. Unknown health/locks use the
user-authorized availability assumption; missing forecasting data remains visible.
"""

from datetime import date, datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, _rates, plan_waivers

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


def _history_periods(snapshot):
    periods = {}
    for row in snapshot.get("matchup_history", []):
        period = row.get("matchup_period_id")
        if not isinstance(period, int) or period >= snapshot["period"]["matchup_period_id"]:
            continue
        teams = periods.setdefault(period, {})
        for side in ("home", "away"):
            teams[row.get(f"{side}_team_id")] = _values(row.get(f"{side}_totals"))
    return periods


def _history(snapshot, user_id, target_id):
    periods = _history_periods(snapshot)
    return [
        {
            k: (periods[period][user_id][k] - periods[period][target_id][k]) * (-1 if k == "to" else 1)
            for k in CATEGORIES
        }
        for period in sorted(periods)
        if periods[period].get(user_id) is not None and periods[period].get(target_id) is not None
    ]


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


def _schedule(player, override, remaining, now):
    schedule = player.get("schedule")
    started = {g.get("date") for g in schedule or [] if isinstance(g, dict) and g.get("started") is True}
    if "schedule" in override:
        dates = override["schedule"]
        if (
            not isinstance(dates, list)
            or len(set(dates)) != len(dates)
            or any(
                not isinstance(d, str) or date.fromisoformat(d).isoformat() != d or d not in remaining or d in started
                for d in dates
            )
        ):
            raise ValueError("schedule correction must use unique remaining unstarted game dates")
        return sorted(dates), "user correction"
    if schedule is None:
        raise ValueError("remaining schedule is unknown")
    dates = []
    for game in schedule:
        start = datetime.fromisoformat(game["start_at"].replace("Z", "+00:00"))
        if start.tzinfo is None or not isinstance(game.get("started"), bool):
            raise ValueError("game start/lock timing is unknown")
        if not game["started"] and start > now and game["date"] in remaining:
            dates.append(game["date"])
    return sorted(set(dates)), player.get("schedule_source") or "upstream schedule checked against server time"


def _remaining_lineup_slots(roster, lineup, remaining, now):
    """Started active players consume today's slot even when no future game remains."""
    daily = {day: list(lineup) for day in remaining}
    for player in roster:
        consumed = set()
        slot = player.get("lineup_slot")
        if slot not in ACTIVE_SLOTS:
            continue
        for game in player.get("schedule") or []:
            day = game.get("date")
            if day not in daily or day in consumed or slot not in daily[day]:
                continue
            try:
                start = datetime.fromisoformat(game["start_at"].replace("Z", "+00:00"))
                if game.get("started") is True or (start.tzinfo is not None and start <= now):
                    daily[day].remove(slot)
                    consumed.add(day)
            except (KeyError, ValueError, TypeError):
                continue
    return daily


def plan_snapshot_waivers(snapshot, preferences, now=None):
    """Default to automatic choices; explicit preferences narrow or correct facts."""
    now = now or datetime.now(timezone.utc)
    gaps, provenance = [], {}
    result = {
        "status": "unavailable",
        "reasons": [],
        "actions": [],
        "plan": [],
        "recommendations": [],
        "recommendation_kind": "alternatives",
        "strategy": {},
        "baseline": None,
        "projected": None,
        "remaining_adds": None,
        "assumptions": [],
        "limitations": [],
        "data_gaps": gaps,
        "provenance": provenance,
    }
    user_id, target_id = snapshot["selected_team_id"], snapshot.get("opponent_team_id")
    teams = {team["id"]: team for team in snapshot["teams"]}
    user, target = teams.get(user_id), teams.get(target_id)
    expected = {
        "league_id": snapshot["league"]["id"],
        "team_id": user_id,
        "matchup_period_id": snapshot["period"]["matchup_period_id"],
    }
    context = preferences.get("context")
    if not isinstance(context, dict) or any(context.get(k) != v for k, v in expected.items()):
        result["reasons"] = ["Preferences belong to another league, team or matchup. Refresh this matchup."]
        return result
    if not snapshot["league"].get("supported") or user is None or target is None or target_id == user_id:
        result["reasons"] = ["A supported nine-category league and an actual current opponent are required."]
        return result
    provenance["context"] = {**expected, "fetched_at": snapshot["fetched_at"]}
    provenance["snapshot_data_gaps"] = snapshot.get("data_gaps", [])
    result["baseline"] = {
        "basis": "recorded",
        "totals": user.get("totals") or {},
        "games": None,
        "minutes": None,
        "probability_five_wins": None,
    }
    settings = snapshot["league"].get("acquisition_settings", {})
    if preferences.get("user_confirmed_counts") is True:
        counts = [preferences.get(k) for k in ("weekly_add_limit", "used_adds", "available_adds")]
        provenance["counts"] = "user_confirmed matchup counts"
    elif settings.get("limit_per_scoring_period") is False and user.get("weekly_usage_complete") is not False:
        counts = [settings.get("weekly_add_limit"), user.get("weekly_used_adds"), user.get("remaining_adds")]
        provenance["counts"] = user.get("weekly_usage_source") or "ESPN complete matchup counts"
    else:
        counts = [None, None, None]
        provenance["counts"] = "unknown; daily acquisition rules are not modeled"
    fallback = preferences.get("matchup_add_limit_fallback")
    if (
        settings.get("weekly_add_limit") is None
        and _integer(fallback)
        and settings.get("limit_per_scoring_period") is False
        and user.get("weekly_usage_complete") is True
        and _integer(user.get("weekly_used_adds"))
        and preferences.get("user_confirmed_counts") is not True
    ):
        used = user["weekly_used_adds"]
        counts = [fallback, used, max(0, fallback - used)]
        provenance["counts"] = "scoped user-declared matchup cap; ESPN complete matchup usage"
        provenance["matchup_add_limit"] = {"value": fallback, "source": "user-declared fallback", **expected}
    if settings.get("limit_per_scoring_period") is True or settings.get("daily_add_limit") is not None:
        # An additional daily cap needs a day-specific ledger; do not call a weekly plan feasible.
        counts = [None, None, None]
        gaps.append(
            "Per-day acquisition limits require a daily ledger; alternatives are conditional, not a weekly plan."
        )
    if not all(_integer(n) for n in counts) or counts[1] + counts[2] > counts[0]:
        counts = [None, None, None]
        gaps.append(
            "Weekly adds remaining are unknown; enter the actual weekly cap, used and remaining counts for a plan."
        )
    rostered = {p["id"] for team in teams.values() for p in team["roster"]}
    market = {
        p["id"]: p
        for p in snapshot.get("free_agents", [])
        if p.get("eligible") is not False and p.get("availability") == "FREEAGENT" and p["id"] not in rostered
    }
    roster = {p["id"]: p for p in user["roster"]}
    candidates = preferences.get("candidate_ids", list(market))
    drops = preferences.get("droppable_ids", list(roster))
    protected = preferences.get("protected_ids", [])
    for ids, pool in ((candidates, market), (drops, roster), (protected, roster)):
        if (
            not isinstance(ids, list)
            or any(not isinstance(pid, str) or pid not in pool for pid in ids)
            or len(ids) != len(set(ids))
        ):
            result["reasons"] = ["Candidate, drop and protection choices must contain unique eligible player IDs."]
            return result
    slots = preferences.get("max_stream_slots", 2)
    if not _integer(slots) or not 1 <= slots <= 4:
        result["reasons"] = ["Maximum stream slots must be from one to four."]
        return result
    today = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    remaining = preferences.get("remaining_dates", snapshot["period"].get("remaining_dates", []))
    try:
        if (
            not isinstance(remaining, list)
            or len(remaining) > 14
            or len(set(remaining)) != len(remaining)
            or any(not isinstance(d, str) or date.fromisoformat(d).isoformat() != d for d in remaining)
        ):
            raise ValueError
        period_dates = snapshot["period"].get("dates", [])
        if "remaining_dates" in preferences and any(
            d < today or (period_dates and d not in period_dates) for d in remaining
        ):
            raise ValueError
        remaining = sorted(d for d in remaining if d >= today)
    except (TypeError, ValueError):
        result.update(status="incomplete", reasons=["Remaining dates must be unique current-matchup ISO dates."])
        return result
    if not remaining:
        gaps.append("No remaining matchup dates; future contributions and pickup timing cannot be projected.")
    lineup = [s for s in snapshot["league"].get("lineup_slots", []) if s not in ("BENCH", "IR", "IR+")]
    if not lineup or any(slot not in ACTIVE_SLOTS for slot in lineup):
        gaps.append("Active lineup rules are missing or unsupported.")
        result.update(status="incomplete", reasons=list(gaps))
        return result
    overrides = preferences.get("player_overrides", {})
    if not isinstance(overrides, dict):
        result["reasons"] = ["Player corrections must be keyed by player ID."]
        return result
    players, forecast_gaps, excluded = [], [], []
    if not user["roster"] or not target["roster"]:
        forecast_gaps.append("Complete user and opponent rosters are required for a remaining-games forecast.")
    relevant = [(p, "user") for p in user["roster"]] + [(p, "opponent") for p in target["roster"]]
    relevant += [(market[pid], "free") for pid in candidates]
    assumed = 0
    for player, owner in relevant:
        pid, name = player["id"], player["name"]
        override = overrides.get(pid, {})
        if not isinstance(override, dict):
            override = {}
        if player.get("lineup_slot") in {"IR", "IR+"}:
            provenance[f"inactive:{pid}"] = "IR player excluded; activation is not modeled"
            continue
        # V2 normalization applies the authorized available-unless-explicitly-out policy.
        # The raw ESPN injured boolean can also mean questionable; do not override health_status.
        health = player.get("health_status")
        known_out = health == "out" or str(player.get("injury_status", "")).upper() in {
            "OUT",
            "O",
            "INACTIVE",
            "SUSPENDED",
            "SUSPENSION",
            "INJURY_RESERVE",
            "RESERVE_RETIRED",
        }
        injured = override.get("injured", known_out)
        if not isinstance(injured, bool):
            forecast_gaps.append(f"{name}: availability override must be Available or Out.")
            continue
        if "injured" not in override and player.get("injured") is None and not known_out:
            assumed += 1
        try:
            # Out players need no schedule/rates for their zero remaining contribution.
            if injured:
                dates, source = [], "explicitly out"
            else:
                dates, source = _schedule(player, override, remaining, now)
            positions = [p for p in player.get("positions") or [] if p in ACTIVE_SLOTS]
            if not positions:
                raise ValueError("active lineup eligibility is missing")
            sample = player.get("current_games")
            if isinstance(sample, (int, float)) and not isinstance(sample, bool) and isfinite(sample) and sample >= 0:
                sample = int(sample) if sample == int(sample) else None
                if sample is None:
                    raise ValueError("observed season game count must be integral")
            else:
                sample = None
            # No observed game count: current averages are still useful, explicitly labeled.
            if sample is None:
                sample = 3 if player.get("current_rates") is not None else 0
                provenance[f"sample:{pid}"] = "sample count unknown; available current season averages used"
            rates, prior = player.get("current_rates"), player.get("prior_rates")
            if rates is None and prior is None and not injured:
                raise ValueError("season rates are missing")
            if injured and rates is None and prior is None:
                # Zero only because explicitly unavailable, never a missing-rate forecast.
                rates = {**dict.fromkeys(TOTALS, 0), "minutes": 0}
                sample = 3
            _rates({"id": pid, "current_rates": rates, "prior_rates": prior, "current_games": sample})
        except (TypeError, ValueError, KeyError) as error:
            (excluded if owner == "free" else forecast_gaps).append(f"{name}: {error}.")
            continue
        provenance[f"schedule:{pid}"] = source
        protection = override.get("protected")
        if pid in protected:
            protection = True
        players.append(
            {
                **player,
                "id": pid,
                "owner": owner,
                "positions": positions,
                "eligible": True,
                "locked": player.get("locked") is True or (owner == "user" and pid not in drops),
                "undroppable": player.get("undroppable") is True or player.get("droppable") is False,
                "protected": protection,
                "schedule": dates,
                "injury_status": "out" if injured else "active",
                "current_rates": rates,
                "prior_rates": prior,
                "current_games": sample,
                "season_value_unknown": player.get("current_rates") is None and player.get("prior_rates") is None,
            }
        )
    gaps.extend(forecast_gaps)
    if excluded:
        provenance["excluded_candidates"] = excluded
    history = _history(snapshot, user_id, target_id)
    periods = _history_periods(snapshot)
    complete_periods = [
        period
        for period in sorted(periods)
        if periods[period].get(user_id) is not None and periods[period].get(target_id) is not None
    ]
    previous = {}
    if complete_periods:
        period = complete_periods[-1]
        previous = {"user": periods[period][user_id], "opponent": periods[period][target_id], "period": period}

    payload = {
        "dates": remaining,
        "current_totals": user.get("totals"),
        "opponent_totals": target.get("totals"),
        "players": players,
        "lineup_slots": lineup,
        "lineup_slots_by_date": _remaining_lineup_slots(user["roster"], lineup, remaining, now),
        "opponent_lineup_slots_by_date": _remaining_lineup_slots(target["roster"], lineup, remaining, now),
        "weekly_add_limit": counts[0],
        "used_adds": counts[1],
        "available_adds": counts[2],
        "max_stream_slots": slots,
        "candidate_limit": min(1000, max(1, len(candidates))),
        "evaluation_limit": 5000,
        "selected_categories": preferences.get("selected_categories"),
        "as_of": now.isoformat(),
        "matchup_end": max(snapshot["period"].get("dates", []) or remaining, default=None),
        "prior_week_margins": history,
        "previous_comparison": previous,
        "data_gaps": forecast_gaps,
    }
    if preferences.get("uncertainty_mode") == "sensitivity":
        payload["margin_sd"] = preferences.get("margin_sd")
    planned = plan_waivers(payload)
    for key in (
        "status",
        "reasons",
        "actions",
        "plan",
        "recommendations",
        "recommendation_kind",
        "strategy",
        "remaining_adds",
        "assumptions",
        "limitations",
        "search",
        "uncertainty",
        "protected_players",
        "score_basis",
        "selected_categories",
        "safe_categories",
        "improvement_categories",
        "category_selection_source",
        "horizon",
        "recommendation_groups",
        "alternatives_explanation",
    ):
        if key in planned:
            result[key] = planned[key]
    result["baseline"] = _forecast_view(planned["baseline"]) or result["baseline"]
    result["projected"] = _forecast_view(planned["projected"])
    provenance["rates"] = planned["provenance"]
    provenance["uncertainty"] = (f"{len(history)} complete prior weekly comparisons; " if history else "") + (
        planned.get("uncertainty", {}).get("source", "unavailable") + "; uncalibrated model estimates"
    )
    provenance["availability"] = (
        f"{assumed} players assumed available unless explicitly out; user toggles take precedence"
    )
    provenance["transactions"] = (
        "Known locks/undroppable and explicit user Protect enforced; all other roster players evaluated"
    )
    if forecast_gaps:
        result["status"] = "incomplete"
        result["reasons"] = list(forecast_gaps)
        result["limitations"].append(
            "Partial roster forecast: omitted players have unknown contributions, not zero ability."
        )
    if not remaining:
        result.update(status="incomplete", reasons=[gaps[-1]])
    for action in result["actions"]:
        action["stream_roster_id"] = action["stream_slot"]
        action["stream_slot"] = drops.index(action["stream_slot"]) + 1
    return result
