"""FastAPI entry point for the NBA Terminal web application."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from nba_terminal.services import game_center

WEB_DIR = Path(__file__).with_name("web")
WEB_DIST = WEB_DIR / "dist"
MAX_API_WORKERS = 4
NBA_POOL = ThreadPoolExecutor(max_workers=MAX_API_WORKERS, thread_name_prefix="nba-api")
NBA_SLOTS = asyncio.Semaphore(MAX_API_WORKERS)
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()

app = FastAPI(title="NBA Terminal", docs_url=None, redoc_url=None)


async def _cached_call(key: str, ttl: int, function: Callable[..., Any], *args: Any) -> Any:
    """Run NBA I/O away from the event loop and retain successful reads briefly."""
    loop = asyncio.get_running_loop()
    async with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > loop.time():
            return cached[1]
    try:
        await asyncio.wait_for(NBA_SLOTS.acquire(), timeout=0.05)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="NBA data service is busy. Try again shortly.") from None
    try:
        result = await loop.run_in_executor(NBA_POOL, partial(function, *args))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="NBA Stats could not return this data. Please retry.") from exc
    finally:
        NBA_SLOTS.release()
    async with _cache_lock:
        cache_result = not (isinstance(result, dict) and result.get("shot_chart_state") == "error")
        if cache_result:
            _cache[key] = (loop.time() + ttl, result)
        if len(_cache) > 250:
            expired = [entry for entry, value in _cache.items() if value[0] <= loop.time()]
            for entry in expired:
                _cache.pop(entry, None)
            if len(_cache) > 250:
                _cache.pop(next(iter(_cache)))
    return result


@app.get("/")
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
    today = date.today()
    return {"current_season": game_center.current_season(today),
            "seasons": game_center.available_seasons(today),
            "supported_from": game_center.SUPPORTED_FROM}


@app.get("/api/upcoming")
async def upcoming() -> dict[str, Any]:
    return await _cached_call(f"upcoming:{date.today().isoformat()}", 120, game_center.fetch_upcoming_games)


@app.get("/api/games")
async def games(season: str = Query(..., min_length=7, max_length=7)) -> dict[str, Any]:
    return await _cached_call(f"games:{season}", 900, game_center.fetch_recent_games, season)


@app.get("/api/games/{game_id}")
async def game(game_id: str) -> dict[str, Any]:
    return await _cached_call(f"game:{game_id}", 3600, game_center.fetch_game_boxscore, game_id)


@app.get("/api/games/{game_id}/players/{player_id}")
async def player_analysis(
    game_id: str,
    player_id: int,
    season: str = Query(..., min_length=7, max_length=7),
    phase: str = Query("Regular Season", max_length=30),
) -> dict[str, Any]:
    if phase not in game_center.PHASES:
        raise HTTPException(status_code=400, detail="Unsupported season phase.")
    return await _cached_call(
        f"player:{game_id}:{player_id}:{season}:{phase}", 3600,
        game_center.fetch_player_game_analysis, game_id, player_id, season, phase,
    )


def main() -> None:
    """Run the web service on the local machine."""
    uvicorn.run("nba_terminal.webapp:app", host="127.0.0.1", port=8000, workers=1)
