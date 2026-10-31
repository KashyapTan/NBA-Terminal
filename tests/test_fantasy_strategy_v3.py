"""V3 remaining-total, selected-five and all-legal-drop regressions (synthetic)."""

from copy import deepcopy

import pytest

from nba_terminal.services.fantasy_optimizer import plan_waivers
from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers
from tests.test_fantasy_optimizer import fixture, player, rates, totals
from tests.test_fantasy_strategy_v2 import NOW, prefs, snapshot


def four_days():
    data = fixture()
    days = [f"2026-11-0{n}" for n in range(1, 5)]
    data.update(dates=days, available_adds=1, selected_categories=["pts", "reb", "ast", "stl", "blk"])
    data["current_totals"] = totals(pts=0)
    data["opponent_totals"] = totals(pts=44)
    data["players"] = [
        player("drop", "user", days, current_rates=rates(pts=10)),
        player("add", schedule=days, current_rates=rates(pts=12)),
    ]
    return data


def test_exact_twelve_times_four_minus_ten_times_four_is_eight():
    data = four_days()
    result = plan_waivers(data)
    option = result["recommendations"][0]
    c = option["calculation"]["pts"]
    assert (c["add_rate"], c["drop_rate"], c["add_starts"], c["drop_starts"]) == (12, 10, 4, 4)
    assert (c["added_total"], c["lost_total"], c["lineup_other_net"], c["net_total"]) == (48, 40, 0, 8)
    assert option["gains"]["pts"] == 8
    assert result["baseline"]["user_totals"]["pts"] == 40
    assert result["projected"]["user_totals"]["pts"] == 48


@pytest.mark.parametrize("days,slots", [(2, ["UTIL"]), (4, [])])
def test_less_remaining_games_and_consumed_capacity_do_not_invent_gain(days, slots):
    data = four_days()
    data["players"][1]["schedule"] = data["dates"][:days]
    data["lineup_slots_by_date"] = {data["dates"][0]: slots}
    if days == 2:
        assert not plan_waivers(data)["recommendations"]
    else:
        c = plan_waivers(data)["recommendations"][0]["calculation"]["pts"]
        assert c["add_starts"] == c["drop_starts"] == 3
        assert c["net_total"] == 6


def test_all_legal_drops_and_repeat_best_drop_have_discoverable_alternatives():
    data = four_days()
    data["players"] += [
        player("other_drop", "user", [], draft_round=1, season_rank=1),
        player("second_add", schedule=data["dates"], current_rates=rates(pts=13)),
    ]
    data["lineup_slots"] = ["UTIL", "UTIL"]
    result = plan_waivers(data)
    pairs = {(a["add_id"], a["drop_id"]) for a in result["recommendations"]}
    assert pairs == {("add", "drop"), ("add", "other_drop"), ("second_add", "drop"), ("second_add", "other_drop")}
    assert len(result["recommendation_groups"]["other_drop"]) == 2
    assert all(a["net_score"] > 0 and a["estimated_win_gain"] > 0 for a in result["recommendations"])
    assert len(result["plan"]) == 1
    data["players"][2]["protected"] = True
    assert all(a["drop_id"] != "other_drop" for a in plan_waivers(data)["recommendations"])


def test_safe_rebounds_count_but_swing_assists_are_improvement_priority():
    data = fixture()
    data["current_totals"] = totals(reb=1000, pts=0, ast=9)
    data["opponent_totals"] = totals(pts=1000)
    data["players"] += [player("reb", current_rates=rates(reb=50)), player("ast", current_rates=rates(ast=8))]
    result = plan_waivers(data)
    assert len(result["selected_categories"]) == 5
    assert "reb" in result["safe_categories"]
    assert "ast" in result["improvement_categories"]
    assert "pts" not in result["selected_categories"]
    assert result["recommendations"][0]["add_id"] == "ast"
    assert not result["strategy"]["reb"]["recommended_target"]
    assert not result["strategy"]["reb"]["improvement_target"]


def test_selection_edits_recompute_and_invalid_keys_fail_closed():
    data = four_days()
    data["selected_categories"] = ["reb", "ast", "stl", "blk", "threes"]
    assert not plan_waivers(data)["recommendations"]
    for invalid in (["pts"] * 5, ["pts"], ["pts", "reb", "ast", "stl", "wat"]):
        data["selected_categories"] = invalid
        assert plan_waivers(data)["status"] == "unavailable"


def test_week_start_midweek_end_keep_recorded_actuals_and_only_future_starts():
    data = four_days()
    for start in range(5):
        case = deepcopy(data)
        case["dates"] = data["dates"][start:]
        case["current_totals"]["pts"] = start * 10
        result = plan_waivers(case)
        assert result["baseline"]["user_totals"]["pts"] == 40
        if start < 4:
            assert result["recommendations"][0]["gains"]["pts"] == 2 * (4 - start)
        else:
            assert not result["recommendations"]


def test_scoped_fallback_seven_used_six_and_unknown_usage():
    data = snapshot()
    data["league"]["acquisition_settings"]["weekly_add_limit"] = None
    user = data["teams"][0]
    user.update(weekly_used_adds=6, remaining_adds=None)
    settings = prefs() | {"matchup_add_limit_fallback": 7}
    result = plan_snapshot_waivers(data, settings, NOW)
    assert len(result["plan"]) == 1 and result["remaining_adds"] == 0
    assert result["provenance"]["matchup_add_limit"]["source"] == "user-declared fallback"
    assert result["provenance"]["matchup_add_limit"]["league_id"] == "synthetic"
    assert result["horizon"]["as_of"] == NOW.isoformat()
    user["weekly_usage_complete"] = False
    result = plan_snapshot_waivers(data, settings, NOW)
    assert not result["plan"] and result["remaining_adds"] is None
    assert "matchup_add_limit" not in result["provenance"]
    assert plan_snapshot_waivers(data, prefs(), NOW)["remaining_adds"] is None


def test_weighted_shooting_and_turnover_calculations():
    data = fixture()
    data["selected_categories"] = ["fg_pct", "ft_pct", "to", "ast", "stl"]
    data["players"] = [
        player("drop", "user", current_rates=rates(fgm=1, fga=10, ftm=1, fta=4, to=4)),
        player("add", current_rates=rates(fgm=4, fga=5, ftm=3, fta=4, to=1)),
    ]
    action = plan_waivers(data)["recommendations"][0]
    fg = action["calculation"]["fg_pct"]
    assert fg["weighted"]["before_makes"] == 41
    assert fg["weighted"]["after_attempts"] == 85
    assert fg["net_total"] == pytest.approx(44 / 85 - 41 / 90)
    assert action["calculation"]["to"]["net_total"] == -3
    assert action["calculation"]["to"]["lower_is_better"]
    assert action["category_probability_gains"]["to"] > 0


@pytest.mark.parametrize(
    "metadata", [{"draft_round": 1}, {"draft_pick": 1}, {"season_rank": 1}, {"season_value_unknown": True}]
)
def test_core_metadata_never_hard_excludes_legal_player(metadata):
    data = four_days()
    data["players"][0].update(metadata)
    result = plan_waivers(data)
    assert result["recommendations"]
    assert result["search"]["evaluated_drop_ids"] == ["drop"]
    assert "drop" not in result["protected_players"]


def test_identical_rates_different_games_and_lineup_opportunity_cost():
    data = four_days()
    data["players"][1]["current_rates"] = rates(pts=10)
    data["players"][0]["schedule"] = data["dates"][:2]
    result = plan_waivers(data)
    c = result["recommendations"][0]["calculation"]["pts"]
    assert c["net_total"] == 20
    data["opponent_totals"]["pts"] = 22
    data["players"].append(player("bench", "user", data["dates"], current_rates=rates(pts=8)))
    result = plan_waivers(data)
    c = next(a for a in result["recommendations"] if a["drop_id"] == "drop")["calculation"]["pts"]
    assert c["lineup_other_net"] == -16  # new starts replace the existing bench starts
    assert c["net_total"] == 4
