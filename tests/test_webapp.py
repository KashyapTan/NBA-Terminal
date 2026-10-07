import asyncio
from pathlib import Path

import httpx2 as httpx
import pytest

from nba_terminal import webapp


@pytest.fixture(autouse=True)
def clear_cache():
    webapp._cache.clear()


def request(method, path):
    async def run():
        transport = httpx.ASGITransport(app=webapp.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path)

    return asyncio.run(run())


def test_metadata_and_api_routes_use_mocked_service_data(monkeypatch):
    monkeypatch.setattr(webapp.game_center, "current_season", lambda today: "2025-26")
    monkeypatch.setattr(webapp.game_center, "available_seasons", lambda today: ["2025-26"])
    monkeypatch.setattr(webapp.game_center, "SUPPORTED_FROM", "1996-97")
    monkeypatch.setattr(webapp.game_center, "fetch_upcoming_games", lambda: {"games": [], "days": []})
    monkeypatch.setattr(
        webapp.game_center,
        "fetch_recent_games",
        lambda season: {"season": season, "supported": True, "games": [], "phases": []},
    )
    monkeypatch.setattr(
        webapp.game_center, "fetch_game_boxscore", lambda game_id: {"game_id": game_id, "players": [], "teams": []}
    )
    monkeypatch.setattr(
        webapp.game_center,
        "fetch_player_game_analysis",
        lambda *args: {"game_id": args[0], "player": {}, "stats": {}, "shots": [], "shot_chart_state": "unavailable"},
    )

    assert request("GET", "/api/meta").json() == {
        "current_season": "2025-26",
        "seasons": ["2025-26"],
        "supported_from": "1996-97",
    }
    assert request("GET", "/api/upcoming").json()["games"] == []
    assert request("GET", "/api/games?season=2025-26").json()["season"] == "2025-26"
    assert request("GET", "/api/games/0022400001").json()["game_id"] == "0022400001"
    assert (
        request("GET", "/api/games/0022400001/players/7?season=2025-26&phase=Playoffs").json()["shot_chart_state"]
        == "unavailable"
    )
    assert request("GET", "/api/games/0022400001/players/7?season=2025-26&phase=NotARealPhase").status_code == 400
    assert request("GET", "/api/games?season=bad").status_code == 422


def test_cache_reuses_successes_and_does_not_keep_shot_chart_errors(monkeypatch):
    calls = []

    def recent(season):
        calls.append(season)
        return {"season": season, "supported": True, "games": [], "phases": []}

    monkeypatch.setattr(webapp.game_center, "fetch_recent_games", recent)
    first = request("GET", "/api/games?season=2024-25")
    second = request("GET", "/api/games?season=2024-25")
    assert first.json() == second.json()
    assert calls == ["2024-25"]

    attempts = []

    def analysis(*args):
        attempts.append(1)
        return {"shot_chart_state": "error", "shots": []}

    monkeypatch.setattr(webapp.game_center, "fetch_player_game_analysis", analysis)
    path = "/api/games/0022400001/players/7?season=2025-26"
    request("GET", path)
    request("GET", path)
    assert len(attempts) == 2


def test_service_value_and_unexpected_errors_map_to_http_responses(monkeypatch):
    monkeypatch.setattr(
        webapp.game_center, "fetch_game_boxscore", lambda _: (_ for _ in ()).throw(ValueError("bad game"))
    )
    response = request("GET", "/api/games/not-valid")
    assert response.status_code == 400
    assert response.json()["detail"] == "bad game"
    monkeypatch.setattr(
        webapp.game_center, "fetch_game_boxscore", lambda _: (_ for _ in ()).throw(RuntimeError("private detail"))
    )
    response = request("GET", "/api/games/0022400001")
    assert response.status_code == 502
    assert response.json()["detail"] == "NBA Stats could not return this data. Please retry."


def test_busy_worker_pool_returns_503(monkeypatch):
    class BusySlots:
        async def acquire(self):
            raise asyncio.TimeoutError

        def release(self):
            raise AssertionError("busy slot must not be released")

    monkeypatch.setattr(webapp, "NBA_SLOTS", BusySlots())
    response = request("GET", "/api/games?season=2025-26")
    assert response.status_code == 503
    assert "busy" in response.json()["detail"]


def test_cache_prunes_expired_entries_and_caps_live_entries():
    async def exercise():
        loop = asyncio.get_running_loop()
        webapp._cache.update({f"expired-{index}": (loop.time() - 1, None) for index in range(251)})
        assert await webapp._cached_call("prune", 30, lambda: "fresh") == "fresh"
        assert list(webapp._cache) == ["prune"]
        webapp._cache.clear()
        webapp._cache.update({f"live-{index}": (loop.time() + 60, index) for index in range(251)})
        assert await webapp._cached_call("overflow", 30, lambda: "fresh") == "fresh"
        assert len(webapp._cache) == 251
        assert "live-0" not in webapp._cache

    asyncio.run(exercise())


def test_main_starts_uvicorn_on_localhost(monkeypatch):
    calls = []
    monkeypatch.setattr(webapp.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    webapp.main()
    assert calls == [(("nba_terminal.webapp:app",), {"host": "127.0.0.1", "port": 8000, "workers": 1})]


def test_static_shell_and_assets_are_confined_to_build_directory(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>fixture</html>")
    (dist / "assets" / "app.js").write_text("fixture")
    monkeypatch.setattr(webapp, "WEB_DIST", dist)
    assert request("GET", "/").status_code == 200
    assert request("GET", "/game/abc/player/1").status_code == 200
    assert request("GET", "/assets/app.js").text == "fixture"
    assert request("GET", "/assets/missing.js").status_code == 404
    assert request("GET", "/assets/../../index.html").status_code == 404


def test_missing_build_returns_helpful_503(monkeypatch, tmp_path):
    monkeypatch.setattr(webapp, "WEB_DIST", Path(tmp_path))
    assert request("GET", "/").status_code == 503
    assert request("GET", "/game/abc").status_code == 503
