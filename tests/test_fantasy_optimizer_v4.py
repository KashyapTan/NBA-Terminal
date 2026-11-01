"""Approved V4 full-roster arithmetic and ordered-search regressions; no live I/O."""

from copy import deepcopy

import pytest

from nba_terminal.services.fantasy_optimizer import (
    CATEGORIES,
    TOTALS,
    _calculation,
    _context,
    _describe_move,
    _forecast,
    plan_waivers,
)
from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers
from tests.test_fantasy_optimizer import fixture, player, rates, totals
from tests.test_fantasy_strategy_v2 import NOW, prefs, snapshot

FIVE = ["pts", "reb", "ast", "stl", "blk"]
DAYS = [f"2026-11-0{n}" for n in range(1, 5)]


def paired(data, add="add", drop="drop", day=None):
    context = _context(data)
    before = _forecast(context, [])
    context["opponent_starts"] = [s for s in before["starts"] if s["owner"] == "opponent"]
    action = {"date": day or data["dates"][0], "add_id": add, "drop_id": drop, "season_cost": 0}
    after = _forecast(context, [action])
    return context, before, after, action


def test_eight_rebounds_times_four_minus_ten_times_four_is_negative_eight():
    data = fixture()
    data.update(dates=DAYS, selected_categories=FIVE, available_adds=1)
    data["players"] = [
        player("drop", "user", DAYS, current_rates=rates(reb=10)),
        player("add", schedule=DAYS, current_rates=rates(reb=8)),
    ]
    context, before, after, action = paired(data)
    row = _calculation(context, before, after, action)["reb"]
    assert (row["added_total"], row["lost_total"], row["lineup_other_net"], row["net_total"]) == (32, 40, 0, -8)
    assert plan_waivers(data)["recommended_plan"]["moves"] == []


def test_both_rosters_reverse_current_rebound_lead_140_to_157():
    data = fixture()
    data.update(current_totals=totals(reb=132), opponent_totals=totals(reb=117), available_adds=0)
    data["players"] = [player("us", "user", current_rates=rates(reb=8))] + [
        player(f"them{n}", "opponent", current_rates=rates(reb=8)) for n in range(5)
    ]
    data["lineup_slots"] = ["UTIL"] * 5
    result = plan_waivers(data)
    baseline = result["baseline"]
    assert baseline["user_totals"]["reb"] == 140
    assert baseline["opponent_totals"]["reb"] == 157
    assert baseline["remaining_primitives"]["user"]["reb"] == 8
    assert baseline["remaining_primitives"]["opponent"]["reb"] == 40
    assert result["strategy"]["reb"]["safe_win"] is False


def test_high_assist_zero_point_add_cannot_remove_core_star_without_separate_override():
    data = fixture()
    data.update(selected_categories=FIVE, available_adds=1)
    data["players"] = [
        player("star", "user", [], current_rates=rates(pts=30), season_rank=12, season_rank_source="observed rank"),
        player("add", current_rates=rates(ast=20)),
    ]
    result = plan_waivers(data)
    assert result["recommended_plan"]["moves"] == []
    assert "season rank 12" in result["protected_players"]["star"]
    data["players"][0]["protected"] = False  # User protect false is not a core override.
    assert not plan_waivers(data)["actions"]
    data["players"][0]["core_protection_override"] = True
    assert plan_waivers(data)["actions"][0]["drop_id"] == "star"
    for constraint in ({"locked": True}, {"undroppable": True}, {"droppable": False}, {"protected": True}):
        locked = deepcopy(data)
        locked["players"][0].update(constraint)
        assert not plan_waivers(locked)["actions"]


def test_all_nine_arithmetic_preserves_tradeoffs_and_shooting_volumes():
    data = fixture()
    data.update(dates=DAYS, selected_categories=FIVE, available_adds=1)
    data["current_totals"] = totals(reb=200, pts=0, ast=0)
    data["margin_sd"] = {k: 0.05 if k.endswith("pct") else 30 for k in CATEGORIES}
    data["opponent_totals"] = totals(pts=44, ast=20)
    data["players"] = [
        player("drop", "user", DAYS, current_rates=rates(pts=10, reb=10, fgm=5, fga=10, ftm=2, fta=2, to=3)),
        player("add", schedule=DAYS, current_rates=rates(pts=12, reb=8, ast=6, fgm=3, fga=8, ftm=4, fta=5, to=1.5)),
    ]
    result = plan_waivers(data)
    move = result["recommended_plan"]["moves"][0]
    assert move["gains"]["reb"] == -8
    assert move["gains"]["ast"] == 24
    assert move["gains"]["pts"] == 8
    assert move["gains"]["to"] == -6
    assert set(move["arithmetic"]["categories"]) == set(CATEGORIES)
    for row in move["arithmetic"]["primitives"].values():
        assert row["before"] + row["add"] - row["drop"] + row["spillover"] == pytest.approx(row["after"])
    fg = move["arithmetic"]["categories"]["fg_pct"]
    assert fg["after"] == pytest.approx(fg["makes"]["after"] / fg["attempts"]["after"])
    assert fg["percentage_points"] < 0
    assert move["category_impacts"]["to"]["margin_after"] > move["category_impacts"]["to"]["margin_before"]
    assert result["baseline"]["opponent_totals"] == result["projected"]["opponent_totals"]


def test_one_acquisition_yields_one_exact_pair_and_all_legal_drops_are_evaluated():
    data = fixture()
    data.update(available_adds=1, used_adds=6)
    data["players"] += [player("drop2", "user", []), player("add", current_rates=rates(ast=6))]
    result = plan_waivers(data)
    assert len(result["recommended_plan"]["moves"]) == 1
    assert result["actions"][0]["add_id"] == "add"
    assert result["actions"][0]["drop_id"] in {"drop", "drop2"}
    assert result["search"]["evaluated_drop_ids"] == ["drop", "drop2"]
    assert result["recommended_plan"]["budget_after"] == 0
    assert result["search"]["category_sets_evaluated"] == 126


def test_joint_plan_ownership_effective_dates_budget_and_telescoping_arithmetic():
    data = fixture()
    data.update(max_stream_slots=1, beam_width=32)
    data["players"] += [
        player("first", current_rates=rates(ast=5)),
        player("second", schedule=["2026-11-02"], earliest_add_date="2026-11-02", current_rates=rates(stl=5)),
    ]
    result = plan_waivers(data)
    moves = result["recommended_plan"]["moves"]
    assert [(m["add_id"], m["drop_id"], m["date"]) for m in moves] == [
        ("first", "drop", "2026-11-01"),
        ("second", "first", "2026-11-02"),
    ]
    assert moves[0]["score_after"] == moves[1]["score_before"]
    assert result["remaining_adds"] == 0
    for k in TOTALS:
        assert sum(m["gains"][k] for m in moves) == pytest.approx(
            result["recommended_plan"]["arithmetic"]["primitives"][k]["net"]
        )
    assert result["projected"]["games"]["user"] == 2


def test_equal_plans_are_deterministic_independent_of_input_order():
    data = fixture()
    data["available_adds"] = 1
    data["players"] += [player("z", current_rates=rates(ast=5)), player("a", current_rates=rates(ast=5))]
    first = plan_waivers(data)
    data["players"].reverse()
    second = plan_waivers(data)
    assert first["recommended_plan"] == second["recommended_plan"]
    assert first["actions"][0]["add_id"] == "a"


@pytest.mark.parametrize("gap", ["data_gaps", "projection_metadata", "shooting"])
def test_missing_required_evidence_clears_every_confidence_label(gap):
    data = fixture()
    data["current_totals"] = totals(reb=1000)
    if gap == "data_gaps":
        data[gap] = ["opponent schedule missing"]
    elif gap == "projection_metadata":
        data[gap] = {"history": {"complete": False, "reason": "missing daily slots"}}
    else:
        data["current_totals"].update(fgm=0, fga=0)
    result = plan_waivers(data)
    assert result["status"] == "incomplete"
    assert result["recommended_plan"] is None
    assert result["safe_categories"] == []
    assert not result["actions"]
    for category in result["strategy"].values():
        assert category["classification"] == "unknown"
        assert category["estimate"] is None and category["safe_win"] is False
    assert all(c["attainability"] == "unknown" for c in result["baseline"]["categories"].values())


def test_displaced_starts_are_spillover_not_hidden_drop_loss():
    data = fixture()
    data.update(dates=DAYS, selected_categories=FIVE)
    data["players"] = [
        player("drop", "user", DAYS[:2], current_rates=rates(pts=10)),
        player("bench", "user", DAYS, current_rates=rates(pts=8)),
        player("add", schedule=DAYS, current_rates=rates(pts=10)),
    ]
    context, before, after, action = paired(data)
    move = _describe_move(context, before, after, action, FIVE)
    row = move["arithmetic"]["primitives"]["pts"]
    assert (row["add"], row["drop"], row["spillover"], row["net"]) == (40, 20, -16, 4)
    assert move["lineup_changes"]["net_starts"] == -2
    assert move["lineup_changes"]["recovered"] == []
    assert [row["player_id"] for row in move["lineup_changes"]["displaced"]] == ["bench", "bench"]


def test_no_benefit_empty_plan_and_zero_start_drop_explanation():
    data = fixture()
    result = plan_waivers(data)
    assert result["recommended_plan"]["moves"] == []
    assert result["recommended_plan"]["acquisitions"] == 0
    data["players"].append(player("add", current_rates=rates(ast=5)))
    move = plan_waivers(data)["recommended_plan"]["moves"][0]
    assert move["drop_starts"] == 0
    assert "no remaining scheduled" in move["zero_drop_reason"]
    assert move["arithmetic"]["primitives"]["ast"]["add"] == move["gains"]["ast"]
    data["players"][0]["current_rates"] = None
    assert plan_waivers(data)["status"] == "unavailable"


def test_cushion_and_viability_guard_prevents_hidden_points_sacrifice():
    data = fixture()
    data.update(selected_categories=FIVE, available_adds=1, allow_core_drops=True)
    data["current_totals"] = totals(pts=0, ast=0, stl=0, blk=0)
    data["opponent_totals"] = totals(pts=25, ast=5, stl=5, blk=5)
    data["players"] = [
        player("drop", "user", current_rates=rates(pts=30)),
        player("add", current_rates=rates(ast=20, stl=20, blk=20)),
    ]
    assert not plan_waivers(data)["actions"]  # PTS cushion would be destroyed.
    data["aggressive_cushion_sacrifice"] = True
    move = plan_waivers(data)["actions"][0]
    assert move["gains"]["pts"] == -30
    assert move["category_impacts"]["pts"]["estimate_gain"] < 0


def test_adapter_data_actuals_gate_season_rate_basis_and_ir_legal_drop():
    data = snapshot()
    user = data["teams"][0]
    user["actuals"] = {
        "forecast_complete": True,
        "forecast_source": "NBA verified daily slots",
        "forecast_totals": totals(ast=11),
    }
    ir = user["roster"][0]
    ir.update(lineup_slot="IR", active=False, season_rank=None)
    ir["season_rates"] = rates(pts=1)
    ir["rate_provenance"] = {"source": "NBA", "small_sample": True}
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["baseline"]["totals"]["ast"] == 11
    assert result["baseline"]["games"] == 0
    assert result["actions"][0]["drop_id"] == "drop"
    assert result["actions"][0]["zero_drop_reason"].startswith("Drop is inactive/IR")
    assert user["totals"]["ast"] == 20  # Official ESPN unchanged.
    assert result["provenance"]["rate_basis:drop"]["source"] == "NBA"
    user["actuals"]["forecast_complete"] = False
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["status"] == "incomplete"
    assert result["safe_categories"] == [] and not result["actions"]


def test_nonbeneficial_prefixes_are_explored_for_complementary_sequences():
    data = fixture()
    data.update(beam_width=32, selected_categories=FIVE)
    # Each move is below the material threshold, but the joint gain clears it.
    data["players"] = [player("drop", "user", []), player("other", "user", [])]
    data["players"] += [player("a", current_rates=rates(ast=0.2)), player("b", current_rates=rates(stl=0.2))]
    data["lineup_slots"] = ["UTIL", "UTIL"]
    one = deepcopy(data)
    one["available_adds"] = 1
    assert not plan_waivers(one)["actions"]
    result = plan_waivers(data)
    assert len(result["actions"]) == 2
    assert result["recommended_plan"]["net_score_gain"] >= 0.005


def test_gross_unusable_free_agent_does_not_pick_categories_or_claim_recovery():
    data = fixture()
    data["available_adds"] = 1
    data["current_totals"] = totals(pts=8, reb=8)
    data["players"][0].update(positions=["C"])
    data["lineup_slots"] = ["C"]
    data["players"] += [player("unusable", current_rates=rates(ast=1000))]
    result = plan_waivers(data)
    assert not result["actions"]
    assert result["strategy"]["ast"]["can_flip_with_one_move"] is False
    assert result["recommended_plan"]["net_score_gain"] == 0


def test_effective_dates_transaction_locks_and_independent_daily_slots():
    data = fixture()
    data["players"] += [
        player("add", schedule=data["dates"], current_rates=rates(ast=6), earliest_add_date="2026-11-02"),
        player("opponent", "opponent", schedule=data["dates"], current_rates=rates(reb=7)),
    ]
    data["opponent_lineup_slots_by_date"] = {"2026-11-01": []}
    result = plan_waivers(data)
    assert result["actions"][0]["date"] == "2026-11-02"
    assert result["baseline"]["remaining_primitives"]["opponent"]["reb"] == 7
    data["players"][0]["transaction_locked_dates"] = ["2026-11-02"]
    assert not plan_waivers(data)["actions"]
    data["players"][0]["transaction_locked_dates"] = []
    data["players"][1]["available_from"] = "2026-11-03"
    assert not plan_waivers(data)["actions"]


def test_confirmed_final_actuals_use_exact_wins_losses_and_ties():
    data = fixture()
    data.update(dates=[], matchup_finalized=True)
    data["current_totals"] = totals(pts=11, reb=9)
    result = plan_waivers(data)
    cats = result["baseline"]["categories"]
    assert cats["pts"]["model_edge"] == 1
    assert cats["reb"]["model_edge"] == 0
    assert cats["ast"]["model_edge"] == 0  # Actual tie never becomes a half-win.
    assert cats["ast"]["estimate_kind"] == "final actual comparison"
    assert result["baseline"]["win_at_least_five_probability"] == 0
    assert not result["actions"]


def test_partial_market_is_disclosed_without_fabricating_roster_gaps():
    data = fixture()
    data["market_complete"] = False
    data["players"].append(player("add", current_rates=rates(ast=5)))
    result = plan_waivers(data)
    assert result["status"] == "ready"
    assert result["search"]["upstream_market_complete"] is False
    assert result["search"]["first_layer_complete"] is True
    assert result["search"]["first_layer_pairs_evaluated"] == 1
    assert any("market" in limitation for limitation in result["limitations"])


def test_user_started_slot_cap_does_not_consume_opponent_capacity():
    data = fixture()
    data.update(available_adds=0, lineup_slots_by_date={"2026-11-01": []})
    data["players"] += [player("opponent", "opponent", current_rates=rates(ast=7))]
    result = plan_waivers(data)
    assert result["baseline"]["games"] == {"user": 0, "opponent": 1}


def test_manual_five_counts_its_cushions_even_when_other_cushions_are_stronger():
    data = fixture()
    data.update(available_adds=0, selected_categories=["pts", "reb", "ast", "stl", "threes"])
    data["current_totals"] = totals(pts=100, reb=100, ast=100, stl=100, blk=100, threes=20, to=0)
    result = plan_waivers(data)
    assert set(result["safe_categories"]) == set(data["selected_categories"])
    assert result["strategy"]["threes"]["safe_win"] is True


def test_data_prior_selected_sample_and_cap_fallback_keep_exact_provenance():
    data = snapshot()
    data["league"]["acquisition_settings"].update(weekly_add_limit=7, cap_source="league_fallback_7")
    user = data["teams"][0]
    user.update(weekly_used_adds=6, remaining_adds=1)
    p = user["roster"][0]
    p.update(current_games=0, current_rates=None, prior_rates=rates(ast=1), season_rates=rates(ast=3))
    p["rate_provenance"] = {"source": "espn_prior_season", "season": "2025-26", "games": 60}
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["baseline"]["totals"]["ast"] == 23
    assert "espn_prior_season" in result["provenance"]["rates"]["drop"]
    assert "league_fallback_7" in result["provenance"]["counts"]
    assert result["provenance"]["acquisition_cap"]["source"] == "league_fallback_7"


def test_negative_first_step_can_support_best_joint_chronological_plan():
    data = fixture()
    data.update(beam_width=32, max_stream_slots=1, selected_categories=FIVE)
    data["current_totals"] = totals(pts=0)
    data["opponent_totals"] = totals(pts=4)
    data["margin_sd"] = {k: 0.05 if k.endswith("pct") else 20 for k in CATEGORIES}
    data["players"] = [
        player("drop", "user", data["dates"], current_rates=rates(pts=2)),
        player("first", current_rates=rates(ast=3)),
        player("second", schedule=["2026-11-02"], current_rates=rates(stl=8)),
    ]
    result = plan_waivers(data)
    assert [m["add_id"] for m in result["actions"]] == ["first", "second"]
    assert result["actions"][0]["net_score"] < 0
    assert result["recommended_plan"]["net_score_gain"] >= 0.005
