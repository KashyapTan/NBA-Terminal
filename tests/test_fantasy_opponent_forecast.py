"""Opponent policy regressions; synthetic data is not private league verification."""

from copy import deepcopy
from itertools import combinations

import pytest

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, _context, _lineup, plan_waivers
from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers
from tests.test_fantasy_integration import preferences
from tests.test_fantasy_optimizer import fixture, player, rates
from tests.test_fantasy_v6_engine import NOW, chain
from tests.test_fantasy_v7_schedule import provider as provider
from tests.test_fantasy_v8_lineups import FIVE, SHOTS, crowded, reconcile


def ledger(result):
    return [s for s in result["baseline"]["starts"] if s["owner"] == "opponent"]


def test_opponent_uses_all_playing_bench_players_even_when_focus_would_bench_them():
    data = fixture()
    data.update(selected_categories=SHOTS, available_adds=0)
    data["players"] += [
        player(
            "big",
            "opponent",
            current_rates=rates(pts=30, reb=15, ast=6, to=12, fgm=1, fga=10, ftm=1, fta=10),
            lineup_slot="BENCH",
        ),
    ]
    # Every selected category except STL is harmed or unchanged by this player.
    result = plan_waivers(data)
    assert ledger(result) == [{"date": "2026-11-01", "owner": "opponent", "player_id": "big", "assigned_slot": "UTIL"}]
    assert result["baseline"]["opponent_totals"]["pts"] == 40
    assert result["baseline"]["categories"]["to"]["opponent"] == 22
    assert result["baseline"]["categories"]["fg_pct"]["opponent"] == pytest.approx(41 / 90)
    assert result["baseline"]["categories"]["ft_pct"]["opponent"] == pytest.approx(21 / 35)
    reconcile(result, data)


def test_focus_discovery_explicit_focus_and_user_counterfactuals_share_one_opponent_ledger():
    data = crowded()
    automatic = deepcopy(data)
    automatic.pop("selected_categories")
    results = [plan_waivers(d) for d in (data, data | {"selected_categories": SHOTS}, automatic)]
    for result in results:
        reconcile(result, data)
        assert ledger(result) == ledger(results[0])
        assert result["baseline"]["opponent_totals"] == results[0]["baseline"]["opponent_totals"]
        assert result["projected"]["opponent_totals"] == result["baseline"]["opponent_totals"]
        assert all(
            r["focus"] == list(CATEGORIES) for r in result["baseline"]["daily_lineups"] if r["owner"] == "opponent"
        )
    # Focus auto-discovery and explicit replay must agree on the frozen opponent.
    replay = plan_waivers(automatic | {"selected_categories": results[-1]["selected_categories"]})
    assert replay["baseline"] == results[-1]["baseline"]


def test_crowded_opponent_matching_has_maximum_legal_cardinality_and_ranked_all_nine_value():
    data = crowded()
    context = _context(data)
    players = [p for p in context["players"].values() if p["owner"] == "opponent"][:5]
    players[-1]["positions"] = ["C"]
    slots = ["PG", "C", "UTIL"]
    chosen = _lineup(players, slots, context["ours"], context["theirs"], context["sd"], opponent=True, selected=SHOTS)
    assert len(chosen) == 3
    assert any(p["assigned_slot"] == "C" for p in chosen)
    # Independent enumeration: feasible size-three subsets include the sole C.
    from nba_terminal.services.fantasy_optimizer import _assessment

    def value(p):
        before, _ = _assessment(context["theirs"], context["ours"], context["sd"])
        after, _ = _assessment(
            {k: context["theirs"][k] + p["rates"][k] for k in TOTALS}, context["ours"], context["sd"]
        )
        return sum(after[k]["win_probability"] - before[k]["win_probability"] for k in CATEGORIES)

    oracle = max(sum(value(p) for p in group) for group in combinations(players, 3) if players[-1] in group)
    assert sum(value(p) for p in chosen) == pytest.approx(oracle)
    result = plan_waivers(data)
    assert len(ledger(result)) == 10
    reconcile(result, data)


def test_future_starters_bench_and_unset_assignments_do_not_change_adapter_forecast():
    snapshot = chain()
    opponent = snapshot["teams"][1]["roster"]
    prefs = preferences(snapshot)
    results = []
    for slot in ("UTIL", "BENCH", None):
        for p in opponent:
            p["lineup_slot"] = slot
        result = plan_snapshot_waivers(snapshot, prefs, NOW)
        assert result["status"] == "ready", result["reasons"]
        results.append(result)
    assert (
        results[0]["baseline"]["opponent_totals"]
        == results[1]["baseline"]["opponent_totals"]
        == results[2]["baseline"]["opponent_totals"]
    )
    assert ledger(results[0]) == ledger(results[1]) == ledger(results[2])
    assert results[0]["baseline"]["opponent_totals"] == results[0]["projected"]["opponent_totals"]


@pytest.mark.parametrize("state", ["ir", "out", "missing_positions"])
def test_opponent_ineligible_or_unknown_players_are_never_promoted(state):
    snapshot = chain()
    p = snapshot["teams"][1]["roster"][0]
    if state == "ir":
        p.update(lineup_slot="IR", active=False)
    elif state == "out":
        p.update(health_status="out")
    else:
        p["positions"] = []
    result = plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert not [s for s in ledger(result) if s["player_id"] == p["id"]]
    if state == "missing_positions":
        assert result["status"] == "incomplete"
        assert any("eligibility" in g for g in result["data_gaps"])


@pytest.mark.parametrize("slot,reserved", [("UTIL", 1), ("BENCH", 0)])
def test_started_opponent_starter_or_bench_stays_banked_and_never_reprojected(slot, reserved):
    snapshot = chain()
    p = snapshot["teams"][1]["roster"][0]
    p["lineup_slot"] = slot
    day = snapshot["period"]["remaining_dates"][0]
    p["schedule"][0].update(date=day, started=True, start_at=NOW.isoformat())
    banked = deepcopy(snapshot["teams"][1]["totals"])
    result = plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    forecast = result["baseline"]
    assert forecast["actual_primitives"]["opponent"] == {k: banked[k] for k in TOTALS}
    assert not [s for s in ledger(result) if s["player_id"] == p["id"] and s["date"] == day]
    row = next(d for d in forecast["daily_lineups"] if d["owner"] == "opponent" and d["date"] == day)
    assert row["available_slots"] == row["capacity"] - reserved
    assert sum(p["state"] == "locked" for p in row["players"]) == reserved


def test_equivalent_refresh_is_stable_and_opponent_roster_rate_schedule_changes_are_observed():
    data = fixture()
    data["players"] += [player("opp", "opponent", current_rates=rates(pts=20, to=3))]
    first = plan_waivers(data)
    assert plan_waivers(deepcopy(data))["baseline"] == first["baseline"]
    changed = deepcopy(data)
    changed["players"][-1]["current_rates"]["pts"] = 30
    assert plan_waivers(changed)["baseline"]["opponent_totals"]["pts"] == 40
    changed["players"][-1]["schedule"].append("2026-11-02")
    assert len(ledger(plan_waivers(changed))) == 2
    changed["players"].pop()
    assert ledger(plan_waivers(changed)) == []


@pytest.mark.parametrize("fallback", [False, True])
def test_provider_normalizer_adapter_future_bench_policy_and_schedule_horizon(provider, fallback):
    raw, state, run = provider
    state["failed"] = fallback
    opponent = next(t for t in raw["league"]["teams"] if t["id"] == 2)
    for entry in opponent["roster"]["entries"]:
        entry["lineupSlotId"] = 12
    snapshot, bench = run()
    assert snapshot["period"]["dates"] == [f"2026-11-{d:02}" for d in range(2, 9)]
    assert snapshot["period"]["schedule_coverage"]["source"] == ("espn_schedule" if fallback else "nba_schedule")
    assert len(ledger(bench)) == 4
    assert bench["baseline"]["opponent_totals"]["pts"] == 20
    for entry in opponent["roster"]["entries"]:
        entry["lineupSlotId"] = 11
    _, starters = run()
    assert ledger(bench) == ledger(starters)
    assert bench["baseline"]["opponent_totals"] == starters["baseline"]["opponent_totals"]


def test_beneficial_real_user_pickup_preserves_every_opponent_date_and_primitive():
    data = fixture()
    data.update(selected_categories=FIVE, available_adds=1)
    data["players"] = [
        player("drop", "user", current_rates=rates(pts=1, ast=1)),
        player("add", current_rates=rates(pts=30, reb=15, ast=10, stl=5, blk=3)),
        player("opp", "opponent", current_rates=rates(pts=20, reb=5, ast=5, to=3)),
    ]
    result = plan_waivers(data)
    assert result["actions"]
    assert result["projected"]["user_totals"] != result["baseline"]["user_totals"]
    for key in ("opponent_totals", "actual_primitives", "remaining_primitives"):
        if key == "opponent_totals":
            assert result["baseline"][key] == result["projected"][key]
        else:
            assert result["baseline"][key]["opponent"] == result["projected"][key]["opponent"]
    assert ledger(result) == [s for s in result["projected"]["starts"] if s["owner"] == "opponent"]
    reconcile(result, data)
