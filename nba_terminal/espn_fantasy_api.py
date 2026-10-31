"""Loopback-only ESPN sessions. No OAuth, passwords, disk secrets, or transactions."""

from __future__ import annotations

import asyncio
import copy
import ipaddress
import json
import re
import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import partial
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request, Response

from nba_terminal.services.espn_fantasy import EspnClient, EspnError, team_choices, validate_team

router = APIRouter(prefix="/api/fantasy/espn", tags=["ESPN Fantasy"])
COOKIE = "nba_espn_session"
SESSION_TTL = 8 * 3600
CACHE_TTL = 60
MAX_SESSIONS = 64


def fail(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status, detail={"code": code, "message": message}, headers={"Cache-Control": "no-store"}
    )


def guard(request: Request, response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    host = request.url.hostname
    try:
        local_client = request.client is not None and ipaddress.ip_address(request.client.host).is_loopback
    except ValueError:
        local_client = False
    if host not in {"localhost", "127.0.0.1", "::1"} or not local_client:
        raise fail("local_only", "ESPN connections require a local single-process server on loopback.", 403)
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise fail("origin_denied", "Use the same-origin NBA Terminal page for ESPN requests.", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise fail("origin_denied", "Cross-site ESPN session access is disabled.", 403)
    if request.method in {"POST", "PUT", "DELETE"}:
        if request.headers.get("x-fantasy-request") != "1":
            raise fail("request_header_required", "Send X-Fantasy-Request: 1 from NBA Terminal.", 403)
        if request.method != "DELETE" and request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise fail("json_required", "Send connection details as JSON.", 415)


async def body(request: Request, *, connect: bool = False) -> dict:
    # Manual validation avoids FastAPI validation errors echoing private cookie input.
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 16_384:
            raise fail("body_too_large", "Connection request exceeds the safe size limit.", 413)
    try:
        data = json.loads(content)
    except (ValueError, UnicodeError):
        raise fail("invalid_json", "Send a valid JSON object.") from None
    allowed = {"team_id", "league_id", "season_id", "swid", "espn_s2"} if connect else {"team_id"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise fail("invalid_fields", "Connection request contains unsupported fields.")
    for key, minimum, maximum in (("team_id", 1, 1_000_000), ("league_id", 1, 2**53), ("season_id", 2019, 2100)):
        if not connect and key != "team_id":
            continue
        value = data.get(key)
        if connect and key == "team_id" and value is None:
            continue
        if type(value) is not int or not minimum <= value <= maximum:
            raise fail("invalid_fields", "Supply valid positive league/team IDs and an ESPN ending season year.")
    if connect:
        swid, s2 = data.get("swid"), data.get("espn_s2")
        if bool(swid) != bool(s2):
            raise fail("cookies_required", "Private league access requires both SWID and espn_s2 cookies.")
        if swid is not None or s2 is not None:
            if (
                not isinstance(swid, str)
                or not re.fullmatch(r"\{?[a-zA-Z0-9-]{16,64}\}?", swid)
                or not isinstance(s2, str)
                or not 1 <= len(s2) <= 8192
                or any(ord(char) < 33 or ord(char) > 126 or char in ';,"\\' for char in s2)
            ):
                raise fail("invalid_cookies", "The supplied ESPN cookie format is invalid.")
    return data


@dataclass(repr=False)
class Connection:
    client: EspnClient
    raw: dict
    team_id: int | None
    expires: float
    cached: dict | None = None
    cached_until: float = 0
    active: bool = True
    lock: Any = field(default_factory=threading.Lock)

    def status(self) -> dict:
        choices = team_choices(self.raw, self.client.swid)
        return {
            "connected": True,
            "league_id": self.client.league_id,
            "season_id": self.client.season_id,
            "team_id": self.team_id,
            "auth_mode": "private" if self.client.swid else "public",
            "ownership_verified": any(t["id"] == self.team_id and t["ownership_verified"] for t in choices),
            "teams": choices,
            "expires_at": datetime.fromtimestamp(self.expires, timezone.utc).isoformat(),
        }

    def clear(self) -> None:
        self.active = False
        self.client.clear()
        self.raw = {}
        self.cached = None


class SessionStore:
    def __init__(self) -> None:
        self.connections: dict[str, Connection] = {}
        self.lock = threading.Lock()

    def _prune(self) -> None:
        for token, conn in list(self.connections.items()):
            if conn.expires <= time.time():
                # Do not block the event loop waiting for a worker's connection lock.
                conn.active = False
                del self.connections[token]
                if conn.lock.acquire(blocking=False):
                    try:
                        conn.clear()
                    finally:
                        conn.lock.release()

    def get(self, token: str | None) -> Connection | None:
        with self.lock:
            self._prune()
            return self.connections.get(token or "")

    def add(self, conn: Connection, previous: str | None) -> str:
        with self.lock:
            self._prune()
            if len(self.connections) >= MAX_SESSIONS and previous not in self.connections:
                conn.clear()
                raise EspnError(
                    "sessions_full", "Local ESPN session capacity reached. Disconnect unused sessions.", 503
                )
            old = self.connections.pop(previous or "", None)
            if old:
                # Other worker calls check active before returning any result.
                old.active = False
                if old.lock.acquire(blocking=False):
                    try:
                        old.clear()
                    finally:
                        old.lock.release()
            token = secrets.token_urlsafe(32)
            self.connections[token] = conn
            return token

    def remove(self, token: str | None) -> Connection | None:
        with self.lock:
            conn = self.connections.pop(token or "", None)
            if conn:
                conn.active = False
            return conn


def store(request: Request) -> SessionStore:
    if not hasattr(request.app.state, "espn_sessions"):
        request.app.state.espn_sessions = SessionStore()
    return request.app.state.espn_sessions


def connection(request: Request) -> Connection:
    conn = store(request).get(request.cookies.get(COOKIE))
    if conn is None:
        raise fail("not_connected", "Connect an ESPN league first.", 401)
    return conn


async def worker(request: Request, function: Callable, *args: Any) -> Any:
    """Share the app's four NBA worker slots; release only after cancelled work finishes."""
    slots = request.app.state.espn_slots
    try:
        await asyncio.wait_for(slots.acquire(), timeout=0.05)
    except asyncio.TimeoutError:
        raise fail("busy", "NBA data workers are busy. Try again shortly.", 503) from None

    async def run() -> Any:
        try:
            return await asyncio.get_running_loop().run_in_executor(
                request.app.state.espn_pool, partial(function, *args)
            )
        except EspnError as exc:
            raise fail(exc.code, exc.message, exc.status) from None
        except Exception:
            # Intentionally avoid upstream exception repr/traceback: they may contain Cookie headers.
            raise fail("schema_changed", "ESPN data could not be safely processed.", 502) from None
        finally:
            slots.release()

    task = asyncio.create_task(run())
    # Retrieve eventual errors if the browser disconnects while a worker is finishing.
    task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
    return await asyncio.shield(task)


def ensure_active(conn: Connection) -> None:
    if not conn.active or conn.expires <= time.time():
        conn.clear()
        raise EspnError("not_connected", "The ESPN session expired or was disconnected.", 401)


@contextmanager
def session_lock(conn: Connection):
    with conn.lock:
        try:
            ensure_active(conn)
            yield
        finally:
            # Revoked/expired secrets are erased even if a pending upstream call failed.
            if not conn.active or conn.expires <= time.time():
                conn.clear()


def connect_sync(data: dict) -> Connection:
    client = EspnClient(data["league_id"], data["season_id"], data.get("swid"), data.get("espn_s2"))
    try:
        raw = client.league()
        team_id = data.get("team_id")
        if team_id is not None:
            validate_team(raw, team_id, client.swid)
        return Connection(client, raw, team_id, time.time() + SESSION_TTL)
    except Exception:
        client.clear()
        raise


@router.post("/connect")
async def connect(request: Request, response: Response) -> dict:
    guard(request, response)
    conn = await worker(request, connect_sync, await body(request, connect=True))
    try:
        token = store(request).add(conn, request.cookies.get(COOKIE))
    except EspnError as exc:
        raise fail(exc.code, exc.message, exc.status) from None
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/api/fantasy/espn",
    )
    return conn.status()


@router.get("/status")
async def status(request: Request, response: Response) -> dict:
    guard(request, response)
    conn = store(request).get(request.cookies.get(COOKIE))
    if conn is None:
        return {"connected": False}
    return await worker(request, status_sync, conn)


def status_sync(conn: Connection) -> dict:
    with session_lock(conn):
        return conn.status()


@router.put("/team")
async def select_team(request: Request, response: Response) -> dict:
    guard(request, response)
    conn, data = connection(request), await body(request)
    return await worker(request, select_sync, conn, data["team_id"])


def select_sync(conn: Connection, team_id: int) -> dict:
    with session_lock(conn):
        validate_team(conn.raw, team_id, conn.client.swid)
        conn.team_id, conn.cached = team_id, None
        return conn.status()


@router.delete("/connection")
async def disconnect(request: Request, response: Response) -> dict:
    guard(request, response)
    conn = store(request).remove(request.cookies.get(COOKIE))
    if conn:
        # Memory deletion is CPU-only; busy connection is already revoked and clears on return.
        if conn.lock.acquire(blocking=False):
            try:
                conn.clear()
            finally:
                conn.lock.release()
    response.delete_cookie(COOKIE, path="/api/fantasy/espn")
    return {"connected": False}


@router.get("/snapshot")
async def snapshot(request: Request, response: Response) -> dict:
    guard(request, response)
    refresh_raw = request.query_params.get("refresh", "false")
    compare_raw = request.query_params.get("compare_team_id")
    if refresh_raw not in {"true", "false"}:
        raise fail("invalid_query", "Refresh must be true or false.")
    comparison = None
    if compare_raw is not None:
        if not compare_raw.isascii() or not compare_raw.isdigit() or len(compare_raw) > 7:
            raise fail("invalid_query", "Comparison team ID must be a positive integer.")
        comparison = int(compare_raw)
        if not 1 <= comparison <= 1_000_000:
            raise fail("invalid_query", "Comparison team ID must be a valid league team ID.")
    return await worker(request, snapshot_sync, connection(request), refresh_raw == "true", comparison)


def snapshot_sync(conn: Connection, refresh: bool, compare_team_id: int | None) -> dict:
    with session_lock(conn):
        if conn.team_id is None:
            raise EspnError("team_required", "Select your team before fetching a matchup.", 409)
        # Cache full normalized data once; changing comparison is pure and does not refetch.
        if refresh or conn.cached is None or conn.cached_until <= time.monotonic():
            raw = conn.client.league()
            result = conn.client.snapshot(raw, conn.team_id)
            ensure_active(conn)
            conn.raw, conn.cached = raw, result
            conn.cached_until = time.monotonic() + CACHE_TTL
        result = copy.deepcopy(conn.cached)
        if compare_team_id is not None:
            from nba_terminal.services.espn_fantasy import compare_categories

            teams = {team["id"]: team for team in result["teams"]}
            if compare_team_id not in teams:
                raise EspnError("team_not_found", "Comparison team is not in this league.", 400)
            result["comparison"] = compare_categories(
                teams[conn.team_id]["totals"],
                teams[compare_team_id]["totals"],
                result["league"]["categories"],
                compare_team_id,
            )
        ensure_active(conn)
        return result


@router.post("/plan")
async def waiver_plan(request: Request, response: Response) -> dict:
    """Read-only modeling using this session's server-owned snapshot and bounded pool."""
    guard(request, response)
    conn = connection(request)
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 65_536:
            raise fail("body_too_large", "Planner inputs exceed the safe size limit.", 413)
    try:
        preferences = json.loads(content)
    except (ValueError, UnicodeError):
        raise fail("invalid_json", "Send valid planner preferences.") from None
    allowed = {
        "context",
        "user_confirmed_counts",
        "user_confirmed_eligibility",
        "candidate_ids",
        "droppable_ids",
        "protected_ids",
        "max_stream_slots",
        "weekly_add_limit",
        "used_adds",
        "available_adds",
        "uncertainty_mode",
        "margin_sd",
        "player_overrides",
        "remaining_dates",
    }
    if not isinstance(preferences, dict) or set(preferences) - allowed:
        raise fail("invalid_fields", "Send planner preferences only; league facts come from the server.")
    return await worker(request, plan_sync, conn, preferences)


def plan_sync(conn: Connection, preferences: dict) -> dict:
    from nba_terminal.services.fantasy_planner_adapter import plan_snapshot_waivers

    current = snapshot_sync(conn, False, None)
    with session_lock(conn):
        # Team selection/refresh could have raced the preceding snapshot read.
        if conn.team_id != current["selected_team_id"] or conn.cached != current:
            raise EspnError("snapshot_changed", "League data changed. Refresh and reconfirm planner inputs.", 409)
        result = plan_snapshot_waivers(current, preferences)
        ensure_active(conn)
        return result
