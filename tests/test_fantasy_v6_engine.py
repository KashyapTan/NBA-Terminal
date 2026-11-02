"""V6 production provider -> normalizer -> adapter -> optimizer regressions (synthetic observations)."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba
from nba_terminal.services import fantasy_planner_adapter as adapter
from nba_terminal.services.fantasy_nba import fetch_team_games as real_fetch_team_games
from nba_terminal.services.fantasy_optimizer import plan_waivers
from tests.fantasy_v6_fixture import team_bundle
from tests.test_fantasy_integration import preferences
from tests.test_fantasy_optimizer import fixture, player, rates

NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
FIVE = ["pts", "reb", "ast", "stl", "blk"]


def chain(gp=2, mpg=30, team_gp=4, prior_only=False, second_free=False):
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    for entry in raw["pool"]["players"] + raw["cards"]["players"]:
        body = espn.player_body(entry)
        for split in body.get("stats", []):
            if split["seasonId"] == 2027:
                split["stats"].update(
                    {"42": gp, "40": gp * mpg, "0": 8 * gp, "3": 6 * gp, "6": 5 * gp, "1": gp, "2": gp}
                )
        if prior_only:
            body["stats"] = [s for s in body["stats"] if s["seasonId"] != 2027]
    if second_free:
        for entry in raw["pool"]["players"]:
            entry.update(status="FREEAGENT", onTeamId=0)
    bundle = team_bundle(NOW.isoformat(), team_gp)
    if team_gp is None:
        bundle["team_games"] = []
    snapshot = espn.normalize(raw["league"], raw["schedule"], raw["pool"], raw["cards"], {}, 1, now=NOW, nba=bundle)
    return snapshot


@pytest.mark.parametrize(
    ("gp", "minutes", "team_gp", "reason"),
    [
        (1, 11, 4, "below_min_minutes"),
        (2, 14.99, 4, "below_min_minutes"),
        (2, 15, 5, "below_min_participation"),
        (2, 15, None, "completed_team_games_unknown"),
        (2, 15, 4, None),
        (3, 30, 5, None),
    ],
)
def test_real_normalizer_qualifies_observed_sample_before_ranking(gp, minutes, team_gp, reason):
    snapshot = chain(gp, minutes, team_gp)
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    summary = result["pickup_filter_summary"]
    if reason:
        assert summary["qualified"] == 0
        assert reason in summary["exclusions"][0]["reasons"]
        assert result["evaluation_state"] == "no_qualified_pickups"
        assert not result["actions"]
    else:
        assert summary["qualified"] == 1  # preferences explicitly select player 100
        assert not summary["exclusions"]
    assert not result["data_gaps"]  # candidate exclusions are not missing own-roster data
    assert result["search"]["legal_drop_ids"] == ["1"]


def test_prior_projection_fallback_cannot_supply_current_qualification():
    snapshot = chain(prior_only=True)
    assert snapshot["free_agents"][0]["season_rates"] is not None
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert result["pickup_filter_summary"]["qualified"] == 0
    assert "current_observed_sample_unknown" in result["pickup_filter_summary"]["exclusions"][0]["reasons"]


@pytest.mark.parametrize(
    "filters",
    [
        {"min_minutes": float("nan")},
        {"min_games": 1.5},
        {"min_games": 0},
        {"min_participation": 1.1},
        {"min_minutes": True},
    ],
)
def test_filters_validate_finite_ranges(filters):
    snapshot = chain()
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot) | {"pickup_filters": filters}, NOW)
    assert result["status"] == "unavailable" and result["reasons"]


def test_adjustable_filters_do_not_change_own_roster_drop_legality():
    snapshot = chain(1, 11, 4)
    result = adapter.plan_snapshot_waivers(
        snapshot,
        preferences(snapshot) | {"pickup_filters": {"min_minutes": 10, "min_games": 1, "min_participation": 0.2}},
        NOW,
    )
    assert result["pickup_filter_summary"]["qualified"] == 1
    assert result["search"]["legal_drop_ids"] == ["1"]


def test_chain_two_independent_improvements_and_compact_all_nine_arithmetic():
    snapshot = chain(second_free=True)
    own = snapshot["teams"][0]["roster"]
    own.append(copy.deepcopy(own[0]))
    own[1]["id"] = "extra"
    for p in own:
        p.update(active=False, lineup_slot="IR")
    snapshot["league"]["lineup_slots"] = ["UTIL", "UTIL"]
    prefs = preferences(snapshot) | {
        "candidate_ids": ["100", "101"],
        "droppable_ids": ["1", "extra"],
        "max_stream_slots": 2,
        "selected_categories": FIVE,
        "player_overrides": {pid: {"core_protection_override": True} for pid in ["1", "extra"]},
    }
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert len(result["actions"]) == 2, result["reasons"]
    assert len({m["add_id"] for m in result["actions"]}) == 2
    for move in result["actions"]:
        assert move["pickup_sample"]["games"] == 2
        assert move["pickup_sample"]["team_games"] == 4
        assert move["net_score"] > 0
        assert len(move["arithmetic"]["categories"]) == 9
    assert result["actions"][0]["score_after"] == result["actions"][1]["score_before"]
    assert result["projected"]["totals"]["ast"] - result["baseline"]["totals"]["ast"] == pytest.approx(
        sum(m["gains"]["ast"] for m in result["actions"])
    )
    prefs["candidate_ids"] = ["100"]
    one = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert len(one["actions"]) == 1  # same pickup cannot be combined against two drops


def test_depth_reservation_prevents_large_first_layer_starving_continuations():
    data = fixture()
    data.update(
        dates=["2026-11-01"],
        selected_categories=FIVE,
        evaluation_limit=12,
        max_stream_slots=2,
        lineup_slots=["UTIL", "UTIL"],
    )
    data["players"] = [player("d1", "user", []), player("d2", "user", [])] + [
        player(f"a{n}", current_rates=rates(ast=4, reb=3, pts=4)) for n in range(10)
    ]
    result = plan_waivers(data)
    assert len(result["actions"]) == 2
    assert result["search"]["depth_reached"] == 2
    assert result["search"]["layer_evaluations"][0] == 6
    assert result["search"]["evaluations"] <= 12
    assert result["search"]["stop_reason"] == "evaluation_limit"
    assert not result["search"]["first_layer_complete"]


def test_search_exhaustion_is_not_a_no_benefit_claim():
    data = fixture()
    data.update(evaluation_limit=1, selected_categories=FIVE)
    data["players"] += [player(f"a{n}") for n in range(3)]
    result = plan_waivers(data)
    assert result["evaluation_state"] == "search_incomplete"
    assert result["search"]["stop_reason"] == "evaluation_limit"
    data["players"] = [player("drop", "user", [])]
    result = plan_waivers(data)
    assert result["evaluation_state"] == "evaluated_no_material_benefit"
    assert result["search"]["stop_reason"] == "no_legal_continuation"


def test_team_stats_batch_schema_and_request(monkeypatch):
    calls = []

    def endpoint(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            get_dict=lambda: {
                "resultSets": [
                    {
                        "name": "LeagueDashTeamStats",
                        "headers": ["TEAM_ID", "GP"],
                        "rowSet": [[tid, 4] for tid in nba.NBA_TO_ESPN],
                    }
                ]
            }
        )

    monkeypatch.setattr(nba.leaguedashteamstats, "LeagueDashTeamStats", endpoint)
    assert len(real_fetch_team_games(2027)) == 30
    assert calls[0]["season"] == "2026-27" and calls[0]["season_type_all_star"] == "Regular Season"
    assert calls[0]["timeout"] == 6 and calls[0]["date_to_nullable"]


def nba_row(games, minutes, team=1610612738):
    return {
        "PLAYER_ID": 990100,
        "PLAYER_NAME": "Fixture Player 100",
        "TEAM_ID": team,
        "TEAM_ABBREVIATION": "BOS" if team else "TOT",
        "GP": games,
        **{field: (minutes if field == "MIN" else 1) for field in nba.FIELDS},
    }


def test_low_nba_observed_sample_overrides_high_espn_and_prior_projection():
    snapshot = chain(gp=10, mpg=30, team_gp=10)
    bundle = team_bundle(NOW.isoformat(), 10) | {
        "rates": [nba_row(1, 11)],
        "rates_status": "fresh",
        "rates_fetched_at": NOW.isoformat(),
    }
    nba.enrich_players(snapshot, bundle)
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    reasons = result["pickup_filter_summary"]["exclusions"][0]["reasons"]
    assert "below_min_minutes" in reasons and "below_min_games" in reasons
    assert not result["actions"]


def test_trade_aggregate_never_double_counts_splits_or_assumes_current_team_exposure():
    snapshot = chain()
    rows = [nba_row(3, 20, 0), nba_row(1, 30), nba_row(2, 15, 1610612738)]
    bundle = team_bundle(NOW.isoformat(), 4) | {
        "rates": rows,
        "rates_status": "fresh",
        "rates_fetched_at": NOW.isoformat(),
    }
    nba.enrich_players(snapshot, bundle)
    pickup = snapshot["free_agents"][0]
    assert pickup["current_games"] == 3 and pickup["pickup_sample"]["aggregate"]
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert "traded_sample_exposure_unknown" in result["pickup_filter_summary"]["exclusions"][0]["reasons"]
    assert not result["actions"]


def test_stale_denominator_date_cannot_qualify_current_sample():
    snapshot = chain()
    snapshot["free_agents"][0]["pickup_sample"]["as_of"] = "2026-10-30T18:00:00Z"
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert "completed_team_games_unknown" in result["pickup_filter_summary"]["exclusions"][0]["reasons"]


def test_full_schedule_fallback_counts_unique_completed_regular_season_games_only():
    snapshot = chain(team_gp=None)
    games = []
    tids = list(nba.NBA_TO_ESPN)
    # Every team has complete endpoint coverage; two finals, one in-progress and
    # one exhibition. Repeat final rows to prove deduplication of team-game IDs.
    for i in range(0, 30, 2):
        for index, status, prefix in [(0, 3, "002"), (1, 3, "002"), (2, 2, "002"), (3, 3, "001")]:
            game = {
                "gameId": f"{prefix}260{i:02}{index:03}",
                "gameDateTimeUTC": "2026-10-30T18:00:00Z",
                "gameStatus": status,
                "homeTeam": {"teamId": tids[i]},
                "awayTeam": {"teamId": tids[i + 1]},
            }
            games.extend([game, copy.deepcopy(game)])
    bundle = team_bundle(NOW.isoformat()) | {
        "team_games": [],
        "schedule": {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [{"games": games}]}},
        "schedule_status": "fresh",
        "schedule_fetched_at": NOW.isoformat(),
        "schedule_scope": "full_season_endpoint",
    }
    nba.enrich_players(snapshot, bundle)
    sample = snapshot["free_agents"][0]["pickup_sample"]
    assert sample["team_games"] == 0  # Verified ESPN full-season sample survives the partial NBA subset.
    assert sample["denominator_source"] == "espn_official_completed_season_schedule"
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert result["pickup_filter_summary"]["qualified"] == 0
    bundle.pop("schedule_scope")  # An arbitrary/trimmed schedule is not a completed-season denominator.
    nba.enrich_players(snapshot, bundle)
    assert snapshot["free_agents"][0]["pickup_sample"]["team_games"] == 0


def test_genuine_one_move_with_unused_budget_has_honest_selected_stop():
    snapshot = chain()
    snapshot["teams"][0]["roster"][0].update(active=False, lineup_slot="IR")
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot) | {"selected_categories": FIVE}, NOW)
    assert len(result["actions"]) == 1 and result["remaining_adds"] == 1
    assert result["search"]["selected_plan_stop_reason"] == "best_beneficial_explored_continuation"
    assert result["recommended_plan"]["optimality"] == "best explored"


def test_observed_public_espn_completed_schedule_fallback_and_coverage():
    observed = json.loads((Path(__file__).parent / "fixtures/fantasy_v6_completed_schedule_observed.json").read_text())
    now = datetime.fromisoformat(observed["observed_at"])
    assert espn.completed_team_games(observed["schedule"], observed["season_id"], now) == {}
    # The older retained observation is a completed-only extract; use the new full public season response.
    schedule = json.loads((Path(__file__).parents[1] / "docs/evidence/v7-schedule/espn-season.response").read_text())
    counts = espn.completed_team_games(schedule, observed["season_id"], now)
    assert {str(k): v for k, v in counts.items()} == observed["completed_counts"]
    assert counts[2] == 6  # BOS actual official completed games in retained public response.
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    snapshot = espn.normalize(
        raw["league"],
        schedule,
        raw["pool"],
        raw["cards"],
        {},
        1,
        now=now,
        nba={"rates": [], "rates_status": "unavailable"},
    )
    sample = snapshot["free_agents"][0]["pickup_sample"]
    assert sample["team_games"] == 6
    assert sample["denominator_source"] == "espn_official_completed_season_schedule"
    assert (
        "below_min_participation"
        in adapter.pickup_exclusions(snapshot["free_agents"][0], adapter.pickup_filters(None), 2027, now)[0]
    )
    # Prior-rate recovery must retain already verified ESPN denominator evidence.
    nba.enrich_players(snapshot, {"rates": [], "rates_status": "unavailable"})
    assert snapshot["free_agents"][0]["pickup_sample"]["team_games"] == 6
    partial = copy.deepcopy(schedule)
    partial["settings"]["proTeams"] = partial["settings"]["proTeams"][:-1]
    assert not espn.completed_team_games(partial, 2027, now)
    malformed = copy.deepcopy(schedule)
    for team in malformed["settings"]["proTeams"]:
        if team["id"] == 2:
            first = next(iter(team["proGamesByScoringPeriod"].values()))[0]
            first.pop("statsOfficial")
    assert 2 not in espn.completed_team_games(malformed, 2027, now)


def test_pickup_sample_gates_never_filter_low_sample_own_drop():
    snapshot = chain()
    own = snapshot["teams"][0]["roster"][0]
    own["current_games"] = 1
    own["current_rates"]["minutes"] = 11
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert result["pickup_filter_summary"]["qualified"] == 1
    assert result["search"]["legal_drop_ids"] == ["1"]
