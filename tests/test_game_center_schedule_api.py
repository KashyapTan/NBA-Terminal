"""Exercise the serialized schedule route with captured public provider rows."""

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx2 as httpx
import pandas as pd

from nba_terminal import webapp


def test_three_date_schedule_serializes_actual_provider_rows(monkeypatch):
    fixture = json.loads((Path(__file__).parent / "fixtures/nba_schedule_2026_11_01.json").read_text())
    frame = pd.DataFrame(fixture["rows"])
    monkeypatch.setattr(webapp.game_center, "nba_today", lambda: date(2026, 11, 1))
    monkeypatch.setattr(webapp.game_center, "fetch_season_schedule", lambda season: frame)
    webapp._cache.clear()

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=webapp.app), base_url="http://test") as client:
            return await client.get("/api/upcoming")

    try:
        response = asyncio.run(run())
        assert response.status_code == 200
        payload = response.json()
        assert payload["days"] == ["2026-11-01", "2026-11-02", "2026-11-03"]
        assert {game["date"] for game in payload["games"]} == {"2026-11-01", "2026-11-02"}
        # The public snapshot has no November 3 games; retain that date in days.
        expected = [row for row in fixture["rows"] if row["gameDateEst"][:10] in payload["days"]]
        assert len(payload["games"]) == len(expected)
        for game in payload["games"]:
            source = next(row for row in expected if row["gameId"] == game["game_id"])
            assert game["status_id"] == source["gameStatus"]
            assert game["start_time"] == source["gameDateTimeUTC"]
            assert game["home_score"] == source["homeTeam_score"]
            assert game["home_team"]["id"] == source["homeTeam_teamId"]
            assert game["home_team"]["logo_url"].endswith(f'/{source["homeTeam_teamId"]}/primary/L/logo.svg')
    finally:
        webapp._cache.clear()
