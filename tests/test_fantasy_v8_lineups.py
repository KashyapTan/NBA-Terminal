"""V8 exact daily-decision reconciliation; synthetic, no fantasy writes."""

from collections import Counter
from copy import deepcopy
from itertools import combinations

import pytest

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, _assessment, _context, _lineup, plan_waivers
from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers
from tests.test_fantasy_integration import preferences
from tests.test_fantasy_optimizer import fixture, player, rates, totals
from tests.test_fantasy_v6_engine import NOW, chain

FIVE = ["pts", "reb", "ast", "stl", "blk"]
SHOTS = ["threes", "to", "fg_pct", "ft_pct", "stl"]
DAY = "2026-11-01"


def crowded(n=13, focus=FIVE):
    data = fixture()
    data.update(used_adds=7, available_adds=0, selected_categories=focus)
    data["lineup_slots"] = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "UTIL", "UTIL"]
    data["players"] = []
    for side, count in (("user", n), ("opponent", n - 1)):
        for i in range(count):
            # Highest raw PTS ten lack the mandatory C. Three low volume bigs fit.
            positions = ["PG", "SG", "G"] if i < 8 else ["SF", "PF", "F"] if i < 10 else ["C", "PF", "F"]
            data["players"].append(
                player(
                    f"{side}-{i:02}",
                    side,
                    [DAY],
                    name=f"{side} player {i}",
                    positions=positions,
                    current_rates=rates(
                        pts=20 - i, ast=i, reb=3, stl=1, blk=1, to=0.1, threes=i, fgm=1, fga=2, ftm=1, fta=2
                    ),
                )
            )
    data["current_totals"] = totals(pts=100, ast=40, fgm=20, fga=50, ftm=10, fta=15)
    data["opponent_totals"] = totals(pts=120, ast=20, fgm=45, fga=90, ftm=25, fta=30)
    data["margin_sd"] = {k: 0.1 if k.endswith("pct") else 100 for k in CATEGORIES}
    return data


def reconcile(result, data):
    for scenario in ("baseline", "projected"):
        forecast = result[scenario]
        for owner in ("user", "opponent"):
            selected = []
            for day in forecast["daily_lineups"]:
                if day["owner"] != owner:
                    continue
                assert day["focus"] == (list(CATEGORIES) if owner == "opponent" else result["selected_categories"])
                starts = [p for p in day["players"] if p["state"] == "start"]
                assert len(starts) <= day["capacity"] <= 10
                assert len({p["player_id"] for p in day["players"]}) == len(day["players"])
                assert not (Counter(p["assigned_slot"] for p in starts) - Counter(data["lineup_slots"]))
                for p in starts:
                    assert p["playing"]
                    assert p["assigned_slot"] == "UTIL" or p["assigned_slot"] in p["positions"]
                assert {p["player_id"] for p in starts} == {
                    s["player_id"] for s in forecast["starts"] if s["owner"] == owner and s["date"] == day["date"]
                }
                selected += starts
            target = forecast["user_totals" if owner == "user" else "opponent_totals"]
            for key in TOTALS:
                expected = sum(p["rates"][key] for p in selected)
                assert forecast["remaining_primitives"][owner][key] == pytest.approx(expected)
                assert target[key] == pytest.approx(forecast["actual_primitives"][owner][key] + expected)
            for pct, made, attempts in (("fg_pct", "fgm", "fga"), ("ft_pct", "ftm", "fta")):
                assert forecast["categories"][pct][owner] == pytest.approx(target[made] / target[attempts])


@pytest.mark.parametrize("n", [11, 12, 13])
def test_ten_capacity_positions_both_rosters_and_all_nine_math(n):
    data = crowded(n)
    result = plan_waivers(data)
    assert result["status"] == "ready"
    reconcile(result, data)
    starts = [p for p in result["baseline"]["daily_lineups"][0]["players"] if p["state"] == "start"]
    assert len(starts) == (9 if n == 11 else 10)
    assert any("C" in p["positions"] for p in starts)
    if n >= 12:
        assert any(p["assigned_slot"] == "C" for p in starts)
    assert any(p["state"] == "bench" and p["playing"] for p in result["baseline"]["daily_lineups"][0]["players"])


def test_focus_changes_selection_and_automatic_matches_explicit_replay():
    data = crowded()
    first = plan_waivers(data)
    second = plan_waivers(data | {"selected_categories": SHOTS})

    def ids(r):
        return {s["player_id"] for s in r["baseline"]["starts"] if s["owner"] == "user"}

    assert ids(first) != ids(second)
    reconcile(second, data)
    data.pop("selected_categories")
    automatic = plan_waivers(data)
    replay = plan_waivers(data | {"selected_categories": automatic["selected_categories"]})
    assert automatic["baseline"] == replay["baseline"]
    assert automatic["projected"] == replay["projected"]
    assert automatic["search"]["evaluations"] <= 5000


@pytest.mark.parametrize("n", [0, 7, 10])
def test_no_forced_nonplayers_or_duplicate_starts(n):
    data = crowded(13)
    data["lineup_slots"] = ["UTIL"] * 10
    for i, p in enumerate(data["players"]):
        p["schedule"] = [DAY] if i < n else []
    result = plan_waivers(data)
    assert len([s for s in result["baseline"]["starts"] if s["owner"] == "user"]) == n
    reconcile(result, data)


def test_small_oracle_checks_marginal_matching_score_not_global_week_claim():
    data = crowded(11)
    context = _context(data)
    players = [p for p in context["players"].values() if p["owner"] == "user"][:5]
    slots = ["PG", "UTIL"]
    ours, theirs, sd = context["ours"], context["theirs"], context["sd"]

    def utility(values):
        cats, _ = _assessment(values, theirs, sd)
        return sum(cats[k]["win_probability"] for k in FIVE)

    def score(p):
        return utility({k: ours[k] + p["rates"][k] for k in TOTALS}) - utility(ours)

    chosen = _lineup(players, slots, ours, theirs, sd, selected=FIVE)
    oracle = max(sum(score(p) for p in subset) for subset in combinations(players, 2))
    assert sum(score(p) for p in chosen) == pytest.approx(oracle)


def test_injury_override_banked_locks_and_missing_rules_are_honest():
    snapshot = chain()
    own = snapshot["teams"][0]["roster"][0]
    own["health_status"] = "out"
    pref = preferences(snapshot)
    off = plan_snapshot_waivers(snapshot, pref, NOW)
    assert not [s for s in off["baseline"]["starts"] if s["owner"] == "user"]
    on = plan_snapshot_waivers(snapshot, pref | {"player_overrides": {own["id"]: {"injured": False}}}, NOW)
    assert [s for s in on["baseline"]["starts"] if s["owner"] == "user"]
    # An active game already started in snapshot reserves the slot and is not projected twice.
    game = own["schedule"][0]
    game.update(date=snapshot["period"]["remaining_dates"][0], started=True, start_at=NOW.isoformat())
    locked = plan_snapshot_waivers(snapshot, pref, NOW)
    day = next(d for d in locked["baseline"]["daily_lineups"] if d["owner"] == "user" and d["date"] == game["date"])
    assert len([p for p in day["players"] if p["state"] == "locked"]) == 1
    assert day["available_slots"] == len(snapshot["league"]["lineup_slots"]) - 1
    assert not [s for s in locked["baseline"]["starts"] if s["owner"] == "user" and s["date"] == game["date"]]
    snapshot["league"]["lineup_slots"] = []
    missing = plan_snapshot_waivers(snapshot, pref, NOW)
    assert missing["status"] == "incomplete"
    assert missing["projected"] is None


def test_current_roster_vs_ordered_transaction_dates_and_all_nine_net():
    data = fixture()
    data.update(selected_categories=FIVE, max_stream_slots=1, beam_width=32)
    data["players"] += [
        player("first", current_rates=rates(ast=5)),
        player("second", schedule=["2026-11-02"], current_rates=rates(stl=5)),
    ]
    original = deepcopy(data)
    result = plan_waivers(data)
    assert data == original
    assert len(result["actions"]) == 2
    reconcile(result, data)
    assert all(
        p["player_id"] == "drop"
        for d in result["baseline"]["daily_lineups"]
        if d["owner"] == "user"
        for p in d["players"]
    )
    for action in result["actions"]:
        for d in result["projected"]["daily_lineups"]:
            if d["owner"] == "user" and d["date"] < action["date"]:
                assert action["add_id"] not in {p["player_id"] for p in d["players"]}
    for key in CATEGORIES:
        row = result["recommended_plan"]["arithmetic"]["categories"][key]
        if key.endswith("pct"):
            assert row["after"] == pytest.approx(result["projected"]["categories"][key]["user"])
        else:
            assert row["net"] == pytest.approx(
                result["projected"]["user_totals"][key] - result["baseline"]["user_totals"][key]
            )


def test_negative_focus_benching_is_explicit():
    data = fixture()
    data.update(selected_categories=SHOTS, available_adds=0)
    data["players"] = [player("harm", "user", current_rates=rates(to=20, fga=10, fta=10))]
    result = plan_waivers(data)
    day = result["baseline"]["daily_lineups"][0]
    assert not result["baseline"]["starts"]
    assert day["players"][0]["reason"] == "intentional_focus_bench"
    assert day["available_slots"] == 1


def test_rules_above_user_cap_fail_closed_and_partial_positions_stay_unknown():
    snapshot = chain()
    pref = preferences(snapshot)
    snapshot["league"]["lineup_slots"] = ["UTIL"] * 11
    mismatch = plan_snapshot_waivers(snapshot, pref, NOW)
    assert mismatch["status"] == "incomplete"
    assert "10-player capacity" in mismatch["reasons"][0]
    snapshot["league"]["lineup_slots"] = ["UTIL"] * 10
    snapshot["teams"][0]["roster"][0]["positions"] = []
    partial = plan_snapshot_waivers(snapshot, pref, NOW)
    assert partial["status"] == "incomplete"
    assert any("eligibility is missing" in gap for gap in partial["data_gaps"])
    assert not [s for s in partial["baseline"]["starts"] if s["owner"] == "user"]


def test_frozen_opponent_explanations_are_coherent_across_changed_rosters():
    data = crowded()
    data.update(available_adds=1, used_adds=6, allow_core_drops=True)
    data["players"].append(
        player("super-add", positions=["PG", "SG", "G"], current_rates=rates(pts=100, ast=60, reb=40, stl=10, blk=10))
    )
    result = plan_waivers(data)
    before = [d for d in result["baseline"]["daily_lineups"] if d["owner"] == "opponent"]
    after = [d for d in result["projected"]["daily_lineups"] if d["owner"] == "opponent"]
    assert before == after
    reconcile(result, data)


def test_automatic_focus_does_not_chase_pickups_when_no_acquisition_is_possible():
    data = crowded()
    data.pop("selected_categories")
    expected = plan_waivers(data)
    data["players"].append(player("unobtainable", current_rates=rates(threes=1000, fgm=1000, fga=1000)))
    actual = plan_waivers(data)
    assert actual["selected_categories"] == expected["selected_categories"]
    for key in ("starts", "daily_lineups", "user_totals", "opponent_totals", "categories"):
        assert actual["baseline"][key] == expected["baseline"][key]


def test_observed_espn_eligibility_is_not_expanded_to_an_unreported_util_slot():
    snapshot = chain()
    own = snapshot["teams"][0]["roster"][0]
    assert own["positions_source"] == "espn_eligibleSlots"
    own["positions"] = ["PG"]
    snapshot["league"]["lineup_slots"] = ["UTIL"] * 10
    pref = preferences(snapshot)
    result = plan_snapshot_waivers(snapshot, pref, NOW)
    assert not [s for s in result["baseline"]["starts"] if s["owner"] == "user"]
    day = next(
        d
        for d in result["baseline"]["daily_lineups"]
        if d["owner"] == "user" and any(p["playing"] for p in d["players"])
    )
    assert day["players"][0]["reason"] == "capacity_or_position"
