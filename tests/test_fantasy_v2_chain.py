"""Real session HTTP normalization with only external ESPN/NBA transports mocked."""

import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx2 as httpx
import pytest
import requests
from fantasy_v2_fixture import league_payload, nba_rates_payload, nba_schedule_payload

from nba_terminal import espn_fantasy_api as api
from nba_terminal import webapp
from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba
from nba_terminal.services import fantasy_planner_adapter as adapter

# Capture before conftest's autouse offline fixture. These tests intentionally run real load/cache/parsers.
NBA_LOAD = nba.load
NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)


@pytest.mark.parametrize("failed", [False, True])
def test_nba_fallback_and_failure_through_real_http_session(monkeypatch, failed):
    raw = league_payload()
    raw["schedule"] = {}
    for collection in (raw["pool"], raw["cards"]):
        for entry in collection["players"]:
            player = espn.player_body(entry)
            if player["id"] == 100:
                player["stats"] = [split for split in player["stats"] if split["seasonId"] != 2027]
    calls = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    def get(self, views, *args, **kwargs):
        key = {
            "mSettings": "league",
            "proTeamSchedules_wl": "schedule",
            "kona_player_info": "pool",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
            "mMatchupScore": "league",
        }[views[0]]
        return copy.deepcopy(raw[key])

    def rates(**kwargs):
        calls.append(("rates", kwargs))
        if failed:
            raise requests.Timeout("Synthetic NBA timeout")
        return SimpleNamespace(get_dict=nba_rates_payload)

    def schedule(**kwargs):
        calls.append(("schedule", kwargs))
        if failed:
            raise requests.Timeout("Synthetic NBA timeout")
        return SimpleNamespace(get_dict=nba_schedule_payload)

    def blocked_cdn(*args, **kwargs):
        raise requests.HTTPError("Synthetic CDN 403")

    monkeypatch.setattr(nba, "load", NBA_LOAD)
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(nba.leaguedashplayerstats, "LeagueDashPlayerStats", rates)
    monkeypatch.setattr(nba.scheduleleaguev2, "ScheduleLeagueV2", schedule)
    monkeypatch.setattr(nba.requests, "get", blocked_cdn)
    monkeypatch.setattr(espn, "datetime", Clock)
    monkeypatch.setattr(adapter, "datetime", Clock)
    monkeypatch.setattr(espn.EspnClient, "get", get)
    monkeypatch.setattr(webapp.app.state, "espn_sessions", api.SessionStore(), raising=False)
    monkeypatch.setattr(webapp.app.state, "espn_slots", asyncio.Semaphore(4), raising=False)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=webapp.app), base_url="http://127.0.0.1"
        ) as browser:
            response = await browser.post(
                "/api/fantasy/espn/connect",
                headers={"X-Fantasy-Request": "1"},
                json={"league_id": 123, "season_id": 2027, "team_id": 1},
            )
            assert response.status_code == 200
            response = await browser.get("/api/fantasy/espn/snapshot")
            assert response.status_code == 200
            snapshot = response.json()
            assert len(snapshot["teams"]) == 14
            assert len(snapshot["teams"][0]["roster"]) == 13
            assert snapshot["teams"][0]["weekly_used_adds"] == 6
            assert snapshot["teams"][0]["remaining_adds"] == 1
            pickup = next(p for p in snapshot["free_agents"] if p["id"] == "100")
            roster = snapshot["teams"][0]["roster"][0]
            assert roster["current_rates"]["minutes"] == 18  # usable ESPN remains authoritative
            if failed:
                assert pickup["current_rates"] is None
                assert pickup["schedule"] is None
                assert snapshot["enrichment"]["rates_status"] == "unavailable"
                assert any("NBA schedule unavailable" in gap for gap in snapshot["data_gaps"])
            else:
                assert pickup["current_rates"]["minutes"] == 28
                assert pickup["current_rates_source"] == "nba_stats"
                assert pickup["identity"]["nba_player_id"] == 990100
                assert pickup["schedule_source"] == "nba_schedule"
                assert pickup["remaining_games"] == 2
                assert pickup["today"] is True
                assert snapshot["enrichment"]["schedule_status"] == "fresh"
                assert roster["injured"] is True and roster["health_status"] == "available"
                assert snapshot["teams"][0]["roster"][2]["draft_round"] == 1
                context = {"league_id": 123, "team_id": 1, "matchup_period_id": 2}

                async def plan(overrides=None):
                    response = await browser.post(
                        "/api/fantasy/espn/plan",
                        headers={"X-Fantasy-Request": "1"},
                        json={"context": context, "player_overrides": overrides or {}},
                    )
                    assert response.status_code == 200
                    return response.json()

                initial = await plan()
                assert len(initial["recommendations"]) > 7
                assert all(item["net_score"] > 0 for item in initial["recommendations"])
                assert all(item["estimated_win_gain"] > 0 for item in initial["recommendations"])
                unique_pairs = {(item["add_id"], item["drop_id"]) for item in initial["recommendations"]}
                assert len(unique_pairs) == len(initial["recommendations"])
                assert len(initial["selected_categories"]) == 5
                assert set(initial["improvement_categories"]).isdisjoint(initial["safe_categories"])
                assert "1002" in initial["search"]["legal_drop_ids"]
                assert "1002" in initial["search"]["evaluated_drop_ids"]
                assert "1001" not in initial["search"]["legal_drop_ids"]
                assert initial["remaining_adds"] + len(initial["actions"]) == 1
                assert "1002" not in initial["protected_players"]
                assert {item["drop_id"] for item in initial["recommendations"]} >= {"1", "1002"}
                best = initial["recommendations"][0]
                assert best["target_categories"]
                assert all(
                    initial["strategy"][key]["improvement_target"]
                    for key in best["target_categories"]
                )
                out = await plan({"100": {"injured": True}})
                assert all(item["add_id"] != "100" for item in out["recommendations"])
                protected = await plan({"1": {"protected": True}, "1002": {"protected": False}})
                assert all(item["drop_id"] != "1" for item in protected["recommendations"])
                assert "1002" not in protected["protected_players"]
                assert "1002" in protected["search"]["evaluated_drop_ids"]
                core_protected = await plan({"1002": {"protected": True}})
                assert all(item["drop_id"] != "1002" for item in core_protected["recommendations"])
                assert "1002" not in core_protected["search"]["legal_drop_ids"]
                available = await plan({"1": {"injured": False}})
                assert available["baseline"]["minutes"] == initial["baseline"]["minutes"]

    asyncio.run(scenario())
    assert len(calls) == 2
    assert all(kwargs["season"] == "2026-27" for _, kwargs in calls)
