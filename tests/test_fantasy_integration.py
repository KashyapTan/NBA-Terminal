"""Production normalization -> authenticated route -> actual pure planner, synthetic transport only."""

import asyncio
import copy
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx2 as httpx
import pytest

from nba_terminal import espn_fantasy_api as api
from nba_terminal import webapp
from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_planner_adapter as adapter
from nba_terminal.services.fantasy_optimizer import CATEGORIES

NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
PREFIX = "/api/fantasy/espn"
HEADERS = {"X-Fantasy-Request": "1", "Origin": "http://127.0.0.1"}


@pytest.fixture
def raw():
    return json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())


@pytest.fixture
def snapshot(raw):
    result = espn.normalize(raw["league"], raw["schedule"], raw["pool"], raw["cards"], raw["transactions"], 1, now=NOW)
    for key in ("current_rates", "prior_rates"):
        result["free_agents"][0][key]["ast"] += 10
        result["free_agents"][0][key]["stl"] += 2
    return result


def preferences(snapshot):
    return {
        "context": {
            "league_id": snapshot["league"]["id"],
            "team_id": snapshot["selected_team_id"],
            "matchup_period_id": snapshot["period"]["matchup_period_id"],
            "fetched_at": snapshot["fetched_at"],
        },
        "weekly_add_limit": 7,
        "used_adds": 5,
        "available_adds": 2,
        "user_confirmed_counts": True,
        "user_confirmed_eligibility": True,
        "candidate_ids": ["100"],
        "droppable_ids": ["1"],
        "max_stream_slots": 1,
        "player_overrides": {"1": {"protected": False, "core_protection_override": True}},
        "uncertainty_mode": "sensitivity",
        "margin_sd": {key: 0.05 if key.endswith("pct") else 5 for key in CATEGORIES},
    }


def test_real_adapter_ready_budget_direction_weighting_and_immutable(snapshot):
    original = copy.deepcopy(snapshot)
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert snapshot == original
    assert result["status"] == "ready", result
    assert result["actions"] and result["actions"][0]["add_id"] == "100"
    assert result["remaining_adds"] == 2 - len(result["actions"])
    baseline = result["baseline"]
    assert baseline["categories"]["to"]["margin"] > 0
    assert baseline["categories"]["fg_pct"]["user"] == baseline["totals"]["fgm"] / baseline["totals"]["fga"]
    assert result["projected"]["probability_five_wins"] > baseline["probability_five_wins"]
    assert "user_confirmed" in result["provenance"]["counts"]
    assert "sensitivity" in result["provenance"]["uncertainty"]


@pytest.mark.parametrize(
    "change",
    [
        {"max_stream_slots": 5},
        {"max_stream_slots": 0},
        {"margin_sd": {}},
        {"margin_sd": {"pts": float("nan")}},
        {"remaining_dates": ["2026-10-30"]},
        {"remaining_dates": ["2026-11-03"]},
        {"remaining_dates": ["2026-11-01", "2026-11-01"]},
        {"remaining_dates": ["wrong"]},
        {"player_overrides": []},
        {"player_overrides": {"1": {"schedule": ["2026-11-03"]}}},
    ],
)
def test_incomplete_inputs_never_create_actions_or_probabilities(snapshot, change):
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot) | change, NOW)
    assert result["status"] != "ready"
    assert not result["actions"]
    assert result["baseline"]["probability_five_wins"] is None
    assert result["reasons"]


@pytest.mark.parametrize(
    "change",
    [
        {"context": None},
        {"candidate_ids": ["101"]},
        {"candidate_ids": ["1"]},
        {"candidate_ids": ["100", "100"]},
        {"candidate_ids": 1},
        {"candidate_ids": [1]},
        {"droppable_ids": ["2"]},
    ],
)
def test_invalid_scope_or_ownership_unavailable(snapshot, change):
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot) | change, NOW)
    assert result["status"] == "unavailable" and not result["actions"]


def test_unknown_fields_have_precise_editable_recovery(snapshot):
    player = snapshot["teams"][0]["roster"][0]
    player.update(injured=None, schedule=None)
    prefs = preferences(snapshot)
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "incomplete"
    assert "assumed available" in result["provenance"]["availability"]
    assert any("schedule is unknown" in gap for gap in result["data_gaps"])
    prefs["player_overrides"] = {"1": {"injured": False, "schedule": ["2026-11-01"]}}
    assert adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["status"] == "ready"
    snapshot["period"]["dates"] = []
    snapshot["period"]["remaining_dates"] = []
    prefs["remaining_dates"] = ["2026-11-01"]
    assert adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["status"] == "ready"


def test_protected_roster_remains_in_forecast_and_shortlist_affects_actual_plan(snapshot):
    protected = copy.deepcopy(snapshot["teams"][0]["roster"][0])
    protected.update(id="protected", name="Protected fixture starter")
    snapshot["teams"][0]["roster"].append(protected)
    alternative = copy.deepcopy(snapshot["free_agents"][0])
    alternative.update(id="alternative", name="Alternative fixture")
    for key in ("current_rates", "prior_rates"):
        alternative[key]["ast"] += 50
    snapshot["free_agents"].append(alternative)
    prefs = preferences(snapshot)
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["baseline"]["games"] == 4  # both full roster players contribute
    assert all(action["drop_id"] != "protected" for action in result["actions"])
    assert all(action["add_id"] == "100" for action in result["actions"])
    prefs["candidate_ids"] = ["alternative"]
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["actions"] and all(action["add_id"] == "alternative" for action in result["actions"])


def test_historical_uncertainty_requires_complete_same_period_variation(snapshot):
    snapshot["period"]["matchup_period_id"] = 4
    snapshot["matchup_history"] = []
    own = snapshot["teams"][0]["totals"]
    other = snapshot["teams"][1]["totals"]
    for index in range(1, 4):
        varied = {key: value + index for key, value in own.items()}
        snapshot["matchup_history"].append(
            {
                "matchup_period_id": index,
                "home_team_id": 1,
                "away_team_id": 2,
                "home_totals": varied,
                "away_totals": other,
            }
        )
    prefs = preferences(snapshot) | {"uncertainty_mode": "history"}
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "ready", result
    assert "3 complete prior" in result["provenance"]["uncertainty"]
    snapshot["matchup_history"][0]["home_totals"]["fga"] = None
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "ready" and result["uncertainty"]["source"] == "model_estimate"


def test_started_games_cannot_be_resurrected(snapshot):
    player = snapshot["teams"][0]["roster"][0]
    player["schedule"][0]["started"] = True
    prefs = preferences(snapshot) | {"player_overrides": {"1": {"schedule": ["2026-10-31"]}}}
    assert adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["status"] == "incomplete"


def test_authenticated_production_chain_and_guards(monkeypatch, raw):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(espn, "datetime", Clock)
    monkeypatch.setattr(adapter, "datetime", Clock)
    monkeypatch.setattr(webapp.app.state, "espn_sessions", api.SessionStore(), raising=False)
    monkeypatch.setattr(webapp.app.state, "espn_slots", asyncio.Semaphore(4))
    worker_threads = []

    def fake_get(self, views, *args, **kwargs):
        worker_threads.append(threading.current_thread().name)
        return raw[
            {
                "mSettings": "league",
                "proTeamSchedules_wl": "schedule",
                "kona_player_info": "pool",
                "kona_playercard": "cards",
                "mTransactions2": "transactions",
                "mMatchupScore": "league",  # Historical view lacks daily rosters: official fallback.
            }[views[0]]
        ]

    monkeypatch.setattr(espn.EspnClient, "get", fake_get)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=webapp.app), base_url="http://127.0.0.1"
        ) as browser:
            assert (await browser.post(PREFIX + "/plan", headers=HEADERS, json={})).status_code == 401
            connected = await browser.post(
                PREFIX + "/connect", headers=HEADERS, json={"league_id": 123, "season_id": 2027}
            )
            assert connected.status_code == 200 and len(connected.json()["teams"]) == 14
            assert (await browser.put(PREFIX + "/team", headers=HEADERS, json={"team_id": 1})).status_code == 200
            snap = (await browser.get(PREFIX + "/snapshot")).json()
            prefs = preferences(snap)
            planned = await browser.post(PREFIX + "/plan", headers=HEADERS, json=prefs)
            assert planned.status_code == 200, planned.text
            assert planned.json()["status"] == "ready", planned.json()
            assert planned.headers["cache-control"] == "no-store"
            # UI controls cross the real request boundary, not only an in-process adapter.
            toggled = await browser.post(
                PREFIX + "/plan", headers=HEADERS,
                json=prefs | {"allow_core_drops": True, "aggressive_cushion_sacrifice": False},
            )
            assert toggled.status_code == 200, toggled.text
            assert toggled.json()["recommended_plan"] is not None

            assert (await browser.post(PREFIX + "/plan", json=prefs)).status_code == 403
            assert (
                await browser.post(PREFIX + "/plan", headers=HEADERS | {"Origin": "http://evil.test"}, json=prefs)
            ).status_code == 403
            assert (
                await browser.post(PREFIX + "/plan", headers=HEADERS, json=prefs | {"snapshot": snap})
            ).status_code == 400
            assert (await browser.post(PREFIX + "/plan", headers=HEADERS, json=[])).status_code == 400
            assert (await browser.post(PREFIX + "/plan", headers=HEADERS, content="{")).status_code == 415
            assert (
                await browser.post(
                    PREFIX + "/plan", headers=HEADERS | {"Content-Type": "application/json"}, content="{"
                )
            ).status_code == 400
            assert (
                await browser.post(
                    PREFIX + "/plan", headers=HEADERS | {"Content-Type": "application/json"}, content=" " * 65_537
                )
            ).status_code == 413
            refreshed = (await browser.get(PREFIX + "/snapshot?refresh=true")).json()
            # Frozen clock keeps timestamp equal; switching teams still invalidates confirmations.
            assert refreshed["selected_team_id"] == 1
            await browser.put(PREFIX + "/team", headers=HEADERS, json={"team_id": 2})
            stale = (await browser.post(PREFIX + "/plan", headers=HEADERS, json=prefs)).json()
            assert stale["status"] == "unavailable" and not stale["actions"]
            await browser.delete(PREFIX + "/connection", headers=HEADERS)
            assert (await browser.post(PREFIX + "/plan", headers=HEADERS, json=prefs)).status_code == 401
        assert worker_threads and all(name.startswith("nba-api") for name in worker_threads)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "field,value",
    [
        ("current_games", 1.5),
        ("positions", []),
        ("schedule", [{"start_at": "2026-11-01", "started": False}]),
        ("current_rates", {"fgm": 10, "fga": 1}),
    ],
)
def test_missing_player_evidence_never_implies_complete_forecast(snapshot, field, value):
    snapshot["teams"][0]["roster"][0][field] = value
    if field == "current_rates":
        snapshot["teams"][0]["roster"][0]["current_games"] = 20
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert result["status"] == "incomplete" and result["reasons"]
    assert not result["actions"] and result["baseline"]["probability_five_wins"] is None


def test_missing_rosters_rules_and_rates_are_actionable_gaps(snapshot):
    snapshot["teams"][1]["roster"] = []
    snapshot["league"]["lineup_slots"] = []
    player = snapshot["teams"][0]["roster"][0]
    player.update(current_rates=None, prior_rates=None, current_games=None)
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
    assert result["data_gaps"]
    assert not result["actions"]


def test_prior_only_fallback_and_verified_server_counts(snapshot):
    player = snapshot["teams"][0]["roster"][0]
    player.update(current_rates=None, current_games=None)
    user = snapshot["teams"][0]
    user.update(
        weekly_used_adds=5,
        remaining_adds=2,
        weekly_usage_complete=True,
        weekly_usage_source="espn_matchup_acquisition_totals",
    )
    prefs = preferences(snapshot) | {"user_confirmed_counts": False, "player_overrides": {"1": []}}
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "ready", result
    assert result["provenance"]["rates"]["1"] == "prior season fallback"
    assert result["provenance"]["counts"] == "espn_matchup_acquisition_totals"
    user["roster"][0]["locked"] = True
    assert not adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["actions"]


def test_unsupported_or_missing_target(snapshot):
    snapshot["league"]["supported"] = False
    assert adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)["status"] == "unavailable"
    snapshot["league"]["supported"] = True
    snapshot["opponent_team_id"] = None
    assert adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)["status"] == "unavailable"


def test_missing_uncertainty_never_means_verified_daily_limit(snapshot):
    snapshot["league"]["acquisition_settings"]["limit_per_scoring_period"] = True
    prefs = preferences(snapshot) | {"user_confirmed_counts": False}
    assert adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["status"] == "incomplete"


def test_ir_and_reported_out_do_not_create_impossible_active_games(snapshot):
    player = snapshot["teams"][0]["roster"][0]
    player.update(injured=False, injury_status="OUT")
    prefs = preferences(snapshot)
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["baseline"]["games"] == 0
    ir = copy.deepcopy(player)
    ir.update(id="ir", lineup_slot="IR", current_rates=None, prior_rates=None)
    snapshot["teams"][0]["roster"].append(ir)
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "incomplete"  # Unknown IR season value cannot become zero drop cost.
    assert "inactive:ir" in result["provenance"]
    prefs["droppable_ids"] = ["ir"]
    assert not adapter.plan_snapshot_waivers(snapshot, prefs, NOW)["actions"]


def test_daily_caps_and_inactive_only_eligibility_never_become_weekly_plans(snapshot):
    prefs = preferences(snapshot)
    snapshot["league"]["acquisition_settings"]["limit_per_scoring_period"] = True
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "incomplete" and not result["actions"]
    assert any("per-day acquisition" in gap.lower() for gap in result["data_gaps"])
    snapshot["league"]["acquisition_settings"]["limit_per_scoring_period"] = False
    snapshot["teams"][0]["roster"][0]["positions"] = ["BENCH", "IR"]
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["status"] == "incomplete" and not result["actions"]


def test_normalized_available_health_overrides_raw_questionable_injury_flag(snapshot):
    player = snapshot["teams"][0]["roster"][0]
    player.update(injured=True, injury_status="DAY_TO_DAY", health_status="available")
    prefs = preferences(snapshot)
    available = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert available["baseline"]["games"] == 2
    player.update(health_status="out", injury_status="OUT")
    out = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert out["baseline"]["games"] == 0
    restored = adapter.plan_snapshot_waivers(snapshot, prefs | {"player_overrides": {"1": {"injured": False}}}, NOW)
    assert restored["baseline"]["minutes"] == available["baseline"]["minutes"]


def test_known_unverified_calendar_blocks_confidence_but_not_official_actuals(raw):
    from nba_terminal.services import fantasy_actuals
    from tests.test_fantasy_nba import schedule

    raw["league"]["settings"]["scheduleSettings"].update(periodTypeId=2, matchupPeriods={"2": [2]})
    for team in raw["league"]["teams"]:
        team["transactionCounter"]["matchupAcquisitionTotals"] = {"2": 6}
    snapshot = espn.normalize(
        raw["league"], {}, raw["pool"], raw["cards"], {}, 1, now=NOW,
        nba={"rates": [], "schedule": schedule(), "rates_status": "unavailable", "schedule_status": "fresh"},
    )

    class HistoryUnavailable:
        season_id = 2027

        def get(self, *args, **kwargs):
            raise espn.EspnError("access_denied", "Synthetic unavailable private history")

    fantasy_actuals.enrich_snapshot(HistoryUnavailable(), raw["league"], snapshot, {})
    assert snapshot["period"]["calendar_verified"] is False
    assert snapshot["projection_metadata"]["matchup_calendar"]["complete"] is False
    assert snapshot["teams"][0]["actuals"]["forecast_source"] == "espn_official"
    assert snapshot["teams"][0]["actuals"]["forecast_complete"] is True
    for missing_metadata in (False, True):
        if missing_metadata:
            snapshot["projection_metadata"].pop("matchup_calendar")
        result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), NOW)
        assert result["status"] == "incomplete"
        assert result["recommended_plan"] is None
        assert result["safe_categories"] == []
        assert all(v["classification"] == "unknown" and v["estimate"] is None for v in result["strategy"].values())

    # Real-shaped ESPN schedule anchors verify the future horizon despite unavailable NBA history.
    verified = espn.normalize(raw["league"], raw["schedule"], raw["pool"], raw["cards"], {}, 1, now=NOW)
    fantasy_actuals.enrich_snapshot(HistoryUnavailable(), raw["league"], verified, {})
    assert verified["period"]["calendar_verified"] is True
    assert verified["projection_metadata"]["matchup_calendar"]["complete"] is True
    result = adapter.plan_snapshot_waivers(verified, preferences(verified), NOW)
    assert result["status"] == "ready", result["reasons"]
    assert result["baseline"]["probability_five_wins"] is not None
