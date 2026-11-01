import asyncio
import threading

import httpx2 as httpx
import pytest

from nba_terminal import webapp


@pytest.fixture(autouse=True)
def clear_cache():
    webapp._cache.clear()


def request(path):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=webapp.app), base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(run())


def test_search_and_profile_routes_share_batched_data_off_event_loop(monkeypatch):
    main_thread = threading.get_ident()
    calls = []

    def profile(player_id, season, phase):
        assert threading.get_ident() != main_thread
        return {"player_id": player_id, "history_state": "available"}

    def dashboard(season, phase):
        assert threading.get_ident() != main_thread
        calls.append((season, phase))
        return {"state": "available", "note": "", "players": {"7": {"TS_PCT": 0.65}}}

    monkeypatch.setattr(webapp.player_data, "search_players", lambda q: [{"player_id": 7, "name": q}])
    monkeypatch.setattr(webapp.player_analysis_service, "fetch_player_profile", profile)
    monkeypatch.setattr(webapp.player_analysis_service, "fetch_season_advanced", dashboard)
    assert request("/api/players?q=Test").json()["players"][0]["name"] == "Test"
    assert request("/api/players/7?season=2025-26&phase=Playoffs").json()["advanced"]["TS_PCT"] == 0.65
    assert request("/api/players/8?season=2025-26&phase=Playoffs").json()["advanced_state"] == "unavailable"
    assert calls == [("2025-26", "Playoffs")]
    assert request("/api/players/7?season=2025-26&phase=invalid").status_code == 400
    assert request("/api/players/7?season=bad").status_code == 422


def test_failed_dashboard_is_retryable_and_missing_is_distinct(monkeypatch):
    attempts = []
    monkeypatch.setattr(
        webapp.player_analysis_service, "fetch_player_profile", lambda *args: {"history_state": "error"}
    )

    def failure(*args):
        attempts.append(1)
        return {"state": "error", "note": "Request failed", "players": {}}

    monkeypatch.setattr(webapp.player_analysis_service, "fetch_season_advanced", failure)
    for _ in range(2):
        result = request("/api/players/7?season=2025-26").json()
        assert result["advanced_state"] == "error"
        assert result["advanced_note"] == "Request failed"
    assert len(attempts) == 2
    assert not webapp._cache


def test_player_browser_direct_reload_shell(monkeypatch, tmp_path):
    monkeypatch.setattr(webapp, "WEB_DIST", tmp_path)
    assert request("/players/7").status_code == 503
    (tmp_path / "index.html").write_text("<html>shell</html>")
    assert request("/players").status_code == 200
    assert request("/players/7?season=2025-26&phase=Playoffs").text == "<html>shell</html>"


def test_on_demand_measures_shooting_history_and_scope_validation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        webapp.player_analysis_service,
        "fetch_season_advanced",
        lambda season, phase, measure: (
            calls.append(measure) or {"state": "available", "note": "", "players": {"7": {"GP": 3}}}
        ),
    )
    monkeypatch.setattr(
        webapp.player_analysis_service,
        "fetch_player_shooting_tables",
        lambda *args: {"state": "available", "tables": {}},
    )
    monkeypatch.setattr(
        webapp.player_analysis_service,
        "fetch_player_profile",
        lambda *args: {"history_state": "available", "history": {"games": []}},
    )
    assert request("/api/players/7/measures/Scoring?season=2025-26").json()["row"]["GP"] == 3
    assert request("/api/players/8/measures/Scoring?season=2025-26").json()["state"] == "unavailable"
    assert calls == ["Scoring"]
    assert request("/api/players/7/shooting?season=2025-26").json()["state"] == "available"
    assert request("/api/players/7/history?season=2024-25").json()["history"]["games"] == []
    assert request("/api/players/7/measures/invalid?season=2025-26").status_code == 400
    for path in ("", "/shooting", "/history", "/measures/Base"):
        assert request(f"/api/players/7{path}?season=2025-99").status_code == 400
        assert request(f"/api/players/7{path}?season=2025-26&phase=invalid").status_code == 400
