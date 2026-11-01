"""Pure, bounded waiver planning with explicit (uncalibrated) uncertainty inputs.

See code_review/fantasy_optimizer.md and the integration interface for limitations.
All dates are remaining *unstarted* game dates supplied by the caller.
"""

from datetime import date
from math import erf, isfinite, sqrt
from statistics import stdev

COUNTS = ("pts", "reb", "ast", "stl", "blk", "threes", "to")
TOTALS = (*COUNTS, "fgm", "fga", "ftm", "fta")
CATEGORIES = (*COUNTS, "fg_pct", "ft_pct")
ASSUMPTIONS = [
    "Independent normal margins use historical variation where available, otherwise labeled heuristic scales.",
    "Ties do not count as wins; five outright category wins are required.",
    "Continuous normal approximation ignores discrete tie mass; numerical probabilities bounded to [1e-6, 1-1e-6].",
    "Rates and supplied schedules remain constant; unavailable dates contribute no games.",
    "Current-season rates are primary from three observed games; prior season is a small/missing-sample fallback.",
    "Availability and transaction eligibility are assumed unless explicitly reported out or locked.",
]
LIMITATIONS = [
    "Model sensitivity estimates are not calibrated probabilities or guarantees; category correlations are ignored.",
    "Bounded beam search and greedy daily lineup selection can miss globally optimal plans.",
    "Schedules and rates must be observed; unknown availability/locks use the stated availability assumption.",
    "Only modeled daily slots are enforced; unsupported daily acquisition rules keep plans conditional.",
    "No same-day game-time ordering, waiver clearance, transaction execution or automatic roster changes.",
]


def _numbers(values, keys):
    if not isinstance(values, dict) or any(
        isinstance(values.get(k), bool)
        or not isinstance(values.get(k), (int, float))
        or not isfinite(values[k])
        or values[k] < 0
        for k in keys
    ):
        raise ValueError("Missing, negative or nonfinite totals/rates")
    if values["fgm"] > values["fga"] or values["ftm"] > values["fta"]:
        raise ValueError("Made shots exceed attempts")
    return {k: float(values[k]) for k in keys}


def _integer(payload, key, default=None):
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a nonnegative integer")
    return value


def _dates(values):
    if not isinstance(values, list) or any(
        not isinstance(v, str) or date.fromisoformat(v).isoformat() != v for v in values
    ):
        raise ValueError("Dates must be ISO date lists")
    if len(values) != len(set(values)):
        raise ValueError("Duplicate game dates are unsupported")
    return sorted(values)


def _slots(value):
    if not isinstance(value, list) or not value or any(not isinstance(s, str) or not s for s in value):
        raise ValueError("Explicit nonempty lineup slots are required")
    if len(value) > 20:
        raise ValueError("At most 20 active lineup slots are supported")
    return value


def _rates(player):
    current, prior = player.get("current_rates"), player.get("prior_rates")
    games = _integer(player, "current_games", 0)
    if current is None or games == 0:
        if prior is None:
            raise ValueError(f"No sampled rates for player {player['id']}")
        return _numbers(prior, (*TOTALS, "minutes")), "prior season fallback"
    if games < 3 and prior is not None:
        return _numbers(prior, (*TOTALS, "minutes")), "prior season fallback; current sample below three games"
    if not isinstance(current, dict):
        raise ValueError("Current season rates must be a mapping")
    missing = [k for k in (*TOTALS, "minutes") if current.get(k) is None]
    repaired = dict(current)
    if missing and isinstance(prior, dict):
        # A percentage pair must share the same sample, not mix two seasons.
        for made, attempts in (("fgm", "fga"), ("ftm", "fta")):
            if made in missing or attempts in missing:
                missing = list(dict.fromkeys([*missing, made, attempts]))
        repaired.update({k: prior.get(k) for k in missing})
    rates = _numbers(repaired, (*TOTALS, "minutes"))
    source = "current season" if games >= 3 else "small current sample; no prior season"
    if missing:
        source += "; prior fallback for " + ", ".join(missing)
    return rates, source


def _values(totals):
    return {
        **{k: totals[k] for k in COUNTS},
        "fg_pct": totals["fgm"] / totals["fga"] if totals["fga"] else None,
        "ft_pct": totals["ftm"] / totals["fta"] if totals["fta"] else None,
    }


def _assessment(ours, theirs, deviations):
    left, right = _values(ours), _values(theirs)
    categories, distribution = {}, [1.0] + [0.0] * 9
    complete = True
    for key in CATEGORIES:
        margin = (
            None if left[key] is None or right[key] is None else (left[key] - right[key]) * (-1 if key == "to" else 1)
        )
        probability = None
        if margin is not None and deviations is not None:
            probability = min(1 - 1e-6, max(1e-6, (1 + erf(margin / (deviations[key] * sqrt(2)))) / 2))
            distribution = [
                distribution[n] * (1 - probability) + (distribution[n - 1] * probability if n else 0) for n in range(10)
            ]
        else:
            complete = False
        categories[key] = {
            "user": left[key],
            "opponent": right[key],
            "margin": margin,
            "state": "unknown" if margin is None else "winning" if margin > 0 else "losing" if margin < 0 else "tied",
            "win_probability": probability,
            "attainability": "unknown"
            if probability is None
            else "unlikely"
            if probability < 0.1
            else "favored"
            if probability > 0.9
            else "swing",
        }
    return categories, min(1 - 1e-6, max(1e-6, sum(distribution[5:]))) if complete else None


def _plus(totals, rates):
    return {k: totals[k] + rates[k] for k in TOTALS}


def _lineup(players, slots, ours, theirs, deviations, opponent=False, selected=None):
    """Rank marginal five-category value, then find a feasible matching by augmentation."""

    def utility(left, right):
        categories, probability = _assessment(left, right, deviations)
        if selected and not opponent:
            return sum(categories[k]["win_probability"] or 0 for k in selected) / 5
        if selected and not opponent:
            return sum(categories[k]["win_probability"] or 0 for k in selected) / 5
        return (
            probability if probability is not None else sum(c["win_probability"] or 0 for c in categories.values()) / 9
        )

    base = utility(ours, theirs)

    def priority(player):
        score = utility(_plus(ours, player["rates"]), theirs)
        gain = score - base
        return (-gain, -player["rates"]["minutes"], player["id"])

    # For opponent lineups optimize its own chance, using symmetric deviations.
    if opponent:
        ours, theirs = theirs, ours
        base = utility(ours, theirs)
    occupied = {}

    def match(player, seen):
        for index, slot in enumerate(slots):
            if index in seen or (slot != "UTIL" and slot not in player["positions"]):
                continue
            seen.add(index)
            if index not in occupied or match(occupied[index], seen):
                occupied[index] = player
                return True
        return False

    for player in sorted(players, key=priority):
        match(player, set())
    return list(occupied.values())


def _forecast(context, actions):
    ours, theirs = dict(context["ours"]), dict(context["theirs"])
    roster = set(context["roster"])
    games = {"user": 0, "opponent": 0}
    minutes = {"user": 0.0, "opponent": 0.0}
    starts = []
    for day in context["dates"]:
        for action in actions:
            if action["date"] == day:
                roster.remove(action["drop_id"])
                roster.add(action["add_id"])
        available = [p for p in context["players"].values() if day in p["schedule"] and day not in p["unavailable"]]
        slots = context["daily_slots"].get(day, context["slots"])
        user = _lineup(
            [p for p in available if p["id"] in roster],
            slots,
            ours,
            theirs,
            context["sd"],
            selected=context.get("scored_categories"),
        )
        opponent = _lineup(
            [p for p in available if p["owner"] == "opponent"],
            context["opponent_daily_slots"].get(day, slots),
            ours,
            theirs,
            context["sd"],
            True,
        )
        if "opponent_starts" in context:
            opponent = [context["players"][s["player_id"]] for s in context["opponent_starts"] if s["date"] == day]
        for owner, lineup in (("user", user), ("opponent", opponent)):
            for player in lineup:
                if owner == "user":
                    ours = _plus(ours, player["rates"])
                else:
                    theirs = _plus(theirs, player["rates"])
                games[owner] += 1
                minutes[owner] += player["rates"]["minutes"]
                starts.append({"date": day, "owner": owner, "player_id": player["id"]})
    categories, probability = _assessment(ours, theirs, context["sd"])
    return {
        "user_totals": ours,
        "opponent_totals": theirs,
        "categories": categories,
        "win_at_least_five_probability": probability,
        "games": games,
        "minutes": minutes,
        "starts": starts,
    }


def _context(payload):
    dates = _dates(payload["dates"])
    if len(dates) > 14:
        raise ValueError("At most fourteen remaining dates supported")
    slots = _slots(payload["lineup_slots"])
    daily = payload.get("lineup_slots_by_date", {})
    if not isinstance(daily, dict) or any(day not in dates for day in daily):
        raise ValueError("Daily lineup overrides must use remaining dates")
    daily = {day: _slots(value) if value != [] else [] for day, value in daily.items()}
    opponent_daily = payload.get("opponent_lineup_slots_by_date", {})
    if not isinstance(opponent_daily, dict) or any(day not in dates for day in opponent_daily):
        raise ValueError("Opponent daily lineup overrides must use remaining dates")
    opponent_daily = {day: _slots(value) if value != [] else [] for day, value in opponent_daily.items()}
    players, provenance = {}, {}
    seen = set()
    if not isinstance(payload["players"], list) or len(payload["players"]) > 1000:
        raise ValueError("At most 1000 normalized players supported")
    for raw in payload["players"]:
        pid = raw["id"]
        if not isinstance(pid, str) or not pid or pid in seen:
            raise ValueError("Player ids must be unique nonempty strings")
        seen.add(pid)
        owner = raw["owner"]
        if owner not in ("user", "opponent", "other", "free"):
            raise ValueError("Unknown roster ownership")
        if owner == "other" or (owner == "free" and not raw.get("eligible", True)):
            continue
        if not isinstance(raw.get("eligible", True), bool):
            raise ValueError("Unknown player eligibility")
        positions = raw["positions"]
        if not isinstance(positions, list) or not positions or any(not isinstance(p, str) or not p for p in positions):
            raise ValueError("Player positions are required")
        rates, provenance[pid] = _rates(raw)
        schedule = _dates(raw["schedule"])
        unavailable = _dates(raw.get("unavailable_dates", []))
        if str(raw.get("injury_status") or "").lower() in ("out", "inactive"):
            unavailable = schedule
        players[pid] = {**raw, "rates": rates, "schedule": schedule, "unavailable": unavailable}
        players[pid]["protection"] = _protection(players[pid])
    if not any(p["owner"] == "user" for p in players.values()) and not payload.get("data_gaps"):
        raise ValueError("User roster is required")
    ours = _numbers(payload["current_totals"], TOTALS)
    theirs = _numbers(payload["opponent_totals"], TOTALS)
    sd = payload.get("margin_sd")
    history = payload.get("prior_week_margins") or []
    uncertainty = "sensitivity" if sd is not None else "model_estimate"
    if sd is None:
        # Floors prevent zero history variance from implying impossible certainty.
        sd = {}
        for key in CATEGORIES:
            floor = 0.025 if key.endswith("pct") else max(2, (ours[key] + theirs[key]) * 0.12)
            if len(history) >= 3:
                sd[key] = max(floor, stdev(row[key] for row in history))
                uncertainty = "history"
            else:
                future = sum(
                    p["rates"].get(key, 0) * len(set(p["schedule"]) & set(dates))
                    for p in players.values()
                    if p["owner"] in ("user", "opponent")
                )
                sd[key] = floor if key.endswith("pct") else max(floor, future * 0.12)
    if not isinstance(sd, dict) or any(
        isinstance(sd.get(k), bool) or not isinstance(sd.get(k), (int, float)) or not isfinite(sd[k]) or sd[k] <= 0
        for k in CATEGORIES
    ):
        raise ValueError("Every category needs a positive finite margin standard deviation")
    counts = [payload.get(k) for k in ("weekly_add_limit", "used_adds", "available_adds")]
    if any(v is None for v in counts):
        budget = None
    else:
        cap, used, available = (_integer(payload, k) for k in ("weekly_add_limit", "used_adds", "available_adds"))
        if used + available > cap:
            raise ValueError("Adds used plus remaining exceed the weekly cap")
        budget = min(available, max(0, cap - used))
    return {
        "dates": dates,
        "slots": slots,
        "daily_slots": daily,
        "opponent_daily_slots": opponent_daily,
        "ours": ours,
        "theirs": theirs,
        "players": players,
        "roster": {pid for pid, p in players.items() if p["owner"] == "user"},
        "sd": sd,
        "budget": budget,
        "history": history,
        "previous_comparison": payload.get("previous_comparison", {}),
        "uncertainty": {"source": uncertainty, "calibrated": False, "margin_sd": sd, "history_samples": len(history)},
        "provenance": provenance,
        "stream_slots": min(4, _integer(payload, "max_stream_slots", 4)),
        "beam": min(32, max(1, _integer(payload, "beam_width", 8))),
        "candidate_limit": min(1000, max(1, _integer(payload, "candidate_limit", 1000))),
        "evaluation_limit": min(20000, max(1, _integer(payload, "evaluation_limit", 5000))),
    }


def _score(forecast, context):
    # Fixed selected five for the whole search: saturated safe wins add almost no
    # marginal value, while close projected margins have the largest sensitivity.
    return sum(forecast["categories"][k]["win_probability"] or 0 for k in context["scored_categories"]) / 5


def _protection(player):
    """Only legal constraints and explicit user decisions prohibit evaluation."""
    if player.get("undroppable") is True or player.get("droppable") is False:
        return "ESPN undroppable"
    if player.get("protected") is True:
        return "User protected"
    return None


def _season_value(player):
    r = player["rates"]
    # Nine-category per-game replacement proxy; percentages use volume impact.
    return (
        r["pts"] / 25
        + r["reb"] / 10
        + r["ast"] / 8
        + r["stl"] / 1.5
        + r["blk"] / 1.5
        + r["threes"] / 3
        - r["to"] / 4
        + (r["fgm"] - 0.47 * r["fga"]) / 3
        + (r["ftm"] - 0.78 * r["fta"]) / 2
    )


def _season_cost(drop, add):
    # Sustained value loss matters beyond this week. Lower sample/role stability
    # discounts an attractive new player rather than treating one hot game as truth.
    add_stability = 0.6 + 0.4 * min(1, add.get("current_games", 0) / 15)
    if add["rates"]["minutes"] < 18:
        add_stability *= 0.8
    loss = max(0, _season_value(drop) - _season_value(add) * add_stability)
    return loss * 0.035


def _strategy(forecast, context):
    strategy = {}
    for key, category in forecast["categories"].items():
        p = category["win_probability"]
        margin = category["margin"]
        historical = context["history"][-1].get(key) if context["history"] else None
        classification = (
            "unknown"
            if p is None
            else "favored"
            if p >= 0.8
            else "punt"
            if p < 0.1
            else "reachable"
            if p < 0.4
            else "swing"
        )
        explanation = {
            "unknown": "Shooting attempts or projection inputs are missing.",
            "favored": "Projected cushion; protect this category without paying heavily for extra volume.",
            "punt": "Projected gap is large relative to modeled variation; a normal pickup is unlikely to close it.",
            "reachable": "Trailing, but the projected gap is within reach of a targeted net upgrade.",
            "swing": "Close projected category; small net changes can alter the matchup.",
        }[classification]
        if historical is not None and margin is not None:
            explanation += (
                " Latest complete prior-week comparison favored us; actuals plus remaining games drive this forecast."
                if historical > 0
                else " Latest complete prior-week comparison trailed; actuals plus remaining games drive this forecast."
            )
        strategy[key] = {
            "classification": classification,
            "explanation": explanation,
            "projected_margin": margin,
            "historical_margin": historical,
            "target_priority": None if p is None else 4 * p * (1 - p),
            "estimate": p,
            "current_user": _values(context["ours"])[key],
            "current_opponent": _values(context["theirs"])[key],
            "projected_user": category["user"],
            "projected_opponent": category["opponent"],
            "previous_period_id": context["previous_comparison"].get("period"),
            "previous_user": context["previous_comparison"].get("user", {}).get(key),
            "previous_opponent": context["previous_comparison"].get("opponent", {}).get(key),
            "lower_is_better": key == "to",
        }
    return strategy


def _calculation(context, before, after, action):
    add, drop = (context["players"][action[k]] for k in ("add_id", "drop_id"))

    def starts(forecast, pid):
        return sum(
            s["owner"] == "user" and s["player_id"] == pid and s["date"] >= action["date"] for s in forecast["starts"]
        )

    added, lost = starts(after, add["id"]), starts(before, drop["id"])
    result = {}
    for k in CATEGORIES:
        row = {
            "add_starts": added,
            "drop_starts": lost,
            "add_eligible_games": sum(
                d >= action["date"] and d in context["dates"] and d not in add["unavailable"] for d in add["schedule"]
            ),
            "drop_eligible_games": sum(
                d >= action["date"] and d in context["dates"] and d not in drop["unavailable"] for d in drop["schedule"]
            ),
            "lower_is_better": k == "to",
        }
        if k in COUNTS:
            net = after["user_totals"][k] - before["user_totals"][k]
            row.update(
                add_rate=add["rates"][k],
                drop_rate=drop["rates"][k],
                added_total=add["rates"][k] * added,
                lost_total=drop["rates"][k] * lost,
                net_total=net,
                lineup_other_net=net - add["rates"][k] * added + drop["rates"][k] * lost,
            )
        else:
            made, attempts = ("fgm", "fga") if k == "fg_pct" else ("ftm", "fta")
            left, right = before["categories"][k]["user"], after["categories"][k]["user"]
            row.update(
                add_rate=_values(add["rates"])[k],
                drop_rate=_values(drop["rates"])[k],
                added_total=None,
                lost_total=None,
                lineup_other_net=None,
                net_total=None if left is None or right is None else right - left,
                weighted={
                    "before_makes": before["user_totals"][made],
                    "before_attempts": before["user_totals"][attempts],
                    "after_makes": after["user_totals"][made],
                    "after_attempts": after["user_totals"][attempts],
                    "add_makes_rate": add["rates"][made],
                    "add_attempts_rate": add["rates"][attempts],
                    "drop_makes_rate": drop["rates"][made],
                    "drop_attempts_rate": drop["rates"][attempts],
                },
            )
        result[k] = row
    return result


def plan_waivers(payload):
    """Rank net upgrades from normalized primitives, retaining useful partial comparisons.

    No input is mutated. Transactions take effect before all games on their given
    date. Adapters must exclude dates on which acquisition cannot yet take effect.
    """
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
        "provenance": {},
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        "data_gaps": payload.get("data_gaps", []) if isinstance(payload, dict) else [],
        "search": {"evaluations": 0, "evaluation_limit_reached": False},
    }
    try:
        if not isinstance(result["data_gaps"], list) or any(not isinstance(g, str) for g in result["data_gaps"]):
            raise ValueError("data_gaps must be a string list")
        context = _context(payload)
        baseline = _forecast(context, [])
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as error:
        result["reasons"] = [f"Incomplete or invalid optimizer inputs: {error}"]
        return result
    result.update(
        baseline=baseline, projected=baseline, remaining_adds=context["budget"], provenance=context["provenance"]
    )
    result["uncertainty"] = context["uncertainty"]
    result["strategy"] = _strategy(baseline, context)
    requested = payload.get("selected_categories")
    if requested is not None and (
        not isinstance(requested, list)
        or len(requested) != 5
        or any(not isinstance(k, str) or k not in CATEGORIES for k in requested)
        or len(set(requested)) != 5
    ):
        result.update(status="unavailable", reasons=["Select exactly five unique supported category keys."])
        return result

    def selection_priority(k):
        category = baseline["categories"][k]
        p = category["win_probability"] or 0
        # Reachability evidence from observed FA rates and remaining schedules.
        # This is selection guidance only: every actual pair still pays the full
        # dropped contribution and lineup cost in the forecast below.
        upside = 0
        if k in COUNTS and category["margin"] is not None:
            drops = [
                v
                for v in context["players"].values()
                if v["owner"] == "user" and not v["protection"] and not v.get("locked")
            ]
            for free in context["players"].values():
                if free["owner"] != "free" or free.get("locked"):
                    continue
                contribution = free["rates"][k] * len(
                    (set(free["schedule"]) - set(free["unavailable"])) & set(context["dates"])
                )
                for drop in drops:
                    loss = drop["rates"][k] * len(
                        (set(drop["schedule"]) - set(drop["unavailable"])) & set(context["dates"])
                    )
                    upside = max(upside, (contribution - loss) * (-1 if k == "to" else 1))
            possible = (1 + erf((category["margin"] + upside) / (context["sd"][k] * sqrt(2)))) / 2
            p += max(0, possible - p) * 0.5
        return (-p, CATEGORIES.index(k))

    selected = requested or sorted(CATEGORIES, key=selection_priority)[:5]
    result["selected_categories"] = selected
    result["category_selection_source"] = "user" if requested else "projected contest with historical variation"
    result["safe_categories"] = [k for k in selected if result["strategy"][k]["classification"] == "favored"]
    result["improvement_categories"] = [k for k in selected if k not in result["safe_categories"]]
    for k, category in result["strategy"].items():
        category.update(
            selected=k in selected,
            safe_win=k in result["safe_categories"],
            improvement_target=k in result["improvement_categories"],
        )
    result["horizon"] = {
        "basis": "prospective remaining matchup totals; recorded actuals are retained",
        "as_of": payload.get("as_of"),
        "matchup_end": payload.get("matchup_end"),
        "remaining_dates": context["dates"],
    }
    result["recommendations"] = []
    result["recommendation_kind"] = "alternatives"
    result["plan"] = []
    result["protected_players"] = {
        pid: p["protection"] for pid, p in context["players"].items() if p["owner"] == "user" and p["protection"]
    }
    if result["data_gaps"]:
        baseline["win_at_least_five_probability"] = None
        for category in baseline["categories"].values():
            category.update(win_probability=None, attainability="unknown")
        for category in result["strategy"].values():
            category.update(estimate=None, target_priority=None)
            category["explanation"] += " Projection is partial because roster inputs are missing."
        result.update(status="incomplete", reasons=["Forecast is partial; resolve the listed data gaps."])
        return result
    partial = baseline["win_at_least_five_probability"] is None
    context["scored_categories"] = [k for k in selected if baseline["categories"][k]["win_probability"] is not None]
    context["partial"] = partial
    context["opponent_starts"] = [s for s in baseline["starts"] if s["owner"] == "opponent"]
    baseline = _forecast(context, [])
    result.update(baseline=baseline, projected=baseline)
    result["strategy"] = _strategy(baseline, context)
    result["safe_categories"] = [k for k in selected if result["strategy"][k]["classification"] == "favored"]
    result["improvement_categories"] = [k for k in selected if k not in result["safe_categories"]]
    for k, category in result["strategy"].items():
        category.update(
            selected=k in selected,
            safe_win=k in result["safe_categories"],
            improvement_target=k in result["improvement_categories"],
        )
        if k in result["safe_categories"] or k not in selected:
            category["target_priority"] = 0
    result["score_basis"] = "known_selected_category_estimates" if partial else "selected_five_category_estimates"
    result["status"] = "ready" if context["budget"] is not None and context["dates"] and not partial else "incomplete"
    if partial:
        result["reasons"].append("Missing shooting attempts: rank known categories without estimating five-win odds.")
    if not context["dates"]:
        result["reasons"].append("No remaining matchup dates; no future games or moves projected.")
        return result
    if context["budget"] is None:
        result["reasons"].append(
            "Weekly adds remaining are unknown. Alternatives assume one add; confirm counts for a plan."
        )
    # Unknown budget still supports conditional single-move alternatives, never a sequential plan.
    search_budget = context["budget"] if context["budget"] is not None else 1
    alternatives = {}
    evaluated_drops = set()
    alternatives_search_complete = False
    # Each state retains its chronological transaction ledger and slot ancestry.
    initial = {pid: pid for pid in context["roster"]}
    beam = [(baseline, [], initial, frozenset(), frozenset())]
    best = beam[0]

    def rank(state):
        forecast, actions = state[:2]
        return (
            _score(forecast, context) - sum(a.get("season_cost", 0) for a in actions),
            -len(actions),
            forecast["minutes"]["user"],
        )

    for depth in range(min(search_budget, len(context["dates"]) * context["stream_slots"])):
        expanded = []
        for forecast, actions, ownership, acquired, stream_roots in beam:
            if result["search"]["evaluation_limit_reached"]:
                break
            for day in context["dates"]:
                if result["search"]["evaluation_limit_reached"]:
                    break
                if actions and day < actions[-1]["date"]:
                    continue
                candidates = []
                for pid, player in context["players"].items():
                    if player["owner"] != "free" or pid in acquired or player.get("locked", False):
                        continue
                    if not any(
                        d >= day and d in context["dates"] and d not in player["unavailable"]
                        for d in player["schedule"]
                    ):
                        continue
                    candidates.append(pid)

                # Deterministic shortlist by per-player marginal five-category value.
                def candidate_rank(pid):
                    rates = context["players"][pid]["rates"]
                    cats, probability = _assessment(
                        _plus(forecast["user_totals"], rates), forecast["opponent_totals"], context["sd"]
                    )
                    value = _score({"categories": cats, "win_at_least_five_probability": probability}, context)
                    return (-value, -rates["minutes"], pid)

                candidates.sort(key=candidate_rank)
                legal_drops = [
                    (pid, root)
                    for pid, root in sorted(
                        ownership.items(), key=lambda item: (_season_value(context["players"][item[0]]), item[0])
                    )
                    if not context["players"][pid].get("locked")
                    and not context["players"][pid]["protection"]
                    and (root in stream_roots or len(stream_roots) < context["stream_slots"])
                ]
                # Round-robin all legal roster drops before considering another
                # candidate, so a large pool cannot spend the bound on one drop.
                pairs = (
                    (add_id, drop_id, root)
                    for add_id in candidates[: context["candidate_limit"]]
                    for drop_id, root in legal_drops
                )
                for add_id, drop_id, root in pairs:
                    if result["search"]["evaluations"] >= context["evaluation_limit"]:
                        result["search"]["evaluation_limit_reached"] = True
                        break
                    result["search"]["evaluations"] += 1
                    evaluated_drops.add(drop_id)
                    action = {"date": day, "add_id": add_id, "drop_id": drop_id, "stream_slot": root}
                    next_actions = [*actions, action]
                    projected = _forecast(context, next_actions)
                    if not partial and projected["win_at_least_five_probability"] is None:
                        continue
                    gain = _score(projected, context) - _score(forecast, context)
                    cost = _season_cost(context["players"][drop_id], context["players"][add_id])
                    if gain - cost <= 1e-5:
                        continue
                    action["season_cost"] = cost
                    action["season_value"] = {
                        "drop": _season_value(context["players"][drop_id]),
                        "add": _season_value(context["players"][add_id]),
                        "basis": "nine-category per-game replacement proxy; heuristic, not a season rank",
                    }
                    action["net_score"] = gain - cost
                    action["probability_gain"] = (
                        None
                        if partial
                        else projected["win_at_least_five_probability"] - forecast["win_at_least_five_probability"]
                    )
                    action["estimated_win_gain"] = gain
                    action["gains"] = {k: projected["user_totals"][k] - forecast["user_totals"][k] for k in TOTALS}
                    action["category_probability_gains"] = {
                        k: (
                            projected["categories"][k]["win_probability"] - forecast["categories"][k]["win_probability"]
                        )
                        if projected["categories"][k]["win_probability"] is not None
                        and forecast["categories"][k]["win_probability"] is not None
                        else None
                        for k in CATEGORIES
                    }
                    action["category_impacts"] = {
                        k: {
                            "before": forecast["categories"][k]["user"],
                            "after": projected["categories"][k]["user"],
                            "margin_before": forecast["categories"][k]["margin"],
                            "margin_after": projected["categories"][k]["margin"],
                            "estimate_gain": action["category_probability_gains"][k],
                            "flips_projection": forecast["categories"][k]["state"] != "winning"
                            and projected["categories"][k]["state"] == "winning",
                        }
                        for k in CATEGORIES
                    }
                    action["calculation"] = _calculation(context, forecast, projected, action)
                    action["long_term_tradeoff"] = {
                        "cost": cost,
                        "draft_round": context["players"][drop_id].get("draft_round"),
                        "season_rank": context["players"][drop_id].get("season_rank"),
                        "explanation": (
                            "Heuristic sustained per-game value cost; core/draft metadata never prohibits a legal drop."
                        ),
                    }
                    action["games_gain"] = projected["games"]["user"] - forecast["games"]["user"]
                    action["minutes_gain"] = projected["minutes"]["user"] - forecast["minutes"]["user"]
                    action["target_categories"] = sorted(
                        (
                            k
                            for k in result["improvement_categories"]
                            if (action["category_probability_gains"][k] or 0) > 0.005
                            and result["strategy"][k]["classification"] in ("swing", "reachable")
                        ),
                        key=lambda k: -action["category_probability_gains"][k],
                    )
                    action["rationale"] = (
                        "Net improvement after the dropped player's remaining games and season value; "
                        + (
                            "targets " + ", ".join(action["target_categories"])
                            if action["target_categories"]
                            else "reinforces the path to five category wins"
                        )
                        + ". Estimates assume stable minutes and availability."
                    )
                    pair = (add_id, drop_id)
                    if depth == 0 and (
                        pair not in alternatives or action["net_score"] > alternatives[pair]["net_score"]
                    ):
                        alternatives[pair] = dict(action)
                    next_ownership = {pid: slot for pid, slot in ownership.items() if pid != drop_id}
                    next_ownership[add_id] = root
                    expanded.append(
                        (projected, next_actions, next_ownership, acquired | {add_id}, stream_roots | {root})
                    )
        if depth == 0:
            alternatives_search_complete = not result["search"]["evaluation_limit_reached"]
        if not expanded:
            break
        expanded.sort(key=rank, reverse=True)
        # Equivalent roster/used-add/date states cannot improve by ledger reordering.
        unique = {}
        for state in expanded:
            signature = (
                tuple(sorted(state[2].items())),
                state[3],
                state[4],
                state[1][-1]["date"],
                tuple((a["date"], a["add_id"], a["drop_id"]) for a in state[1]),
            )
            unique.setdefault(signature, state)
        beam = list(unique.values())[: context["beam"]]
        if rank(beam[0]) > rank(best):
            best = beam[0]
    if result["search"]["evaluation_limit_reached"]:
        result["limitations"].append(
            "Evaluation budget reached; these are the best explored options, not a global optimum."
        )
    result["recommendations"] = sorted(
        alternatives.values(), key=lambda a: (-a["net_score"], a["add_id"], a["drop_id"])
    )
    for index, option in enumerate(result["recommendations"], 1):
        option["rank"] = index
        option["conditional_on_one_add"] = context["budget"] is None
    result["recommendation_groups"] = {
        pid: [r["rank"] for r in result["recommendations"] if r["drop_id"] == pid] for pid in sorted(context["roster"])
    }
    result["alternatives_explanation"] = (
        "Ranked alternatives may share a drop; they cannot all be combined. "
        "Each pair retains its best explored date. Only plan is a sequential acquisition ledger."
    )
    result["search"].update(
        candidate_limit=context["candidate_limit"],
        evaluation_limit=context["evaluation_limit"],
        candidate_pool=sum(p["owner"] == "free" for p in context["players"].values()),
        legal_drop_ids=sorted(
            pid
            for pid in context["roster"]
            if not context["players"][pid].get("locked") and not context["players"][pid]["protection"]
        ),
        alternatives_returned=len(result["recommendations"]),
        evaluated_drop_ids=sorted(evaluated_drops),
        alternatives_complete=alternatives_search_complete
        and sum(p["owner"] == "free" for p in context["players"].values()) <= context["candidate_limit"],
        plan_search="bounded beam; not a global optimum",
    )
    for key, category in result["strategy"].items():
        impacts = [
            option["category_impacts"][key]
            for option in result["recommendations"]
            if option["category_impacts"][key]["margin_after"] is not None
        ]
        best_margin = max((impact["margin_after"] for impact in impacts), default=category["projected_margin"])
        category["best_pickup_margin"] = best_margin
        category["can_flip_with_one_move"] = (
            category["projected_margin"] is not None
            and category["projected_margin"] <= 0
            and best_margin is not None
            and best_margin > 0
        )
        category["best_estimate_gain"] = max((impact["estimate_gain"] or 0 for impact in impacts), default=0)
        category["recommended_target"] = (
            category["improvement_target"]
            and category["classification"] in ("swing", "reachable")
            and category["best_estimate_gain"] > 0.005
        )
        if category["can_flip_with_one_move"]:
            category["explanation"] += " An explored net add/drop alternative flips the projected lead."
        elif category["classification"] == "reachable":
            category["explanation"] += (
                " Explored pickups do not flip the projected lead; reachability reflects uncertainty."
            )
    if context["budget"] is not None and not partial:
        result.update(projected=best[0], actions=best[1], plan=best[1], remaining_adds=context["budget"] - len(best[1]))
    return result
