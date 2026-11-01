"""Pure, bounded waiver planning with explicit (uncalibrated) uncertainty inputs.

See code_review/fantasy_optimizer.md and the integration interface for limitations.
All dates are remaining *unstarted* game dates supplied by the caller.
"""

from datetime import date
from itertools import combinations
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
    "Available current-season rates are primary, including small samples; missing fields use labeled prior fallback.",
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
    if player.get("season_rates") is not None:
        source = "normalized season_rates; " + str(player.get("rate_provenance") or "source unknown")
        return _numbers(player["season_rates"], (*TOTALS, "minutes")), source
    current, prior = player.get("current_rates"), player.get("prior_rates")
    games = _integer(player, "current_games", 0)
    if current is None or games == 0:
        if prior is None:
            raise ValueError(f"No sampled rates for player {player['id']}")
        return _numbers(prior, (*TOTALS, "minutes")), "prior season fallback"
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
    source = "current season" if games >= 3 else "small current sample"
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
            "model_edge": probability,
            "estimate_kind": "uncalibrated heuristic edge",
            "attainability": "unknown"
            if probability is None
            else "cushion"
            if probability >= 0.8
            else "favored"
            if probability >= 0.6
            else "swing"
            if probability >= 0.4
            else "trailing",
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
        return sum(c["win_probability"] or 0 for c in categories.values()) / 9

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
        # Optional benching avoids forced negative TO/shooting contributions.
        if priority(player)[0] <= 0:
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
        available = [
            p
            for p in context["players"].values()
            if day in p["schedule"]
            and day not in p["unavailable"]
            and p.get("active", True)
            and p.get("lineup_slot") not in ("IR", "IR+")
            and day >= p.get("available_from", day)
        ]
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
            context["opponent_daily_slots"].get(day, context["slots"]),
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
    if context.get("finalized") and not context["dates"]:
        for category in categories.values():
            margin = category["margin"]
            edge = None if margin is None else float(margin > 0)
            category.update(
                win_probability=edge,
                model_edge=edge,
                estimate_kind="final actual comparison",
                attainability="unknown" if edge is None else category["state"],
            )
        probability = (
            None
            if any(c["margin"] is None for c in categories.values())
            else float(sum(c["state"] == "winning" for c in categories.values()) >= 5)
        )
    return {
        "actual_primitives": {"user": dict(context["ours"]), "opponent": dict(context["theirs"])},
        "remaining_primitives": {
            "user": {k: ours[k] - context["ours"][k] for k in TOTALS},
            "opponent": {k: theirs[k] - context["theirs"][k] for k in TOTALS},
        },
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
        if raw.get("rate_basis_source"):
            provenance[pid] = str(raw["rate_basis_source"])
        for flag in ("active", "core_protection_override", "protected", "locked", "undroppable", "droppable"):
            if raw.get(flag) is not None and not isinstance(raw[flag], bool):
                raise ValueError(f"{flag} must be boolean when supplied")
        schedule = _dates(raw["schedule"])
        unavailable = _dates(raw.get("unavailable_dates", []))
        if str(raw.get("injury_status") or "").lower() in ("out", "inactive"):
            unavailable = schedule
        players[pid] = {**raw, "rates": rates, "schedule": schedule, "unavailable": unavailable}
        for field in ("available_from", "earliest_add_date", "earliest_drop_date"):
            if raw.get(field) is not None:
                _dates([raw[field]])
        players[pid]["transaction_locked_dates"] = _dates(raw.get("transaction_locked_dates", []))
        if payload.get("allow_core_drops") is True:
            players[pid]["core_protection_override"] = True
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
        "finalized": payload.get("matchup_finalized") is True,
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


def _protection(player):
    """Separate immutable ESPN constraints, user protects, and overridable core guard."""
    if player.get("undroppable") is True or player.get("droppable") is False:
        return "ESPN undroppable"
    if player.get("locked") is True:
        return "ESPN/transaction lock"
    if player.get("protected") is True:
        return "User protected"
    if player.get("core_protection_override") is True:
        return None
    rank = player.get("season_rank")
    if player.get("core_player") is True:
        return "Default core protection: " + str(
            player.get("core_player_source") or "caller core designation; source unknown"
        )
    if isinstance(rank, (int, float)) and not isinstance(rank, bool) and 0 < rank <= 50:
        return f"Default core protection: season rank {rank} ({player.get('season_rank_source') or 'source unknown'})"
    if player["rates"]["pts"] >= 25 or _season_value(player) >= 3:
        return "Default core protection: 25+ PTS/game or season-value proxy >=3; rank metadata incomplete"
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
            else "cushion"
            if p >= 0.8
            else "favored"
            if p >= 0.6
            else "swing"
            if p >= 0.4
            else "trailing"
        )
        if context.get("finalized") and not context["dates"] and margin is not None:
            classification = category["state"]
        explanation = {
            "winning": "Final actual category win.",
            "losing": "Final actual category loss.",
            "tied": "Final actual category tie; ties do not count as outright wins.",
            "unknown": "Shooting attempts or projection inputs are missing.",
            "cushion": "Modeled cushion under heuristic uncertainty, not a guaranteed win.",
            "favored": "Positive modeled edge; additional production may still matter.",
            "trailing": "Trailing in the model; recovery requires an explored feasible plan.",
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
                d >= action["date"]
                and d in context["dates"]
                and d not in add["unavailable"]
                and add.get("active", True)
                and add.get("lineup_slot") not in ("IR", "IR+")
                and d >= add.get("available_from", d)
                for d in add["schedule"]
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


def _edges(forecast):
    return {k: forecast["categories"][k]["win_probability"] for k in CATEGORIES}


def _focus(forecast, selected):
    return sum(_edges(forecast)[k] for k in selected) / 5


def _guards(baseline, forecast, selected, aggressive=False):
    if aggressive:
        return True
    before, after = _edges(baseline), _edges(forecast)
    return all(after[k] >= 0.8 - 1e-12 for k in selected if before[k] >= 0.8) and sum(
        after[k] >= 0.4 for k in selected
    ) >= sum(before[k] >= 0.4 for k in selected)


def _material(baseline, forecast, selected, cost):
    before, after = _edges(baseline), _edges(forecast)
    return _focus(forecast, selected) - _focus(baseline, selected) - cost >= 0.005 and any(
        before[k] < 0.8 and after[k] - before[k] >= 0.01 for k in selected
    )


def _primitive_arithmetic(before, after, added, lost):
    return {
        k: {
            "before": before["user_totals"][k],
            "add": added[k],
            "drop": lost[k],
            "spillover": after["user_totals"][k] - before["user_totals"][k] - added[k] + lost[k],
            "after": after["user_totals"][k],
            "net": after["user_totals"][k] - before["user_totals"][k],
        }
        for k in TOTALS
    }


def _category_arithmetic(before, after, primitives):
    result = {}
    for k in CATEGORIES:
        left, right = before["categories"][k]["user"], after["categories"][k]["user"]
        row = {
            "before": left,
            "after": right,
            "net": None if left is None or right is None else right - left,
            "opponent_before": before["categories"][k]["opponent"],
            "opponent_after": after["categories"][k]["opponent"],
            "lower_is_better": k == "to",
        }
        if k in COUNTS:
            row.update(primitives[k])
        else:
            made, attempts = ("fgm", "fga") if k == "fg_pct" else ("ftm", "fta")
            row.update(
                makes=primitives[made],
                attempts=primitives[attempts],
                percentage_points=None if left is None or right is None else (right - left) * 100,
                additive=False,
            )
        result[k] = row
    return result


def _describe_move(context, before, after, action, selected):
    move = dict(action)
    add, drop = (context["players"][move[k]] for k in ("add_id", "drop_id"))
    calculation = _calculation(context, before, after, move)
    added_starts, lost_starts = calculation["pts"]["add_starts"], calculation["pts"]["drop_starts"]
    primitives = _primitive_arithmetic(
        before,
        after,
        {k: add["rates"][k] * added_starts for k in TOTALS},
        {k: drop["rates"][k] * lost_starts for k in TOTALS},
    )
    impacts = {}
    for k in CATEGORIES:
        left, right = before["categories"][k], after["categories"][k]
        impacts[k] = {
            "before": left["user"],
            "after": right["user"],
            "margin_before": left["margin"],
            "margin_after": right["margin"],
            "estimate_gain": right["win_probability"] - left["win_probability"],
            "flips_projection": left["state"] != "winning" and right["state"] == "winning",
        }
    if lost_starts:
        zero_reason = None
    elif not drop.get("active", True) or drop.get("lineup_slot") in ("IR", "IR+"):
        zero_reason = "Drop is inactive/IR; activation is not modeled."
    elif not any(d >= move["date"] and d in context["dates"] for d in drop["schedule"]):
        zero_reason = "Drop has no remaining scheduled unstarted games after the effective date."
    elif all(d in drop["unavailable"] for d in drop["schedule"] if d >= move["date"]):
        zero_reason = "Drop is explicitly unavailable for all remaining games."
    else:
        zero_reason = "Drop receives zero usable starts under the modeled slots, availability and lineup policy."
    def other_starts(forecast):
        return {
            (row["date"], row["player_id"])
            for row in forecast["starts"]
            if row["owner"] == "user" and row["player_id"] not in (add["id"], drop["id"])
        }

    prior_starts, next_starts = other_starts(before), other_starts(after)

    def changed_starts(keys):
        return [
            {"date": day, "player_id": pid, "name": context["players"][pid].get("name") or pid}
            for day, pid in sorted(keys)
        ]

    gain = _focus(after, selected) - _focus(before, selected)
    move.update(
        calculation=calculation,
        arithmetic={"primitives": primitives, "categories": _category_arithmetic(before, after, primitives)},
        add_starts=added_starts,
        drop_starts=lost_starts,
        zero_drop_reason=zero_reason,
        lineup_changes={
            "displaced": changed_starts(prior_starts - next_starts),
            "recovered": changed_starts(next_starts - prior_starts),
            "net_starts": len(next_starts) - len(prior_starts),
        },
        rate_provenance={"add": context["provenance"][add["id"]], "drop": context["provenance"][drop["id"]]},
        rate_evidence={"add": add.get("rate_provenance"), "drop": drop.get("rate_provenance")},
        add_rates=dict(add["rates"]),
        drop_rates=dict(drop["rates"]),
        score_before=_focus(before, selected),
        score_after=_focus(after, selected),
        focus_score_gain=gain,
        estimated_win_gain=gain,
        net_score=gain - action["season_cost"],
        probability_gain=after["win_at_least_five_probability"] - before["win_at_least_five_probability"],
        gains={k: row["net"] for k, row in primitives.items()},
        category_impacts=impacts,
        category_probability_gains={k: row["estimate_gain"] for k, row in impacts.items()},
        target_categories=[k for k in selected if impacts[k]["estimate_gain"] >= 0.01],
        games_gain=after["games"]["user"] - before["games"]["user"],
        minutes_gain=after["minutes"]["user"] - before["minutes"]["user"],
        season_value={"drop": _season_value(drop), "add": _season_value(add), "basis": "per-game heuristic proxy"},
        long_term_tradeoff={
            "cost": action["season_cost"],
            "explanation": "Soft per-game opportunity cost, not future-week modeling.",
        },
        rationale=(
            "Full-roster counterfactual including lost starts and spillover; "
            "focus score is a heuristic, not win probability."
        ),
    )
    return move


def _invalidate(result):
    """Clear confidence and all derived labels together, including legacy fields."""
    for forecast in (result.get("baseline"), result.get("projected")):
        if forecast:
            forecast["win_at_least_five_probability"] = None
            for category in forecast["categories"].values():
                category.update(win_probability=None, model_edge=None, attainability="unknown")
    result.update(safe_categories=[], improvement_categories=[], recommended_plan=None, actions=[], plan=[])
    for category in result["strategy"].values():
        category.update(
            classification="unknown",
            estimate=None,
            target_priority=None,
            safe_win=False,
            improvement_target=False,
            recommended_target=False,
            can_flip_with_one_move=False,
            best_estimate_gain=None,
            explanation="Required projection inputs are incomplete; no confidence or cushion claim is available.",
        )


def _eligible_pickups(context, day, ownership, acquired):
    return [
        pid
        for pid, p in sorted(context["players"].items())
        if p["owner"] == "free"
        and pid not in acquired
        and pid not in ownership
        and not p.get("locked")
        and day >= p.get("earliest_add_date", day)
        and day not in p["transaction_locked_dates"]
        and p.get("active", True)
        and p.get("lineup_slot") not in ("IR", "IR+")
        and any(
            d >= max(day, p.get("available_from", day)) and d in context["dates"] and d not in p["unavailable"]
            for d in p["schedule"]
        )
    ]


def plan_waivers(payload):
    """Return one best explored legal ordered plan; all calculations are pure.

    Shared deterministic nine-category lineups make full-roster projections reusable
    across all 126 focus sets. Beam expansion permits non-improving intermediate
    moves. Exact global lineup/plan optimization is deliberately not claimed.
    """
    result = {
        "status": "unavailable",
        "reasons": [],
        "actions": [],
        "plan": [],
        "recommended_plan": None,
        "recommendations": [],
        "recommendation_kind": "alternatives",
        "primary_recommendation_kind": "ordered_plan",
        "strategy": {},
        "baseline": None,
        "projected": None,
        "remaining_adds": None,
        "provenance": {},
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
        "data_gaps": list(payload.get("data_gaps", []))
        if isinstance(payload, dict) and isinstance(payload.get("data_gaps", []), list)
        else [],
        "search": {"evaluations": 0, "evaluation_limit_reached": False},
    }
    try:
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("data_gaps", []), list)
            or any(not isinstance(g, str) for g in payload.get("data_gaps", []))
        ):
            raise ValueError("data_gaps must be a string list")
        metadata = payload.get("projection_metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("projection_metadata must be a mapping")
        for name, component in metadata.items():
            if not isinstance(component, dict) or not isinstance(component.get("complete"), bool):
                raise ValueError("projection metadata components require an explicit complete boolean")
            if not component["complete"]:
                result["data_gaps"].append(f"{name}: {component.get('reason') or 'incomplete projection evidence'}")
        context = _context(payload)
        requested = payload.get("selected_categories")
        if requested is not None and (
            not isinstance(requested, list)
            or len(requested) != 5
            or len(set(requested)) != 5
            or any(k not in CATEGORIES for k in requested)
        ):
            raise ValueError("Select exactly five unique supported category keys")
        baseline = _forecast(context, [])
        context["opponent_starts"] = [s for s in baseline["starts"] if s["owner"] == "opponent"]
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as error:
        result["reasons"] = [f"Incomplete or invalid optimizer inputs: {error}"]
        return result
    result.update(
        baseline=baseline,
        projected=baseline,
        remaining_adds=context["budget"],
        provenance=context["provenance"],
        uncertainty=context["uncertainty"],
        strategy=_strategy(baseline, context),
        horizon={
            "basis": "banked actuals plus remaining usable starts",
            "as_of": payload.get("as_of"),
            "matchup_end": payload.get("matchup_end"),
            "remaining_dates": context["dates"],
        },
        protected_players={
            pid: p["protection"] for pid, p in context["players"].items() if p["owner"] == "user" and p["protection"]
        },
        protection_policy={
            "automatic": "top-50 season rank, explicit core designation, or disclosed rate proxy",
            "override": "allow_core_drops / player core_protection_override; ESPN and user locks persist",
            "rank_metadata_missing": sorted(
                pid for pid in context["roster"] if context["players"][pid].get("season_rank") is None
            ),
        },
        projection_metadata=metadata,
    )
    if result["data_gaps"] or any(v is None for v in _edges(baseline).values()):
        _invalidate(result)
        result.update(
            status="incomplete", reasons=["Required roster, actual, rate, history or schedule evidence is incomplete."]
        )
        return result
    aggressive = payload.get("aggressive_cushion_sacrifice") is True
    cushions = {k for k, edge in _edges(baseline).items() if edge >= 0.8}
    if len(cushions) > 5:
        cushions = set(sorted(cushions, key=lambda k: (-_edges(baseline)[k], CATEGORIES.index(k)))[:5])
    subsets = [tuple(requested)] if requested else [s for s in combinations(CATEGORIES, 5) if cushions <= set(s)]
    # Compute all 126 consistently, then apply the cushion inclusion policy.
    all_sets = [tuple(requested)] if requested else list(combinations(CATEGORIES, 5))
    initial = {pid: pid for pid in sorted(context["roster"])}
    # State: forecast, ordered bare ledger, current ownership/ancestry, ever acquired, streamed roots.
    empty = (baseline, [], initial, frozenset(), frozenset())
    library = [empty]
    beam = [empty]
    score_cache = {}

    def state_key(state):
        return tuple((a["date"], a["add_id"], a["drop_id"]) for a in state[1])

    def set_scores(state):
        key = state_key(state)
        if key not in score_cache:
            edges = _edges(state[0])
            cost = sum(a["season_cost"] for a in state[1])
            score_cache[key] = {s: sum(edges[k] for k in s) / 5 - cost for s in all_sets}
        return score_cache[key]

    def rank(state, selected=None):
        eligible = [selected] if selected else subsets
        score = max(set_scores(state)[s] for s in eligible)
        return (
            -score,
            len(state[1]),
            sum(a["season_cost"] for a in state[1]),
            -max(min(_edges(state[0])[k] for k in s) for s in eligible),
            state_key(state),
        )

    evaluations, evaluated_drops, pruned = 0, set(), False
    first_layer_evaluated = 0
    first_layer_complete = budget_zero = context["budget"] == 0
    candidate_truncated = False
    budget = context["budget"] if context["budget"] is not None else 1
    first_layer_total = (
        sum(
            len(_eligible_pickups(context, day, initial, frozenset()))
            * sum(
                not context["players"][pid]["protection"]
                and day >= context["players"][pid].get("earliest_drop_date", day)
                and day not in context["players"][pid]["transaction_locked_dates"]
                for pid in initial
            )
            for day in context["dates"]
        )
        if budget and context["stream_slots"]
        else 0
    )
    for depth in range(budget):
        expanded = []
        for forecast, actions, ownership, acquired, roots in beam:
            for day in context["dates"]:
                if actions and day < actions[-1]["date"]:
                    continue
                candidates = _eligible_pickups(context, day, ownership, acquired)
                candidate_truncated |= len(candidates) > context["candidate_limit"]
                for add_id in candidates[: context["candidate_limit"]]:
                    for drop_id, root in sorted(ownership.items()):
                        drop = context["players"][drop_id]
                        if (
                            drop["protection"]
                            or day < drop.get("earliest_drop_date", day)
                            or day in drop["transaction_locked_dates"]
                        ):
                            continue
                        if root not in roots and len(roots) >= context["stream_slots"]:
                            continue
                        if evaluations >= context["evaluation_limit"]:
                            result["search"]["evaluation_limit_reached"] = True
                            break
                        action = {
                            "date": day,
                            "add_id": add_id,
                            "drop_id": drop_id,
                            "stream_slot": root,
                            "season_cost": _season_cost(drop, context["players"][add_id]),
                        }
                        ledger = [*actions, action]
                        projected = _forecast(context, ledger)
                        evaluations += 1
                        if depth == 0:
                            first_layer_evaluated += 1
                        evaluated_drops.add(drop_id)
                        if any(v is None for v in _edges(projected).values()):
                            continue
                        # Do not prune neutral/negative prefixes: later moves can complement them.
                        next_ownership = {pid: ancestry for pid, ancestry in ownership.items() if pid != drop_id}
                        next_ownership[add_id] = root
                        state = (projected, ledger, next_ownership, acquired | {add_id}, roots | {root})
                        library.append(state)
                        expanded.append(state)
                    if result["search"]["evaluation_limit_reached"]:
                        break
                if result["search"]["evaluation_limit_reached"]:
                    break
            if result["search"]["evaluation_limit_reached"]:
                break
        if depth == 0:
            first_layer_complete = not result["search"]["evaluation_limit_reached"] and not candidate_truncated
        if not expanded or result["search"]["evaluation_limit_reached"]:
            break
        expanded.sort(key=rank)
        pruned |= len(expanded) > context["beam"]
        beam = expanded[: context["beam"]]
    # Every full projection is reused across the same focus subsets.
    choices = []
    library_by_key = {state_key(state): state for state in library}
    for state in library:
        set_scores(state)
        cost = sum(a["season_cost"] for a in state[1])
        prefixes = [library_by_key[state_key(state)[:n]] for n in range(1, len(state[1]) + 1)]
        for selected in subsets:
            # A selected cushion/viability guard applies at every ledger step too.
            if not _guards(baseline, state[0], selected, aggressive) or any(
                not _guards(baseline, s[0], selected, aggressive) for s in prefixes
            ):
                continue
            if state[1] and not _material(baseline, state[0], selected, cost):
                continue
            choices.append((rank(state, selected), tuple(CATEGORIES.index(k) for k in selected), selected, state))
    _, _, selected, best = min(choices)
    # With unknown budget only conditional one-move alternatives are returned.
    if context["budget"] is None:
        best = empty
    moves, before = [], baseline
    for index, action in enumerate(best[1]):
        after = library_by_key[state_key(best)[: index + 1]][0]
        moves.append(_describe_move(context, before, after, action, selected))
        before = after
    added = {k: sum(m["arithmetic"]["primitives"][k]["add"] for m in moves) for k in TOTALS}
    lost = {k: sum(m["arithmetic"]["primitives"][k]["drop"] for m in moves) for k in TOTALS}
    primitives = _primitive_arithmetic(baseline, best[0], added, lost)
    cost = sum(m["season_cost"] for m in moves)
    search = result["search"]
    search.update(
        evaluations=evaluations,
        evaluation_limit=context["evaluation_limit"],
        beam_width=context["beam"],
        beam_pruned=pruned,
        candidate_limit=context["candidate_limit"],
        candidate_pool=sum(p["owner"] == "free" for p in context["players"].values()),
        evaluated_drop_ids=sorted(evaluated_drops),
        legal_drop_ids=sorted(pid for pid in context["roster"] if not context["players"][pid]["protection"]),
        forecasts=len(library),
        category_sets_evaluated=len(all_sets),
        first_layer_pairs_evaluated=first_layer_evaluated,
        first_layer_pairs_total=first_layer_total,
        first_layer_complete=first_layer_complete,
        candidate_truncated=candidate_truncated,
        budget_zero=budget_zero,
        upstream_market_complete=payload.get("market_complete"),
        plan_search="best explored; bounded beam and shared greedy nine-category lineup policy",
        alternatives_complete=first_layer_complete,
    )
    alternatives = []
    for state in library:
        if (
            len(state[1]) == 1
            and _guards(baseline, state[0], selected, aggressive)
            and _material(baseline, state[0], selected, state[1][0]["season_cost"])
        ):
            alternatives.append(_describe_move(context, baseline, state[0], state[1][0], selected))
    alternatives.sort(key=lambda m: (-m["net_score"], m["season_cost"], m["date"], m["add_id"], m["drop_id"]))
    unique = {}
    for alternative in alternatives:
        unique.setdefault((alternative["add_id"], alternative["drop_id"]), alternative)
    alternatives = list(unique.values())
    for index, alternative in enumerate(alternatives, 1):
        alternative.update(rank=index, conditional_on_one_add=context["budget"] is None)
    safe = [k for k in selected if _edges(baseline)[k] >= 0.8]
    result.update(
        status="ready" if context["budget"] is not None else "incomplete",
        selected_categories=list(selected),
        category_selection_source="user" if requested else "common feasible full-roster plan library; all 126 sets",
        safe_categories=safe,
        improvement_categories=[k for k in selected if k not in safe],
        projected=best[0],
        actions=moves,
        plan=moves,
        remaining_adds=None if context["budget"] is None else context["budget"] - len(moves),
        recommendations=alternatives,
        score_basis="selected_five_heuristic_edges_minus_soft_season_cost",
        recommendation_groups={
            pid: [m["rank"] for m in alternatives if m["drop_id"] == pid] for pid in sorted(context["roster"])
        },
        alternatives_explanation="Secondary alternatives compete; only recommended_plan.moves form one ordered plan.",
        recommended_plan={
            "moves": moves,
            "selected_categories": list(selected),
            "score_before": _focus(baseline, selected),
            "score_after": _focus(best[0], selected) - cost,
            "focus_score_after": _focus(best[0], selected),
            "season_cost": cost,
            "net_score_gain": _focus(best[0], selected) - _focus(baseline, selected) - cost,
            "arithmetic": {"primitives": primitives, "categories": _category_arithmetic(baseline, best[0], primitives)},
            "budget_before": context["budget"],
            "acquisitions": len(moves),
            "budget_after": None if context["budget"] is None else context["budget"] - len(moves),
            "weakest_selected_edge": min(_edges(best[0])[k] for k in selected),
            "viable_five": all(_edges(best[0])[k] >= 0.4 for k in selected),
            "guard_policy": "selected baseline cushion >=.80; preserve viable-edge count >=.40",
            "aggressive_opt_in": aggressive,
            "coverage": search,
            "optimality": "best explored",
        },
    )
    for k, category in result["strategy"].items():
        impacts = [m["category_impacts"][k] for m in alternatives]
        gain = max((i["estimate_gain"] for i in impacts), default=0)
        can_flip = any(i["flips_projection"] for i in impacts)
        if category["classification"] == "trailing" and gain >= 0.01:
            category["classification"] = "reachable"
        category.update(
            selected=k in selected,
            safe_win=k in safe,
            improvement_target=k in selected and k not in safe,
            target_priority=0 if k not in selected or k in safe else category["target_priority"],
            best_pickup_margin=max((i["margin_after"] for i in impacts), default=category["projected_margin"]),
            can_flip_with_one_move=can_flip,
            best_estimate_gain=gain,
            recommended_target=k in selected and k not in safe and gain >= 0.01,
        )
    cautious_sd = {k: value * 1.5 for k, value in context["sd"].items()}
    cautious_before, _ = _assessment(baseline["user_totals"], baseline["opponent_totals"], cautious_sd)
    cautious_after, _ = _assessment(best[0]["user_totals"], best[0]["opponent_totals"], cautious_sd)
    result["recommended_plan"]["sensitivity"] = {
        "scale_multiplier": 1.5,
        "net_score_gain": sum(
            cautious_after[k]["win_probability"] - cautious_before[k]["win_probability"] for k in selected
        )
        / 5
        - cost,
        "basis": "same final totals and chosen five; wider heuristic scale, not reranked alternatives",
    }
    if not moves:
        result["reasons"].append("No materially beneficial legal ordered plan passed the selected-category guards.")
    if context["budget"] is None:
        result["reasons"].append(
            "Acquisition budget unknown; alternatives are conditional and no ordered moves are confirmed."
        )
    if search["evaluation_limit_reached"] or pruned:
        result["limitations"].append(
            "Search bounds pruned exploration; result is best found, not a proven global optimum."
        )
    if payload.get("market_complete") is not True:
        result["limitations"].append("Upstream whole-market coverage is partial or unverified.")
    if not context["dates"]:
        result["reasons"].append("No remaining dates; only banked actuals are compared.")
    return result
