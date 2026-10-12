"""HTTP routes for the Fantasy workspace."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request

from nba_terminal.services import fantasy

router = APIRouter()


@router.get("/api/fantasy/players")
async def fantasy_players(
    request: Request,
    season: str = Query(..., min_length=7, max_length=7, pattern=r"^\d{4}-\d{2}$"),
) -> dict[str, Any]:
    """Return one cached, batched regular-season player totals response."""
    try:
        fantasy.season_start_year(season)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cached_call: Callable[..., Awaitable[Any]] = request.app.state.cached_nba_call
    return await cached_call(
        f"fantasy:{season}:regular",
        1800,
        fantasy.fetch_fantasy_season,
        season,
    )
