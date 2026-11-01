"""FastAPI entry point for the NBA Terminal web application."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from nba_terminal.espn_fantasy_api import router as espn_fantasy_router
from nba_terminal.fantasy_api import router as fantasy_router
from nba_terminal.legacy_tools_api import create_legacy_tools_router
from nba_terminal.services import game_center, player_data
from nba_terminal.services import player_analysis as player_analysis_service
from nba_terminal.services.nba_http import configure_nba_stats_client

WEB_DIR = Path(__file__).with_name("web")
WEB_DIST = WEB_DIR / "dist"
MAX_API_WORKERS = 4
NBA_POOL = ThreadPoolExecutor(max_workers=MAX_API_WORKERS, thread_name_prefix="nba-api")
NBA_SLOTS = asyncio.Semaphore(MAX_API_WORKERS)
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()
_inflight: dict[str, asyncio.Task[Any]] = {}
logger = logging.getLogger(__name__)

app = FastAPI(title="NBA Terminal", docs_url=None, redoc_url=None)


async def _cached_call(key: str, ttl: int, function: Callable[..., Any], *args: Any) -> Any:
    """Deduplicate concurrent cache misses and run NBA work away from the event loop."""
    loop = asyncio.get_running_loop()
    async with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > loop.time():
            return cached[1]
        task = _inflight.get(key)
        if task is None:
            task = asyncio.create_task(_fetch_and_cache(key, ttl, function, args))
            _inflight[key] = task
    return await asyncio.shield(task)


async def _fetch_and_cache(key: str, ttl: int, function: Callable[..., Any], args: tuple[Any, ...]) -> Any:
    """Fetch one cache key, log its underlying failure, and cache successful results."""
    loop = asyncio.get_running_loop()
    acquired = False
    try:
        try:
            await asyncio.wait_for(NBA_SLOTS.acquire(), timeout=0.05)
            acquired = True
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="NBA data service is busy. Try again shortly.") from None
        try:
            result = await loop.run_in_executor(NBA_POOL, partial(_run_nba_fetch, function, *args))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception(
                "NBA data fetch failed: cache_key=%s service=%s",
                key,
                getattr(function, "__name__", type(function).__name__),
            )
            raise HTTPException(
                status_code=502,
                detail="NBA Stats could not return this data. Check server logs for the upstream cause.",
            ) from exc
        transient_error_states = {"shot_chart_state", "advanced_stats_state", "history_state", "state"}
        cache_result = not (
            isinstance(result, dict) and any(result.get(state) == "error" for state in transient_error_states)
        )
        async with _cache_lock:
            if cache_result:
                _cache[key] = (loop.time() + ttl, result)
            if len(_cache) > 250:
                expired = [entry for entry, value in _cache.items() if value[0] <= loop.time()]
                for entry in expired:
                    _cache.pop(entry, None)
                if len(_cache) > 250:
                    _cache.pop(next(iter(_cache)))
        return result
    finally:
        if acquired:
            NBA_SLOTS.release()
        async with _cache_lock:
            _inflight.pop(key, None)


def _run_nba_fetch(function: Callable[..., Any], *args: Any) -> Any:
    """Install conservative Stats API transport settings before the first request."""
    configure_nba_stats_client()
    return function(*args)


app.state.cached_nba_call = _cached_call
app.include_router(fantasy_router)
app.include_router(create_legacy_tools_router(_cached_call))
app.state.espn_pool = NBA_POOL
app.state.espn_slots = NBA_SLOTS
app.include_router(espn_fantasy_router)


@app.get("/")
@app.get("/fantasy")
@app.get("/players")
@app.get("/players/{player_id}")
@app.get("/tools")
@app.get("/tools/{tool}")
async def index() -> FileResponse:
    if not (WEB_DIST / "index.html").is_file():
        raise HTTPException(status_code=503, detail="Web client is not built. Run `bun run build` in nba_terminal/web.")
    return FileResponse(WEB_DIST / "index.html")


@app.get("/game/{path:path}")
async def game_page(path: str) -> FileResponse:
    """Serve the browser shell for shareable game and player detail URLs."""
    if not (WEB_DIST / "index.html").is_file():
        raise HTTPException(status_code=503, detail="Web client is not built. Run `bun run build` in nba_terminal/web.")
    return FileResponse(WEB_DIST / "index.html")


@app.get("/assets/{filename:path}")
async def asset(filename: str) -> FileResponse:
    assets_dir = (WEB_DIST / "assets").resolve()
    candidate = (assets_dir / filename).resolve()
    if assets_dir not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(candidate)


@app.get("/api/meta")
async def metadata() -> dict[str, Any]:
    today = game_center.nba_today()
    return {
        "current_season": game_center.current_season(today),
        "seasons": game_center.available_seasons(today),
        "supported_from": game_center.SUPPORTED_FROM,
    }


@app.get("/api/upcoming")
async def upcoming() -> dict[str, Any]:
    today = game_center.nba_today()
    season = game_center.current_season(today)
    schedule = await _cached_call(f"schedule:{season}", 120, game_center.fetch_season_schedule, season)
    return await _cached_call(f"upcoming:{today.isoformat()}", 120, game_center.fetch_upcoming_games, today, schedule)


@app.get("/api/games")
async def games(season: str = Query(..., min_length=7, max_length=7)) -> dict[str, Any]:
    schedule = await _cached_call(f"schedule:{season}", 120, game_center.fetch_season_schedule, season)
    return await _cached_call(f"games:{season}", 900, game_center.fetch_recent_games, season, schedule)


@app.get("/api/games/{game_id}")
async def game(game_id: str, season: str | None = None) -> dict[str, Any]:
    return await _cached_call(
        f"game:{game_id}:{season or 'from-game-id'}",
        3600,
        game_center.fetch_game_boxscore,
        game_id,
        season,
    )


@app.get("/api/games/{game_id}/players/{player_id}")
async def player_analysis(
    game_id: str,
    player_id: int,
    season: str = Query(..., min_length=7, max_length=7),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    if phase not in game_center.GAME_PHASES:
        raise HTTPException(status_code=400, detail="Unsupported season phase.")
    return await _cached_call(
        f"player:{game_id}:{player_id}:{season}:{phase}",
        3600,
        player_analysis_service.fetch_player_game_analysis,
        game_id,
        player_id,
        season,
        phase,
    )


@app.get("/api/players")
async def search_players(q: str = Query("", max_length=100)) -> dict[str, Any]:
    return {"players": player_data.search_players(q)}


def _validate_player_scope(season: str, phase: str) -> None:
    if phase not in game_center.GAME_PHASES:
        raise HTTPException(status_code=400, detail="Unsupported season phase.")
    if int(season[-2:]) != (int(season[:4]) + 1) % 100:
        raise HTTPException(status_code=400, detail="Season must use consecutive years, for example 2025-26.")


@app.get("/api/players/{player_id}")
async def player_profile(
    player_id: int,
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    _validate_player_scope(season, phase)
    profile = await _cached_call(
        f"profile:{player_id}:{season}:{phase}",
        900,
        player_analysis_service.fetch_player_profile,
        player_id,
        season,
        phase,
    )
    dashboard = await _cached_call(
        f"season-advanced:{season}:{phase}",
        900,
        player_analysis_service.fetch_season_advanced,
        season,
        phase,
    )
    row = dashboard["players"].get(str(player_id), {})
    state = "available" if row else "error" if dashboard["state"] == "error" else "unavailable"
    return {
        **profile,
        "advanced": row,
        "advanced_state": state,
        "advanced_note": dashboard["note"] or ("No advanced season line returned." if not row else ""),
        "advanced_source": "LeagueDashPlayerStats · Advanced · PerGame",
    }


@app.get("/api/players/{player_id}/measures/{measure}")
async def player_measure(
    player_id: int,
    measure: str,
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    _validate_player_scope(season, phase)
    if measure not in player_data.PLAYER_PROFILE_MEASURES:
        raise HTTPException(status_code=400, detail="Unsupported profile measure.")
    dashboard = await _cached_call(
        f"season-{measure.lower()}:{season}:{phase}",
        900,
        player_analysis_service.fetch_season_advanced,
        season,
        phase,
        measure,
    )
    row = dashboard["players"].get(str(player_id), {})
    return {
        "measure": measure,
        "row": row,
        "state": "available" if row else "error" if dashboard["state"] == "error" else "unavailable",
        "note": dashboard["note"] or ("No season line returned for this player." if not row else ""),
        "source": f"LeagueDashPlayerStats · {measure} · PerGame",
        "season": season,
        "phase": phase,
    }


@app.get("/api/players/{player_id}/shooting")
async def player_shooting(
    player_id: int,
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    _validate_player_scope(season, phase)
    return await _cached_call(
        f"shooting:{player_id}:{season}:{phase}",
        900,
        player_analysis_service.fetch_player_shooting_tables,
        player_id,
        season,
        phase,
    )


@app.get("/api/players/{player_id}/history")
async def player_history(
    player_id: int,
    season: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    _validate_player_scope(season, phase)
    return await _cached_call(
        f"profile:{player_id}:{season}:{phase}",
        900,
        player_analysis_service.fetch_player_profile,
        player_id,
        season,
        phase,
    )


def main() -> None:
    """Run the web service on the local machine."""
    uvicorn.run("nba_terminal.webapp:app", host="127.0.0.1", port=8000, workers=1)
