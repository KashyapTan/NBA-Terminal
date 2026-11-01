"""Focused standalone analytics routes; runner is injected by the application."""

from __future__ import annotations

from datetime import date
from typing import Any, Awaitable, Callable, Literal

from fastapi import APIRouter, HTTPException, Query
from nba_api.stats.static import teams

from nba_terminal.services.legacy_tools import LegacyToolsService

Runner = Callable[..., Awaitable[Any]]
Phase = Literal["Regular Season", "Playoffs", "Pre Season", "All Star"]
Tool = Literal["predictor", "consistency", "defense", "slate", "picks", "catalog", "meta"]


def create_legacy_tools_router(runner: Runner, service: LegacyToolsService | None = None) -> APIRouter:
    """Inject existing cached bounded worker runner(key, ttl, function, *args)."""
    router = APIRouter(prefix="/api/tools", tags=["Analytics tools"])
    service = service or LegacyToolsService()

    async def run(tool: Tool, *args: Any) -> dict:
        return await runner(f"legacy-tools:{tool}:{args!r}", 30, getattr(service, tool), *args)

    def validate(season: str, *team_ids: int) -> None:
        try:
            start, end = season.split("-")
            if len(start) != 4 or len(end) != 2 or int(end) != (int(start) + 1) % 100 or int(start) < 1996:
                raise ValueError
        except ValueError:
            raise HTTPException(400, "Season must use YYYY-YY from 1996-97 onward.") from None
        known = {t["id"] for t in teams.get_teams()}
        if any(team not in known for team in team_ids):
            raise HTTPException(400, "Unknown NBA team.")

    @router.get("/meta")
    async def meta() -> dict:
        return await run("meta")

    @router.get("/consistency")
    async def consistency(
        season: str = Query(..., min_length=7, max_length=7),
        phase: Phase = "Regular Season",
        team_id: int = Query(..., gt=0),
        stat: Literal["PTS", "REB", "AST", "STL", "BLK"] = "PTS",
        window: int = Query(10),
    ) -> dict:
        validate(season, team_id)
        if window not in {5, 10, 15, 20}:
            raise HTTPException(400, "Window must be 5, 10, 15 or 20.")
        return await run("consistency", season, phase, team_id, stat, window)

    @router.get("/defense")
    async def defense(season: str = Query(..., min_length=7, max_length=7), phase: Phase = "Regular Season") -> dict:
        validate(season)
        return await run("defense", season, phase)

    @router.get("/slate")
    async def slate(
        season: str = Query(..., min_length=7, max_length=7),
        phase: Phase = "Regular Season",
        day: date = Query(...),
    ) -> dict:
        validate(season)
        return await run("slate", season, phase, day.isoformat())

    @router.get("/predictor")
    async def predictor(
        season: str = Query(..., min_length=7, max_length=7),
        phase: Phase = "Regular Season",
        player_id: int = Query(..., gt=0),
        team_id: int = Query(..., gt=0),
        opponent_id: int = Query(..., gt=0),
        minutes: float = Query(..., gt=0, le=60, allow_inf_nan=False),
        day: date = Query(...),
        rest_days: float | None = Query(None, ge=0, le=5, allow_inf_nan=False),
        is_home: bool | None = None,
        def_rating: float | None = Query(None, gt=0, le=250, allow_inf_nan=False),
        league_def_rating: float | None = Query(None, gt=0, le=250, allow_inf_nan=False),
        pace: float | None = Query(None, gt=0, le=200, allow_inf_nan=False),
        league_pace: float | None = Query(None, gt=0, le=200, allow_inf_nan=False),
    ) -> dict:
        validate(season, team_id, opponent_id)
        if team_id == opponent_id:
            raise HTTPException(400, "Select different player and opponent teams.")
        overrides = {
            "rest_days": rest_days,
            "is_home": is_home,
            "def_rating": def_rating,
            "league_def_rating": league_def_rating,
            "pace": pace,
            "league_pace": league_pace,
        }
        return await run(
            "predictor", season, phase, player_id, team_id, opponent_id, minutes, day.isoformat(), overrides
        )

    @router.get("/picks")
    async def picks(q: str = Query("", max_length=200), filename: str | None = Query(None, max_length=100)) -> dict:
        return await run("picks", q, filename)

    @router.get("/catalog")
    async def catalog(q: str = Query("", max_length=200)) -> dict:
        return await run("catalog", q)

    return router
