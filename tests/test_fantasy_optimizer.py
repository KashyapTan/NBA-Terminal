"""Synthetic, deterministic league fixtures; no live data or transactions."""

from copy import deepcopy

import pytest

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, plan_waivers


def totals(**changes):
    return {**dict.fromkeys(TOTALS, 10), "fgm": 40, "fga": 80, "ftm": 20, "fta": 25, **changes}


def rates(**changes):
    return {**dict.fromkeys(TOTALS, 0), "minutes": 20, **changes}


def player(pid, owner="free", schedule=None, **changes):
    return {
        "id": pid,
        "locked": False,
        "owner": owner,
        "positions": ["PG"],
        "schedule": schedule if schedule is not None else ["2026-11-01"],
        "current_rates": rates(),
        "current_games": 20,
        **changes,
    }


def fixture():
    return {
        "dates": ["2026-11-01", "2026-11-02"],
        "current_totals": totals(),
        "opponent_totals": totals(),
        "players": [player("drop", "user", [])],
        "lineup_slots": ["UTIL"],
        "weekly_add_limit": 7,
        "used_adds": 5,
        "available_adds": 2,
        "margin_sd": {k: 0.05 if k.endswith("pct") else 5 for k in CATEGORIES},
    }


def test_no_inputs_and_unknown_uncertainty():
    assert plan_waivers({})["status"] == "unavailable"
    assert plan_waivers(None)["status"] == "unavailable"
    data = fixture()
    del data["margin_sd"]
    result = plan_waivers(data)
    assert result["status"] == "ready"
    assert result["actions"] == []
    assert result["uncertainty"]["source"] == "model_estimate"
    assert result["uncertainty"]["calibrated"] is False


def test_category_direction_and_weighted_shooting():
    data = fixture()
    data["players"] = [player("starter", "user", current_rates=rates(to=3, fgm=1, fga=10, ftm=1, fta=2))]
    data["available_adds"] = 0
    forecast = plan_waivers(data)["baseline"]
    assert forecast["categories"]["to"]["state"] == "losing"
    assert forecast["categories"]["to"]["margin"] == -3
    assert forecast["categories"]["fg_pct"]["user"] == pytest.approx(41 / 90)
    assert forecast["categories"]["ft_pct"]["user"] == pytest.approx(21 / 27)
    assert forecast["categories"]["pts"]["state"] == "tied"


def test_zero_attempts_are_unknown_not_zero_percent():
    data = fixture()
    data["current_totals"] = totals(fgm=0, fga=0)
    result = plan_waivers(data)
    assert result["status"] == "incomplete"
    assert result["baseline"]["categories"]["fg_pct"]["user"] is None
    assert result["actions"] == []


def test_swing_beats_hopeless_punt_and_minutes():
    data = fixture()
    data["current_totals"] = totals(pts=0, ast=9)
    data["opponent_totals"] = totals(pts=1000)
    data["players"] += [
        player("volume", current_rates=rates(pts=50, minutes=40)),
        player("swing", current_rates=rates(ast=8, minutes=15)),
    ]
    data["available_adds"] = 1
    result = plan_waivers(data)
    assert result["actions"][0]["add_id"] == "swing"
    assert result["projected"]["win_at_least_five_probability"] > result["baseline"]["win_at_least_five_probability"]
    assert result["projected"]["categories"]["pts"]["attainability"] == "unlikely"


def test_sequential_rotation_counts_games_once_and_respects_budget():
    data = fixture()
    data["max_stream_slots"] = 1
    data["players"] += [
        player("first", current_rates=rates(ast=5)),
        player("second", schedule=["2026-11-02"], current_rates=rates(stl=5)),
    ]
    original = deepcopy(data)
    result = plan_waivers(data)
    assert data == original
    assert len(result["actions"]) == 2
    assert len({a["add_id"] for a in result["actions"]}) == 2
    assert len({a["stream_slot"] for a in result["actions"]}) == 1
    assert result["projected"]["games"]["user"] == 2
    assert result["projected"]["user_totals"]["ast"] == 15
    assert result["projected"]["user_totals"]["stl"] == 15
    assert result["remaining_adds"] == 0
    data["used_adds"] = 6
    data["available_adds"] = 1
    assert len(plan_waivers(data)["actions"]) == 1
    data["used_adds"] = 7
    data["available_adds"] = 0
    assert plan_waivers(data)["actions"] == []


@pytest.mark.parametrize(
    "change",
    [
        {"locked": True},
        {"injury_status": "out"},
        {"eligible": False},
        {"owner": "other"},
        {"unavailable_dates": ["2026-11-01"]},
    ],
)
def test_unavailable_candidates_never_added(change):
    data = fixture()
    data["players"].append(player("unavailable", current_rates=rates(ast=50), **change))
    assert plan_waivers(data)["actions"] == []


def test_roster_locks_and_disabled_stream_slots():
    data = fixture()
    data["players"][0]["locked"] = True
    data["players"].append(player("free", current_rates=rates(ast=5)))
    assert plan_waivers(data)["actions"] == []
    data["players"][0]["locked"] = False
    data["max_stream_slots"] = 0
    assert plan_waivers(data)["actions"] == []


def test_lineup_crowding_and_position_matching():
    data = fixture()
    data["players"] = [
        player("pg", "user", current_rates=rates(ast=10)),
        player("center", "user", positions=["C"], current_rates=rates(blk=10)),
        player("bench", "user", current_rates=rates(pts=1)),
        player("free", current_rates=rates(pts=1)),
    ]
    data["lineup_slots"] = ["UTIL", "C"]
    data["available_adds"] = 0
    result = plan_waivers(data)
    starts = result["baseline"]["starts"]
    assert {s["player_id"] for s in starts} == {"pg", "center"}
    assert result["baseline"]["games"]["user"] == 2
    data["lineup_slots_by_date"] = {"2026-11-01": ["C"]}
    assert plan_waivers(data)["baseline"]["games"]["user"] == 1


def test_already_rostered_and_no_schedule_do_not_enter_plan():
    data = fixture()
    data["players"] += [
        player("opponent", "opponent", current_rates=rates(ast=30)),
        player("offday", schedule=[], current_rates=rates(ast=100)),
    ]
    assert plan_waivers(data)["actions"] == []


def test_prior_stats_and_history_provenance():
    data = fixture()
    data["players"][0].update(
        current_games=2, current_rates=rates(ast=10), prior_rates=rates(ast=5), schedule=["2026-11-01"]
    )
    del data["margin_sd"]
    data["prior_week_margins"] = [{k: n for k in CATEGORIES} for n in (1, 2, 3)]
    result = plan_waivers(data)
    assert result["status"] == "ready"
    assert "prior season fallback" in result["provenance"]["drop"]
    assert result["baseline"]["user_totals"]["ast"] == 15
    data["players"][0].pop("current_rates")
    assert plan_waivers(data)["provenance"]["drop"] == "prior season fallback"


@pytest.mark.parametrize(
    "key,value", [("weekly_add_limit", -1), ("used_adds", True), ("margin_sd", {}), ("lineup_slots", [])]
)
def test_invalid_inputs_fail_closed(key, value):
    data = fixture()
    data[key] = value
    assert plan_waivers(data)["status"] == "unavailable"


def test_data_gaps_suppress_recommendations():
    data = fixture()
    data["data_gaps"] = ["Schedule incomplete"]
    assert plan_waivers(data)["status"] == "incomplete"


def test_percentages_can_make_volume_add_harmful():
    data = fixture()
    data["players"].append(player("bad", current_rates=rates(fga=100, fta=100, to=40)))
    assert plan_waivers(data)["actions"] == []


@pytest.mark.parametrize("field", ["locked", "used_adds", "weekly_add_limit", "available_adds"])
def test_unknown_constraints_are_not_false_or_zero(field):
    data = fixture()
    if field == "locked":
        data["players"][0][field] = None
    else:
        data[field] = None
    result = plan_waivers(data)
    assert result["status"] == ("ready" if field == "locked" else "incomplete")
    if field != "locked":
        assert result["remaining_adds"] is None and not result["actions"]


def test_evaluation_limit_is_reported_and_deterministic():
    data = fixture()
    data["evaluation_limit"] = 1
    data["players"] += [player("one", current_rates=rates(ast=5)), player("two", current_rates=rates(blk=5))]
    first = plan_waivers(data)
    assert first == plan_waivers(deepcopy(data))
    assert first["search"] == {"evaluations": 1, "evaluation_limit_reached": True}


def test_drop_cannot_invent_zero_attempt_probability():
    data = fixture()
    data["current_totals"] = totals(fgm=0, fga=0, ftm=0, fta=0)
    data["players"] = [
        player("only_shooter", "user", current_rates=rates(fgm=1, fga=2, ftm=1, fta=2)),
        player("no_shots", current_rates=rates(ast=100)),
    ]
    result = plan_waivers(data)
    assert result["status"] == "ready"
    assert result["actions"] == []


def test_single_stream_slot_cannot_be_two_concurrent_roster_spots():
    data = fixture()
    data["players"] += [
        player("second_drop", "user", []),
        player("one", current_rates=rates(ast=6)),
        player("two", current_rates=rates(blk=6)),
    ]
    data["lineup_slots"] = ["UTIL", "UTIL"]
    data["max_stream_slots"] = 1
    result = plan_waivers(data)
    assert len({a["stream_slot"] for a in result["actions"]}) == 1
    assert len(result["actions"]) == 1


def test_prior_only_small_sample_and_missing_rates():
    data = fixture()
    data["players"][0]["current_games"] = 1
    assert "small current sample" in plan_waivers(data)["provenance"]["drop"]
    data["players"][0]["current_games"] = 0
    assert plan_waivers(data)["status"] == "unavailable"
    data["players"][0].pop("current_rates")
    assert plan_waivers(data)["status"] == "unavailable"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["current_totals"].update(fga=0),
        lambda p: p["current_totals"].update(pts=float("nan")),
        lambda p: p["dates"].append(p["dates"][0]),
        lambda p: p["players"].append(deepcopy(p["players"][0])),
        lambda p: p["players"][0].update(owner="unknown"),
        lambda p: p["players"][0].update(positions=[]),
        lambda p: p.update(lineup_slots_by_date={"2020-01-01": ["PG"]}),
        lambda p: p.update(players=[]),
        lambda p: p.update(data_gaps=None),
    ],
)
def test_malformed_primitives_fail_closed(mutate):
    data = fixture()
    mutate(data)
    assert plan_waivers(data)["status"] == "unavailable"
