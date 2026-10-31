"""V2 strategy, automatic choices and honest partial-data behavior; synthetic only."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from nba_terminal.services.fantasy_optimizer import CATEGORIES, TOTALS, plan_waivers
from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers

DAY = "2026-11-01"
NOW = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)


def totals(**kwargs):
    return {**dict.fromkeys(TOTALS, 20), "fgm": 50, "fga": 100, "ftm": 40, "fta": 50, **kwargs}


def rates(**kwargs):
    return {**dict.fromkeys(TOTALS, 0), "minutes": 22, **kwargs}


def player(pid, owner="free", **kwargs):
    return {
        "id": pid,
        "name": pid,
        "owner": owner,
        "positions": ["PG"],
        "locked": None,
        "eligible": True,
        "availability": "FREEAGENT",
        "current_games": 20,
        "current_rates": rates(),
        "schedule": [DAY],
        **kwargs,
    }


def payload():
    return {
        "dates": [DAY],
        "current_totals": totals(),
        "opponent_totals": totals(),
        "players": [player("drop", "user", schedule=[])],
        "lineup_slots": ["UTIL"],
        "weekly_add_limit": 3,
        "used_adds": 2,
        "available_adds": 1,
        "margin_sd": {k: 0.03 if k.endswith("pct") else 5 for k in CATEGORIES},
    }


def snapshot():
    def scheduled(p):
        return {**p, "schedule": [{"date": DAY, "start_at": DAY + "T22:00:00Z", "started": False}]}

    return {
        "league": {
            "id": "synthetic",
            "supported": True,
            "lineup_slots": ["UTIL"],
            "acquisition_settings": {"limit_per_scoring_period": False, "weekly_add_limit": 3},
        },
        "selected_team_id": 1,
        "opponent_team_id": 2,
        "fetched_at": "fixture-v1",
        "period": {"matchup_period_id": 4, "dates": [DAY], "remaining_dates": [DAY]},
        "teams": [
            {
                "id": 1,
                "totals": totals(),
                "roster": [scheduled(player("drop", "user"))],
                "weekly_used_adds": 2,
                "remaining_adds": 1,
                "weekly_usage_complete": True,
            },
            {"id": 2, "totals": totals(), "roster": [scheduled(player("opponent", "opponent"))]},
        ],
        "free_agents": [scheduled(player("add", current_rates=rates(ast=6, stl=1)))],
        "matchup_history": [],
    }


def prefs():
    return {"context": {"league_id": "synthetic", "team_id": 1, "matchup_period_id": 4, "fetched_at": "fixture-v1"}}


def test_top_seven_are_unique_pickup_alternatives_not_seven_budgeted_moves():
    data = payload()
    data["players"] += [player(str(n), current_rates=rates(ast=3 + n / 10)) for n in range(12)]
    result = plan_waivers(data)
    assert len(result["recommendations"]) == 7
    assert len({r["add_id"] for r in result["recommendations"]}) == 7
    assert [r["rank"] for r in result["recommendations"]] == list(range(1, 8))
    assert result["recommendation_kind"] == "alternatives"
    assert len(result["plan"]) == len(result["actions"]) == 1
    assert result["remaining_adds"] == 0
    assert all(r["drop_id"] == "drop" and r["net_score"] > 0 for r in result["recommendations"])


def test_unknown_budget_retains_conditional_rankings_and_never_invents_plan():
    data = payload()
    data.update(used_adds=None, available_adds=None)
    data["players"].append(player("add", current_rates=rates(ast=5)))
    result = plan_waivers(data)
    assert result["status"] == "incomplete"
    assert result["baseline"] and result["strategy"]
    assert result["recommendations"][0]["conditional_on_one_add"] is True
    assert result["remaining_adds"] is None and result["actions"] == result["plan"] == []
    data.update(used_adds=3, available_adds=0)
    assert not plan_waivers(data)["recommendations"]


def test_current_season_rates_and_minutes_are_primary_not_blended():
    data = payload()
    data["players"] = [
        player(
            "starter",
            "user",
            current_games=3,
            current_rates=rates(ast=9, minutes=32),
            prior_rates=rates(ast=1, minutes=8),
        )
    ]
    result = plan_waivers(data)
    assert result["baseline"]["user_totals"]["ast"] == 29
    assert result["baseline"]["minutes"]["user"] == 32
    assert result["provenance"]["starter"] == "current season"
    data["players"][0]["current_games"] = 2
    result = plan_waivers(data)
    assert result["baseline"]["minutes"]["user"] == 8
    assert "fallback" in result["provenance"]["starter"]


def test_missing_rate_fields_get_targeted_prior_fallback_with_provenance():
    data = payload()
    data["players"] = [
        player(
            "starter",
            "user",
            current_rates=rates(ast=9, minutes=None, fga=None),
            prior_rates=rates(ast=1, minutes=15, fga=8, fgm=4),
        )
    ]
    result = plan_waivers(data)
    assert result["baseline"]["user_totals"]["ast"] == 29
    assert result["baseline"]["minutes"]["user"] == 15
    assert result["baseline"]["user_totals"]["fgm"] == 54
    assert "prior fallback" in result["provenance"]["starter"]


@pytest.mark.parametrize(
    "evidence", [{"undroppable": True}, {"droppable": False}, {"draft_round": 1}, {"draft_pick": 5}, {"season_rank": 9}]
)
def test_elites_cannot_be_dropped_even_with_unprotect_toggle(evidence):
    data = payload()
    data["players"][0].update(**evidence, protected=False)
    data["players"].append(player("add", current_rates=rates(ast=50)))
    result = plan_waivers(data)
    assert not result["actions"] and not result["recommendations"]
    assert "drop" in result["protected_players"]


def test_default_season_protection_has_explicit_override_but_long_term_cost_remains():
    data = payload()
    data["players"][0].update(season_rank=25, current_rates=rates(pts=24, reb=8), protected=None)
    data["players"].append(player("add", current_rates=rates(ast=6)))
    assert not plan_waivers(data)["recommendations"]
    data["players"][0]["protected"] = False
    result = plan_waivers(data)
    if result["recommendations"]:
        assert result["recommendations"][0]["season_cost"] > 0
    assert "drop" not in result["protected_players"]


def test_drop_cost_and_net_remaining_contribution_beat_raw_free_agent_production():
    data = payload()
    data["current_totals"] = totals(pts=0, ast=13)
    data["opponent_totals"] = totals(pts=1000)
    data["players"] = [
        player("valuable", "user", current_rates=rates(ast=7, stl=2)),
        player("expendable", "user", schedule=[]),
        player("points", current_rates=rates(pts=50, minutes=40)),
        player("target", current_rates=rates(ast=4, minutes=20)),
    ]
    data["lineup_slots"] = ["UTIL", "UTIL"]
    result = plan_waivers(data)
    assert result["recommendations"][0]["add_id"] == "target"
    assert result["recommendations"][0]["drop_id"] == "expendable"
    assert result["strategy"]["pts"]["classification"] == "punt"
    assert "ast" in result["recommendations"][0]["target_categories"]


def test_prior_week_context_is_distinct_from_current_projected_swing():
    data = snapshot()
    for period in (1, 2, 3):
        data["matchup_history"] += [
            {
                "matchup_period_id": period,
                "home_team_id": 1,
                "away_team_id": 3,
                "home_totals": totals(ast=30 + period),
                "away_totals": totals(),
            },
            {
                "matchup_period_id": period,
                "home_team_id": 4,
                "away_team_id": 2,
                "home_totals": totals(),
                "away_totals": totals(ast=20),
            },
        ]
    data["teams"][0]["totals"]["ast"] = 18
    result = plan_snapshot_waivers(data, prefs(), NOW)
    category = result["strategy"]["ast"]
    assert category["historical_margin"] == 13
    assert category["previous_user"] == 33 and category["previous_opponent"] == 20
    assert category["current_user"] == 18 and category["projected_margin"] == -2
    assert category["classification"] in ("reachable", "swing")
    assert "prior-week" in category["explanation"]
    assert result["uncertainty"]["source"] == "history"


def test_unknown_shooting_denominators_keep_known_category_alternatives_not_fake_odds():
    data = payload()
    data["current_totals"].update(fgm=0, fga=0)
    data["players"].append(player("add", current_rates=rates(ast=6)))
    result = plan_waivers(data)
    assert result["baseline"]["categories"]["fg_pct"]["user"] is None
    assert result["baseline"]["win_at_least_five_probability"] is None
    assert result["recommendations"] and result["recommendations"][0]["probability_gain"] is None
    assert result["recommendations"][0]["category_probability_gains"]["fg_pct"] is None
    assert result["actions"] == []


def test_automatic_adapter_refresh_context_and_availability_toggles_are_immediate():
    data = snapshot()
    original = deepcopy(data)
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["recommendations"] and data == original
    data["fetched_at"] = "fixture-v2"
    assert plan_snapshot_waivers(data, prefs(), NOW)["recommendations"]
    overrides = {"player_overrides": {"add": {"injured": True}}}
    assert not plan_snapshot_waivers(data, prefs() | overrides, NOW)["recommendations"]
    data["free_agents"][0].update(health_status="out", injury_status="OUT")
    assert not plan_snapshot_waivers(data, prefs(), NOW)["recommendations"]
    overrides["player_overrides"]["add"]["injured"] = False
    assert plan_snapshot_waivers(data, prefs() | overrides, NOW)["recommendations"]
    assert not plan_snapshot_waivers(data, prefs() | {"protected_ids": ["drop"]}, NOW)["recommendations"]
    assert not plan_snapshot_waivers(data, prefs() | {"candidate_ids": []}, NOW)["recommendations"]
    stale = prefs()
    stale["context"]["matchup_period_id"] = 3
    assert plan_snapshot_waivers(data, stale, NOW)["status"] == "unavailable"


def test_missing_candidate_schedule_is_local_gap_not_blanket_block():
    data = snapshot()
    unavailable = deepcopy(data["free_agents"][0])
    unavailable.update(id="unknown", schedule=None)
    data["free_agents"].append(unavailable)
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["status"] == "ready" and result["recommendations"]
    assert result["provenance"]["excluded_candidates"]
    data["teams"][0]["roster"][0]["schedule"] = None
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["status"] == "incomplete" and not result["actions"]
    assert result["baseline"]["probability_five_wins"] is None


def test_unknown_counts_and_complete_usage_flag_are_honest_in_adapter():
    data = snapshot()
    data["teams"][0]["weekly_usage_complete"] = False
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["remaining_adds"] is None and not result["plan"]
    assert result["recommendations"][0]["conditional_on_one_add"]
    override = {"user_confirmed_counts": True, "weekly_add_limit": 3, "used_adds": 2, "available_adds": 1}
    assert plan_snapshot_waivers(data, prefs() | override, NOW)["plan"]


def test_current_date_consumed_lineup_capacity_and_known_locks():
    data = snapshot()
    p = data["teams"][0]["roster"][0]
    p.update(lineup_slot="UTIL", schedule=[{"date": DAY, "start_at": DAY + "T10:00:00Z", "started": True}])
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["baseline"]["games"] == 0 and not result["recommendations"]
    p["lineup_slot"] = "BENCH"
    assert plan_snapshot_waivers(data, prefs(), NOW)["recommendations"]
    p["locked"] = True
    assert not plan_snapshot_waivers(data, prefs(), NOW)["recommendations"]
    data["period"]["remaining_dates"] = ["2026-10-30"]
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["status"] == "incomplete" and not result["recommendations"]
    assert result["strategy"]


def test_observed_core_production_is_protected_without_draft_or_rank():
    data = payload()
    data["players"][0].update(current_rates=rates(pts=25, reb=8, ast=8, stl=1.5, threes=3, to=3, minutes=33))
    data["players"].append(player("add", current_rates=rates(ast=5)))
    result = plan_waivers(data)
    assert not result["recommendations"]
    assert result["protected_players"]["drop"] == "Core production and established minutes"


def test_full_season_opportunity_cost_rejects_tiny_weekly_gain_after_unprotect():
    data = payload()
    data["players"][0].update(current_rates=rates(pts=25, reb=8, minutes=30), protected=False)
    data["players"].append(player("add", current_rates=rates(ast=0.01)))
    assert not plan_waivers(data)["recommendations"]


def test_history_never_pairs_previous_totals_from_different_weeks():
    data = snapshot()
    data["matchup_history"] = [
        {
            "matchup_period_id": 2,
            "home_team_id": 1,
            "away_team_id": 2,
            "home_totals": totals(ast=30),
            "away_totals": totals(ast=20),
        },
        {
            "matchup_period_id": 3,
            "home_team_id": 1,
            "away_team_id": 3,
            "home_totals": totals(ast=99),
            "away_totals": totals(),
        },
    ]
    result = plan_snapshot_waivers(data, prefs(), NOW)
    assert result["strategy"]["ast"]["previous_user"] == 30
    assert result["strategy"]["ast"]["previous_opponent"] == 20
