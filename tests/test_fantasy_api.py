"""Tests for Fantasy API routing, parameter validation and cache reuse."""

import asyncio

import httpx2 as httpx

from nba_terminal import webapp
from nba_terminal.fantasy_api import fantasy


def test_fantasy_players_route_uses_shared_cache_and_rejects_bad_season(monkeypatch):
    webapp._cache.clear()
    calls = []

    def fetch(season):
        calls.append(season)
        return {"season": season, "supported": True, "phase": "Regular Season", "players": []}

    monkeypatch.setattr(fantasy, "fetch_fantasy_season", fetch)

    async def scenario():
        transport = httpx.ASGITransport(app=webapp.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.get("/api/fantasy/players", params={"season": "2025-26"})
            second = await client.get("/api/fantasy/players", params={"season": "2025-26"})
            invalid = await client.get("/api/fantasy/players", params={"season": "2025-27"})
        return first, second, invalid

    first, second, invalid = asyncio.run(scenario())

    assert first.status_code == 200
    assert second.json() == first.json()
    assert calls == ["2025-26"]
    assert invalid.status_code == 400
    assert calls == ["2025-26"]
    webapp._cache.clear()
