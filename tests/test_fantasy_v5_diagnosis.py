"""V5 status honesty and captured public-provider shapes (no authenticated I/O)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_actuals as actuals
from nba_terminal.services import fantasy_nba as nba
from nba_terminal.services.fantasy_optimizer import plan_waivers
from tests.test_fantasy_optimizer import fixture, player, rates


@pytest.mark.parametrize(
    ("budget", "improves", "state"),
    [
        (None, True, "conditional_opportunities"),
        (0, True, "known_zero_acquisitions"),
        (1, True, "confirmed_ordered_plan"),
        (1, False, "evaluated_no_material_benefit"),
    ],
)
def test_evaluation_state_distinguishes_missing_budget_zero_no_benefit_and_plan(budget, improves, state):
    data = fixture()
    data.update(available_adds=budget)
    data["players"] = (
        [
            player("drop", "user", [], current_rates=rates()),
            player("add", current_rates=rates(ast=20 if improves else 0)),
        ]
        if improves
        else [player("drop", "user", current_rates=rates())]
    )
    result = plan_waivers(data)
    assert result["evaluation_state"] == state
    if budget is None:
        assert result["recommendations"]
        assert not result["actions"]
        assert not any("No materially" in reason for reason in result["reasons"])
        for move in result["recommendations"]:
            assert move["conditional_on_one_add"]
            assert move["add_usable_dates"]
            assert len(move["arithmetic"]["categories"]) == 9
    if budget == 0:
        assert not result["recommendations"]
        assert not any("No materially" in reason for reason in result["reasons"])


def test_missing_required_fact_cannot_become_conditional_or_negative_evaluation():
    data = fixture()
    data.update(available_adds=None, projection_metadata={"matchup_calendar": {"complete": False}})
    result = plan_waivers(data)
    assert result["evaluation_state"] == "required_inputs_unknown"
    assert not result["recommendations"]
    assert not result["recommended_plan"]


def test_observed_public_provider_shapes_preserve_calendar_status_rates_and_eligibility():
    observed = json.loads((Path(__file__).parent / "fixtures/fantasy_provider_observed_v5.json").read_text())
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    schedules = espn.normalize_schedule(observed["espn_schedule"], now)
    assert len(espn.scoring_date_anchors(schedules)) == 1
    nba_schedules = nba.schedule_games(observed["nba_schedule"], 2027, now)
    assert nba_schedules
    row = observed["nba_rates"][0]
    snapshot = {
        "league": {"season_id": 2027},
        "teams": [],
        "data_gaps": [],
        "free_agents": [
            {
                "name": row["PLAYER_NAME"],
                "pro_team_id": next(k for k, v in nba.ESPN_TEAMS.items() if v == row["TEAM_ABBREVIATION"]),
                "current_rates": None,
                "prior_rates": None,
                "positions": [],
                "eligible": False,
            }
        ],
    }
    nba.enrich_players(snapshot, {"rates": [row], "rates_status": "fresh", "season": "2026-27"})
    enriched = snapshot["free_agents"][0]
    assert enriched["season_rates"]["pts"] == row["PTS"]
    assert enriched["rate_provenance"]["source"] == "nba_stats"
    assert enriched["positions"] == [] and enriched["eligible"] is False
    assert enriched["rate_provenance"]["fetched_at"] is None  # No invented freshness.


def test_missing_unused_prior_sample_does_not_report_missing_selected_rate_basis():
    data = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    # Keep the complete current sample, remove every unused prior-season sample.
    for entry in (
        [p for team in data["league"]["teams"] for p in team["roster"]["entries"]]
        + data["pool"]["players"]
        + data["cards"]["players"]
    ):
        body = espn.player_body(entry)
        body["stats"] = [split for split in body.get("stats", []) if split.get("seasonId") == 2027]
    result = espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1)
    assert not any("average samples are unavailable" in gap for gap in result["data_gaps"])


def test_real_client_constructor_and_captured_game_logs_recover_without_network(monkeypatch):
    # Patch only HTTP execution, preserving the installed client's real constructor.
    # A permissive lambda(**kwargs) previously hid the invalid PerMode argument.
    from nba_api.stats.endpoints.playergamelogs import PlayerGameLogs

    observed = json.loads((Path(__file__).parent / "fixtures/fantasy_provider_observed_v5.json").read_text())
    rows = observed["nba_game_logs"]
    headers = list(rows[0])
    payload = {
        "resultSets": [
            {"name": "PlayerGameLogs", "headers": headers, "rowSet": [[row[key] for key in headers] for row in rows]}
        ]
    }
    monkeypatch.setattr(PlayerGameLogs, "get_request", lambda self: None)
    monkeypatch.setattr(PlayerGameLogs, "get_dict", lambda self: payload)
    result = actuals.fetch_logs(2027, "2026-10-26", "2026-11-01")
    assert result["rows"] == rows
    assert len(result["rows"]) == 2


def test_unknown_schedule_cannot_claim_zero_expected_eligible_games():
    entry = {
        "lineupSlotId": 0,
        "playerPoolEntry": {"teamId": 1, "player": {"id": 2, "eligibleSlots": [0], "proTeamId": 1}},
    }
    official = dict.fromkeys(actuals.PRIMITIVES, 1)
    result = actuals.reconstruct(1, {7: "2026-10-26"}, {7: {1: [entry]}}, {}, {}, official, "2026-11-01T16:00:00Z")
    assert result["nba_derived"]["expected_player_games"] is None
    assert result["nba_derived"]["covered_player_games"] == 0
    assert result["nba_derived"]["eligible_coverage_known"] is False
    assert result["forecast_source"] == "espn_official"
    assert result["forecast_complete"] is True
    assert result["forecast_totals"] == official
