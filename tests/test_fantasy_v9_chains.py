"""Dated acquisition efficiency, using the same final-horizon lineup engine."""

from copy import deepcopy

import pytest

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, plan_waivers
from tests.test_fantasy_optimizer import fixture, player, rates
from tests.test_fantasy_v8_lineups import reconcile

DAYS = ["2026-11-06", "2026-11-07", "2026-11-08"]
FIVE = ["reb", "ast", "stl", "threes", "to"]


def chain(interim=0):
    data = fixture()
    data.update(dates=DAYS, selected_categories=FIVE, max_stream_slots=1)
    data["players"] = [
        player("root", "user", [], name="Jalen Green"),
        player(
            "interim",
            schedule=[DAYS[0]],
            name="Sam Merrill",
            current_rates=rates(reb=interim, ast=interim, stl=interim / 2, threes=interim),
        ),
        player(
            "final", schedule=[DAYS[-1]], name="Derrick Jones Jr.", current_rates=rates(reb=3, ast=3, stl=2, threes=3)
        ),
        player("opp", "opponent", [DAYS[1]], current_rates=rates(reb=1, ast=1, stl=1, threes=1)),
    ]
    return data


def check(result, data):
    assert result["status"] == "ready"
    reconcile(result, data)
    assert result["search"]["evaluations"] <= result["search"]["evaluation_limit"]
    assert result["remaining_adds"] == data["available_adds"] - len(result["actions"])
    for move in result["actions"]:
        dates = [
            r["date"]
            for r in result["projected"]["starts"]
            if r["owner"] == "user" and r["player_id"] == move["add_id"]
        ]
        assert move["realized"]["dates"] == dates
        for k in TOTALS:
            expected = next(p for p in data["players"] if p["id"] == move["add_id"])["current_rates"][k] * len(dates)
            assert move["realized"]["primitives"][k] == pytest.approx(expected)
    for k in TOTALS:
        row = result["recommended_plan"]["arithmetic"]["primitives"][k]
        assert row["before"] + row["add"] - row["drop"] + row["spillover"] == pytest.approx(row["after"])


@pytest.mark.parametrize("interim", [0, 0.001, 0.02])
def test_no_or_immaterial_interim_production_uses_one_add(interim):
    data = chain(interim)
    result = plan_waivers(data)
    check(result, data)
    assert [(m["drop_id"], m["add_id"]) for m in result["actions"]] == [("root", "final")]
    assert result["remaining_adds"] == 1


def test_material_interim_production_retained_with_dates_and_extra_acquisition():
    data = chain(2)
    result = plan_waivers(data)
    check(result, data)
    assert [m["add_id"] for m in result["actions"]] == ["interim", "final"]
    assert result["actions"][0]["date"] == DAYS[0]
    assert result["actions"][0]["realized"]["until"] <= DAYS[-1]
    assert "extra acquisition" in result["actions"][0]["chain_reason"]
    assert result["recommended_plan"]["acquisitions"] == 2
    assert result["shortcut_comparisons"]
    assert all(c["acquisitions"] < 2 for c in result["shortcut_comparisons"])
    assert result["projected"]["actual_primitives"] == result["baseline"]["actual_primitives"]


@pytest.mark.parametrize("field,value", [("earliest_add_date", DAYS[-1]), ("transaction_locked_dates", DAYS[:2])])
def test_direct_timing_rules_not_bypassed(field, value):
    data = chain(2)
    data["players"][2][field] = value
    result = plan_waivers(data)
    check(result, data)
    final = next(m for m in result["actions"] if m["add_id"] == "final")
    assert final["date"] == DAYS[-1]


def test_non_free_agent_and_protected_root_not_shortcut_candidates():
    data = chain(2)
    data["players"][2]["owner"] = "other"
    assert all(m["add_id"] != "final" for m in plan_waivers(data)["actions"])
    data["players"][0]["protected"] = True
    assert not plan_waivers(data)["actions"]


def test_same_day_zero_production_cannot_waste_add_or_readd():
    data = chain(2)
    data["players"][1]["schedule"] = [DAYS[-1]]
    result = plan_waivers(data)
    check(result, data)
    assert len(result["actions"]) == 1
    assert len({m["add_id"] for m in result["actions"]}) == len(result["actions"])


def test_ten_occupied_slots_remove_false_interim_value():
    data = chain(2)
    data["lineup_slots"] = ["UTIL"] * 10
    data["margin_sd"] = {k: 0.05 if k.endswith("pct") else 25 for k in CATEGORIES}
    for n in range(10):
        data["players"].append(
            player(
                f"occupied{n}", "user", [DAYS[0]], protected=True, current_rates=rates(reb=3, ast=3, stl=2, threes=3)
            )
        )
    result = plan_waivers(data)
    check(result, data)
    assert len(result["actions"]) == 1
    assert result["actions"][0]["add_id"] == "final"


def test_negative_shooting_and_turnovers_are_in_comparison_all_nine():
    data = chain(2)
    data["players"][1]["current_rates"].update(to=50, fgm=0, fga=30, ftm=0, fta=30)
    data["selected_categories"] = ["reb", "stl", "to", "fg_pct", "ft_pct"]
    result = plan_waivers(data)
    check(result, data)
    assert len(result["actions"]) <= 1
    assert set(result["recommended_plan"]["arithmetic"]["categories"]) == set(CATEGORIES)


def test_small_budget_never_silently_runs_postprocessing_forecasts():
    data = chain(2)
    data["evaluation_limit"] = 3
    result = plan_waivers(data)
    check(result, data)
    assert result["search"]["evaluations"] <= 3
    assert len(result["actions"]) <= 1 or result["search"]["shortcut_verification_complete"]


def test_same_terminal_roster_can_have_different_interim_production():
    first = plan_waivers(chain(0))
    second = plan_waivers(chain(2))
    assert first["actions"][-1]["add_id"] == second["actions"][-1]["add_id"]
    assert second["projected"]["user_totals"]["reb"] > first["projected"]["user_totals"]["reb"]
    assert deepcopy(first)["recommended_plan"]["acquisitions"] == 1


def test_missing_direct_path_is_explicitly_replayed_despite_candidate_and_beam_bounds():
    data = chain(4)
    data.update(candidate_limit=1, beam_width=1, evaluation_limit=6)
    data["lineup_slots"] = ["PG"]
    # Optimistic candidate ordering overvalues an unusable PF-only stream.
    data["players"][1].update(positions=["PF"], strict_positions=True, schedule=DAYS[:2], core_protection_override=True)
    result = plan_waivers(data)
    check(result, data)
    assert [(m["drop_id"], m["add_id"]) for m in result["actions"]] == [("root", "final")]
    assert not result["search"]["first_layer_complete"]
    assert result["search"]["shortcut_evaluations"] > 0
