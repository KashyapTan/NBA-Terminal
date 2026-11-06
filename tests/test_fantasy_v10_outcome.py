"""Date ledger versus category-outcome regression, not a private-plan reproduction."""

from copy import deepcopy

import pytest

from nba_terminal.services.fantasy_optimizer import (
    CATEGORIES,
    TOTALS,
    _assessment,
    _context,
    _forecast,
    _outcome,
    plan_waivers,
)
from tests.fantasy_v10_fixture import ACTUAL, DAYS, END, FIVE, JONES, MERRILL, domain
from tests.test_fantasy_v8_lineups import reconcile


def test_screenshot_totals_reproduced_but_uncompensated_turnover_loss_rejected():
    data = domain()
    result = plan_waivers(data)
    assert result["actions"] == []
    assert result["remaining_adds"] == 1
    assert result["outcome_policy"]["baseline"]["all_nine"] == {"wins": 4, "losses": 5, "ties": 0}
    for key in TOTALS:
        assert result["baseline"]["user_totals"][key] == pytest.approx(END[key])
    sunday = next(e for e in result["outcome_policy"]["examples"] if e["actions"][0]["date"] == DAYS[2])
    assert sunday["all_nine"] == {"wins": 3, "losses": 6, "ties": 0}
    assert sunday["totals"]["to"] == pytest.approx(74.8)
    assert sunday["totals"]["pts"] == pytest.approx(666.7)
    assert sunday["totals"]["fgm"] / sunday["totals"]["fga"] == pytest.approx(0.4648)
    assert sunday["totals"]["ftm"] / sunday["totals"]["fta"] == pytest.approx(0.6958)
    assert [s["date"] for s in sunday["starts"] if s["player_id"] == "100"] == DAYS[:2]
    assert [s["date"] for s in sunday["starts"] if s["player_id"] == "101"] == DAYS[2:]
    reconcile(result, data)


def test_today_and_sunday_ownership_are_different_and_banked_actuals_never_rewritten():
    data = domain()
    context = _context(data)
    context["scored_categories"] = FIVE
    results = [_forecast(context, [{"date": day, "add_id": "101", "drop_id": "100"}]) for day in (DAYS[0], DAYS[2])]
    for key in TOTALS:
        assert results[1]["user_totals"][key] - results[0]["user_totals"][key] == pytest.approx(2 * MERRILL[key])
        assert results[0]["actual_primitives"]["user"][key] == ACTUAL[key]
    assert results[0]["opponent_totals"] == results[1]["opponent_totals"]


@pytest.mark.parametrize("turnovers,wins", [(1.1, 4), (0.1, 5)])
def test_compensating_real_win_and_genuine_five_win_improvement_survive(turnovers, wins):
    data = domain()
    data["players"][1]["current_rates"] = JONES | {"reb": 20, "to": turnovers}
    result = plan_waivers(data)
    assert len(result["actions"]) == 1
    assert result["actions"][0]["date"] == DAYS[2]
    assert result["outcome_policy"]["projected"]["all_nine"]["wins"] == wins
    assert result["projected"]["user_totals"]["reb"] == pytest.approx(220.4)
    reconcile(result, data)


def test_backend_uses_same_tie_tolerance_as_browser():
    data = domain()
    left, right = deepcopy(data["current_totals"]), deepcopy(data["current_totals"])
    left["to"] += 1e-11
    categories, _ = _assessment(left, right, {k: 1 for k in CATEGORIES})
    assert _outcome({"categories": categories}) == {"wins": 0, "losses": 0, "ties": 9}


def test_positions_capacity_and_dated_transaction_lock_cannot_manufacture_improvement():
    data = domain()
    data["players"][1]["current_rates"] = JONES | {"reb": 20, "to": 0.1}
    data["players"][0]["transaction_locked_dates"] = DAYS[:2]
    result = plan_waivers(data)
    assert result["actions"][0]["date"] == DAYS[2]
    assert len([s for s in result["projected"]["starts"] if s["owner"] == "user" and s["date"] == DAYS[2]]) == 10
    data["players"][1].update(positions=["PG"], strict_positions=True)
    assert plan_waivers(data)["actions"] == []  # observed UTIL-only configuration is exact
