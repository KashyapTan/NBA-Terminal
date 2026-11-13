"""Progressive exploration uses frozen synthetic inputs, never provider calls."""

from copy import deepcopy
from datetime import date, timedelta

import pytest

from nba_terminal.services.fantasy_optimizer import iter_waiver_plans, plan_waivers
from tests.test_fantasy_optimizer import fixture, player, rates
from tests.test_fantasy_v9_chains import chain


def final(data):
    publications = list(iter_waiver_plans(data, progressive=True))
    assert publications[-1]["search"]["phase"] == "finished"
    return publications[-1]


def late_market():
    data = fixture()
    days = [(date(2026, 11, 1) + timedelta(days=i)).isoformat() for i in range(12)]
    data.update(dates=days, available_adds=1, selected_categories=["pts", "reb", "ast", "stl", "blk"])
    # Early legal pickups produce no gain. The qualifying pickup is not legally
    # available until day twelve, beyond 11 x 460 full forecasts in old ordering.
    data["players"] += [player(f"neutral{i:03}", schedule=[days[-1]]) for i in range(460)]
    data["players"] += [player("late", schedule=[days[-1]], earliest_add_date=days[-1], current_rates=rates(ast=5))]
    return data


def test_late_legal_candidate_past_5000_is_found_without_total_cutoff():
    data = late_market()
    old = plan_waivers(data)
    assert old["search"]["evaluation_limit_reached"]
    assert old["actions"] == []
    broader = final(data)
    assert broader["search"]["evaluations"] > 5000
    assert broader["search"]["evaluation_limit"] is None
    assert broader["search"]["first_layer_complete"]
    assert broader["actions"][0]["add_id"] == "late"
    assert broader["actions"][0]["date"] == data["dates"][-1]
    assert broader["projected"]["opponent_totals"] == old["baseline"]["opponent_totals"]


@pytest.mark.parametrize("interim", [0, 0.02, 2])
def test_progressive_preserves_dated_chain_efficiency_and_frozen_input(interim):
    data = chain(interim)
    untouched = deepcopy(data)
    expected = plan_waivers(data)
    result = final(data)
    assert result["actions"] == expected["actions"]
    assert result["projected"] == expected["projected"]
    assert data == untouched


def test_no_benefit_small_market_is_finished_without_manufacturing_moves():
    data = fixture()
    data["players"] += [player("zero")]
    result = final(data)
    assert result["actions"] == []
    assert result["search"]["complete"]
    assert result["search"]["first_layer_complete"]
    assert not result["search"]["beam_pruned"]
    assert result["evaluation_state"] == "evaluated_no_material_benefit"


def test_cancel_interrupts_local_continuation_and_does_not_mutate_published_result():
    data = late_market()
    stopped = False
    iterator = iter_waiver_plans(data, progressive=True, cancelled=lambda: stopped)
    first = next(iterator)
    saved = deepcopy(first)
    assert first["search"]["phase"] == "searching"
    stopped = True
    assert next(iterator, None) is None
    assert first == saved


def test_small_exhaustive_oracle_matches_best_two_add_legal_subset():
    from itertools import combinations

    from nba_terminal.services.fantasy_optimizer import _context, _forecast

    data = fixture()
    day = data["dates"][0]
    focus = ["pts", "reb", "ast", "stl", "blk"]
    data.update(dates=[day], selected_categories=focus, max_stream_slots=2, lineup_slots=["UTIL", "UTIL"])
    data["players"] = [player("d0", "user", []), player("d1", "user", [])] + [
        player(f"p{i}", current_rates=rates(**dict.fromkeys(focus, i + 1))) for i in range(3)
    ]
    context = _context(data)
    context["scored_categories"] = focus
    context["opponent_starts"] = []
    candidates = []
    for size in range(3):
        for group in combinations(["p0", "p1", "p2"], size):
            ledger = [{"date": day, "add_id": pid, "drop_id": f"d{i}"} for i, pid in enumerate(group)]
            forecast = _forecast(context, ledger)
            wins = sum(c["state"] == "winning" for c in forecast["categories"].values())
            score = sum(forecast["categories"][k]["win_probability"] for k in focus)
            candidates.append(((wins, score, -size), group, forecast))
    _, group, oracle = max(candidates)
    result = final(data)
    assert {m["add_id"] for m in result["actions"]} == set(group)
    assert result["projected"]["user_totals"] == oracle["user_totals"]
