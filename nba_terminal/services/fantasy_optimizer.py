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
    "Independent normal category margins with caller-supplied or historical standard deviations.",
    "Ties do not count as wins; five outright category wins are required.",
    "Continuous normal approximation ignores discrete tie mass; numerical probabilities bounded to [1e-6, 1-1e-6].",
    "Rates and supplied schedules remain constant; unavailable dates contribute no games.",
    "Small current samples blend with up to ten prior-equivalent games; minutes break score ties.",
]
LIMITATIONS = [
    "Model sensitivity estimates are not calibrated probabilities or guarantees; category correlations are ignored.",
    "Bounded beam search and greedy daily lineup selection can miss globally optimal plans.",
    "Caller must supply transaction-effective dates, eligibility, injuries, locks and complete remaining schedules.",
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
    current = _numbers(current, (*TOTALS, "minutes")) if current is not None else None
    prior = _numbers(prior, (*TOTALS, "minutes")) if prior is not None else None
    if current is None and prior is None:
        raise ValueError(f"Missing rates for player {player['id']}")
    if current is None or games == 0:
        if prior is None:
            raise ValueError(f"No sampled rates for player {player['id']}")
        return prior, "prior season fallback"
    if prior is None or games >= 10:
        return current, "current season" if games >= 10 else "small current sample; no prior season"
    weight = games / 10
    return {k: current[k] * weight + prior[k] * (1 - weight) for k in current}, "current/prior blend"


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


def _lineup(players, slots, ours, theirs, deviations, opponent=False):
    """Rank marginal five-category value, then find a feasible matching by augmentation."""
    base = _assessment(ours, theirs, deviations)[1]

    def priority(player):
        score = _assessment(_plus(ours, player["rates"]), theirs, deviations)[1]
        gain = score - base if score is not None and base is not None else 0
        return (-gain, -player["rates"]["minutes"], player["id"])

    # For opponent lineups optimize its own chance, using symmetric deviations.
    if opponent:
        ours, theirs = theirs, ours
        base = _assessment(ours, theirs, deviations)[1]
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
        user = _lineup([p for p in available if p["id"] in roster], slots, ours, theirs, context["sd"])
        opponent = _lineup([p for p in available if p["owner"] == "opponent"], slots, ours, theirs, context["sd"], True)
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
    if not dates or len(dates) > 14:
        raise ValueError("One to fourteen remaining dates required")
    slots = _slots(payload["lineup_slots"])
    daily = payload.get("lineup_slots_by_date", {})
    if not isinstance(daily, dict) or any(day not in dates for day in daily):
        raise ValueError("Daily lineup overrides must use remaining dates")
    daily = {day: _slots(value) for day, value in daily.items()}
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
        if not isinstance(raw.get("locked"), bool):
            raise ValueError("Trusted or user-confirmed player transaction locks required")
        if not isinstance(raw.get("eligible", True), bool):
            raise ValueError("Unknown player eligibility")
        positions = raw["positions"]
        if not isinstance(positions, list) or not positions or any(not isinstance(p, str) or not p for p in positions):
            raise ValueError("Player positions are required")
        rates, provenance[pid] = _rates(raw)
        schedule = _dates(raw["schedule"])
        unavailable = _dates(raw.get("unavailable_dates", []))
        if raw.get("injury_status", "").lower() in ("out", "inactive"):
            unavailable = schedule
        players[pid] = {**raw, "rates": rates, "schedule": schedule, "unavailable": unavailable}
    if not any(p["owner"] == "user" for p in players.values()):
        raise ValueError("User roster is required")
    sd = payload.get("margin_sd")
    if sd is None and payload.get("prior_week_margins"):
        history = payload["prior_week_margins"]
        if len(history) >= 3:
            sd = {k: stdev(row[k] for row in history) for k in CATEGORIES}
    if sd is not None and (
        not isinstance(sd, dict)
        or any(
            isinstance(sd.get(k), bool) or not isinstance(sd.get(k), (int, float)) or not isfinite(sd[k]) or sd[k] <= 0
            for k in CATEGORIES
        )
    ):
        raise ValueError("Every category needs a positive finite margin standard deviation")
    budget = min(
        _integer(payload, "available_adds"),
        max(0, _integer(payload, "weekly_add_limit") - _integer(payload, "used_adds")),
    )
    return {
        "dates": dates,
        "slots": slots,
        "daily_slots": daily,
        "ours": _numbers(payload["current_totals"], TOTALS),
        "theirs": _numbers(payload["opponent_totals"], TOTALS),
        "players": players,
        "roster": {pid for pid, p in players.items() if p["owner"] == "user"},
        "sd": sd,
        "budget": budget,
        "provenance": provenance,
        "stream_slots": min(4, _integer(payload, "max_stream_slots", 4)),
        "beam": min(32, max(1, _integer(payload, "beam_width", 8))),
        "candidate_limit": min(100, max(1, _integer(payload, "candidate_limit", 40))),
        "evaluation_limit": min(5000, max(1, _integer(payload, "evaluation_limit", 2000))),
    }


def plan_waivers(payload):
    """Return recommendations from normalized primitives; malformed/missing data fail closed.

    No input is mutated. Transactions take effect before all games on their given
    date. Adapters must exclude dates on which acquisition cannot yet take effect.
    """
    result = {
        "status": "unavailable",
        "reasons": [],
        "actions": [],
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
    if baseline["win_at_least_five_probability"] is None or result["data_gaps"]:
        if result["data_gaps"]:
            baseline["win_at_least_five_probability"] = None
            for category in baseline["categories"].values():
                category.update(win_probability=None, attainability="unknown")
        result.update(
            status="incomplete",
            reasons=["Complete shooting denominators, uncertainty and availability evidence required"],
        )
        return result
    result["status"] = "ready"
    # Each state retains its chronological transaction ledger and slot ancestry.
    initial = {pid: pid for pid in context["roster"]}
    beam = [(baseline, [], initial, frozenset(), frozenset())]
    best = beam[0]

    def rank(state):
        forecast, actions = state[:2]
        return (forecast["win_at_least_five_probability"], -len(actions), forecast["minutes"]["user"])

    for _ in range(min(context["budget"], len(context["dates"]) * context["stream_slots"])):
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
                    probability = _assessment(
                        _plus(forecast["user_totals"], rates), forecast["opponent_totals"], context["sd"]
                    )[1]
                    return (-probability, -rates["minutes"], pid)

                candidates.sort(key=candidate_rank)
                for drop_id, root in sorted(ownership.items()):
                    if result["search"]["evaluation_limit_reached"]:
                        break
                    if context["players"][drop_id].get("locked", False):
                        continue
                    if root not in stream_roots and len(stream_roots) >= context["stream_slots"]:
                        continue
                    for add_id in candidates[: context["candidate_limit"]]:
                        if result["search"]["evaluations"] >= context["evaluation_limit"]:
                            result["search"]["evaluation_limit_reached"] = True
                            break
                        result["search"]["evaluations"] += 1
                        action = {"date": day, "add_id": add_id, "drop_id": drop_id, "stream_slot": root}
                        next_actions = [*actions, action]
                        projected = _forecast(context, next_actions)
                        if projected["win_at_least_five_probability"] is None:
                            continue
                        gain = projected["win_at_least_five_probability"] - forecast["win_at_least_five_probability"]
                        if gain <= 1e-12:
                            continue
                        action["probability_gain"] = gain
                        action["gains"] = {k: projected["user_totals"][k] - forecast["user_totals"][k] for k in TOTALS}
                        action["category_probability_gains"] = {
                            k: projected["categories"][k]["win_probability"]
                            - forecast["categories"][k]["win_probability"]
                            for k in CATEGORIES
                        }
                        action["games_gain"] = projected["games"]["user"] - forecast["games"]["user"]
                        action["minutes_gain"] = projected["minutes"]["user"] - forecast["minutes"]["user"]
                        next_ownership = {pid: slot for pid, slot in ownership.items() if pid != drop_id}
                        next_ownership[add_id] = root
                        expanded.append(
                            (projected, next_actions, next_ownership, acquired | {add_id}, stream_roots | {root})
                        )
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
    result.update(projected=best[0], actions=best[1], remaining_adds=context["budget"] - len(best[1]))
    return result
