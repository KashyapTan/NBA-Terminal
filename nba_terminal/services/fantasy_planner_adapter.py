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
        "actual_primitives": forecast["actual_primitives"],
        "remaining_primitives": forecast["remaining_primitives"],
        "starts": forecast["starts"],
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
        "evaluation_state": "required_inputs_unknown",
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
    if preferences.get("user_confirmed_counts") is True and "counts_snapshot_at" in preferences:
        if preferences["counts_snapshot_at"] != snapshot["fetched_at"]:
            result["reasons"] = [
                "Manual acquisition counts were confirmed for older data. Verify current counts and reconfirm."
            ]
            return result
        provenance["counts_confirmation"] = {
            "snapshot_fetched_at": snapshot["fetched_at"],
            "evaluated_at": now.isoformat(),
        }
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
    fallback = preferences.get("matchup_add_limit_fallback")
    per_day = settings.get("limit_per_scoring_period")
    # A scoped matchup declaration establishes cap units independently of the
    # provider's optional per-scoring-period flag. Do not default that flag False.
    cap = settings.get("weekly_add_limit") if per_day is False else None
    cap_source = settings.get("cap_source") or "legacy ESPN settings"
    if cap is None and cap_source == "league_fallback_7":
        cap = settings.get("matchup_add_limit", settings.get("weekly_add_limit"))
    if not _integer(cap) and _integer(fallback):
        cap, cap_source = fallback, "scoped user-declared matchup cap"
    used = user.get("weekly_used_adds") if user.get("weekly_usage_complete") is not False else None
    remaining = max(0, cap - used) if _integer(cap) and _integer(used) else None
    if preferences.get("user_confirmed_counts") is True:
        counts = [preferences.get(k) for k in ("weekly_add_limit", "used_adds", "available_adds")]
        cap, used, remaining = counts
        cap_source = "user_confirmed matchup cap"
        provenance["counts"] = "user_confirmed matchup counts"
    else:
        supplied_remaining = user.get("remaining_adds")
        counts = [cap, used, supplied_remaining if _integer(supplied_remaining) else remaining]
        provenance["counts"] = (
            f"{cap_source}; " + (user.get("weekly_usage_source") or "ESPN complete matchup usage")
            if _integer(used)
            else f"{cap_source}; current matchup usage unknown"
        )
    provenance["acquisition_cap"] = {"value": cap, "source": cap_source}
    remaining = counts[2]
    provenance["reported_acquisition_limit"] = {
        "value": settings.get("reported_add_limit"),
        "scope": settings.get("reported_limit_scope", "unknown"),
        "source": "ESPN acquisition settings; not automatically a matchup cap",
    }
    if cap_source == "scoped user-declared matchup cap":
        provenance["matchup_add_limit"] = {"value": cap, "source": "user-declared fallback", **expected}
    result["acquisition_budget"] = {
        "matchup_cap": cap if _integer(cap) else None,
        "used": used if _integer(used) else None,
        "remaining": remaining if _integer(remaining) else None,
        "cap_source": cap_source,
        "usage_source": "user_confirmed"
        if preferences.get("user_confirmed_counts") is True
        else user.get("weekly_usage_source"),
        "daily_limit": settings.get("daily_add_limit"),
        "daily_applicability": "daily" if per_day is True else "matchup" if per_day is False else "unreported",
    }
    provenance["daily_acquisition_rule"] = {
        "limit_per_scoring_period": per_day,
        "source": "ESPN acquisition settings" if isinstance(per_day, bool) else "not supplied by ESPN",
        "modeled_scope": "supplied matchup cap; explicit daily limits require a daily ledger",
    }
    supplied_counts = list(counts)
    if per_day is True or settings.get("daily_add_limit") is not None:
        counts = [None, None, None]
        gaps.append(
            "Per-day acquisition limits require a daily ledger; alternatives are conditional, not a weekly plan."
        )
    if not all(_integer(n) for n in counts) or counts[1] + counts[2] > counts[0]:
        if preferences.get("user_confirmed_counts") is True:
            for label, value in zip(("cap", "used", "remaining"), supplied_counts):
                if not _integer(value):
                    gaps.append(f"User-confirmed matchup acquisitions {label}: enter a nonnegative whole count.")
        else:
            if not _integer(cap):
                gaps.append(
                    "Matchup acquisition cap unknown: ESPN cap scope is unavailable; no scoped user cap was supplied."
                )
            if not _integer(used):
                gaps.append(
                    "Current matchup acquisitions used unknown: ESPN's current-matchup counter is unavailable "
                    "or invalid. Season/day totals and yesterday's count are not substitutes."
                )
        if all(_integer(n) for n in counts) and counts[1] + counts[2] > counts[0]:
            gaps.append("Acquisition counts conflict: used plus remaining exceeds the matchup cap.")
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
    candidate_capacity = max(0, 1000 - len(user["roster"]) - len(target["roster"]))
    qualified_candidates = selected_candidates = 0
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
        inactive = player.get("active") is False or player.get("lineup_slot") in {"IR", "IR+"}
        if inactive:
            provenance[f"inactive:{pid}"] = "IR/inactive player retained as legal drop; activation is not modeled"
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
            # Out/inactive players need no future schedule; rates still establish drop value.
            if injured or inactive:
                dates, source = [], "explicitly out or inactive; zero usable starts"
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
            rates, prior = player.get("season_rates", player.get("current_rates")), player.get("prior_rates")
            if player.get("season_rates") is not None:
                # season_rates is the data adapter's chosen same-sample rate basis.
                prior = None
                provenance[f"rate_basis:{pid}"] = player.get("rate_provenance") or "normalized season_rates"
            if rates is None and prior is None:
                raise ValueError("season rates are missing; unknown drop value cannot be treated as zero")
            _rates(
                {
                    "id": pid,
                    "current_rates": rates,
                    "prior_rates": prior,
                    "current_games": sample,
                    "season_rates": player.get("season_rates"),
                    "rate_provenance": player.get("rate_provenance"),
                }
            )
        except (TypeError, ValueError, KeyError) as error:
            (excluded if owner == "free" else forecast_gaps).append(f"{name}: {error}.")
            continue
        if owner == "free":
            qualified_candidates += 1
            if selected_candidates >= candidate_capacity:
                excluded.append(f"{name}: optimizer candidate resource bound.")
                continue
            selected_candidates += 1
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
                "active": not inactive,
                "core_protection_override": override.get("core_protection_override") is True,
                "schedule": dates,
                "injury_status": "out" if injured else "active",
                "current_rates": rates,
                "rate_basis_source": (
                    "normalized season_rates; " + str(player.get("rate_provenance") or "source unknown")
                    if player.get("season_rates") is not None
                    else None
                ),
                "prior_rates": prior,
                "current_games": sample,
                "season_value_unknown": all(
                    player.get(k) is None for k in ("current_rates", "prior_rates", "season_rates")
                ),
            }
        )
    if not snapshot.get("free_agents") and snapshot.get("market_complete") is not True:
        forecast_gaps.append(
            "Free-agent market evidence is unavailable or unverified; an empty response is not a no-benefit evaluation."
        )
    elif candidates and qualified_candidates == 0 and excluded:
        forecast_gaps.append(
            "No selected eligible free agent has a usable rate/schedule sample; pickup benefit could not be evaluated."
        )
    gaps.extend(forecast_gaps)
    if excluded:
        provenance["excluded_candidates"] = excluded
    result["candidate_coverage"] = {
        "requested": len(candidates),
        "qualified": qualified_candidates,
        "selected": selected_candidates,
        "limit": candidate_capacity,
        "resource_bound_reached": qualified_candidates > selected_candidates,
        "excluded_count": len(excluded),
        "scope": "normalized candidates; separate from raw market enumeration",
    }
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

    projection_metadata = dict(snapshot.get("projection_metadata") or {})
    # Retain the explicit normalized fact even when an older caller omitted metadata.
    if snapshot.get("period", {}).get("calendar_verified") is False:
        projection_metadata["matchup_calendar"] = {
            "complete": False,
            "source": "espn_scoring_date_anchors",
            "reason": "ESPN scoring-date anchor unavailable or conflicting; future matchup calendar unverified",
        }

    def banked(team, side):
        actuals = team.get("actuals")
        if actuals is None:
            provenance[f"actuals:{side}"] = "legacy official ESPN totals; no optional actuals attestation supplied"
            return team.get("totals")
        complete = actuals.get("forecast_complete") is True
        projection_metadata[f"actuals:{side}"] = {
            "complete": complete,
            "source": actuals.get("forecast_source"),
            "reason": "Selected banked actuals are incomplete" if not complete else None,
        }
        provenance[f"actuals:{side}"] = actuals
        # Preserve official totals in snapshot and provenance; never silently replace them.
        return actuals.get("forecast_totals") if complete else team.get("totals")

    payload = {
        "dates": remaining,
        "current_totals": banked(user, "user"),
        "opponent_totals": banked(target, "opponent"),
        "projection_metadata": projection_metadata,
        "market_complete": snapshot.get("market_complete"),
        "matchup_finalized": snapshot["period"].get("finalized") is True,
        "allow_core_drops": preferences.get("allow_core_drops") is True,
        "aggressive_cushion_sacrifice": preferences.get("aggressive_cushion_sacrifice") is True,
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
    gaps.extend(g for g in planned.get("data_gaps", []) if g not in gaps)
    for key in (
        "status",
        "evaluation_state",
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
        "protection_policy",
        "recommended_plan",
        "primary_recommendation_kind",
        "projection_metadata",
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
    if per_day is None:
        result["limitations"].append(
            "ESPN did not report daily acquisition applicability; this plan models the supplied matchup cap only. "
            "ESPN remains authoritative for additional transaction restrictions."
        )
    if qualified_candidates > selected_candidates:
        result["limitations"].append(
            f"Optimizer resource bound selected {selected_candidates} of {qualified_candidates} qualified candidates; "
            "raw market enumeration is retained separately."
        )
        result.setdefault("search", {}).update(candidate_truncated=True, alternatives_complete=False)
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
        "ESPN locks/undroppable, user Protect and default core guard enforced; "
        "core override never bypasses official locks"
    )
    if forecast_gaps:
        result["status"] = "incomplete"
        result["evaluation_state"] = "required_inputs_unknown"
        result["reasons"] = list(forecast_gaps)
        result["limitations"].append(
            "Partial roster forecast: omitted players have unknown contributions, not zero ability."
        )
    if not remaining:
        result.update(status="incomplete", evaluation_state="required_inputs_unknown", reasons=[gaps[-1]])
    for action in result["actions"]:
        action["stream_roster_id"] = action["stream_slot"]
        action["stream_slot"] = drops.index(action["stream_slot"]) + 1
    return result
