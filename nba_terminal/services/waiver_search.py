"""Session-owned, bounded local continuations. This module never calls a provider."""

import copy
import secrets
import threading
import time
import weakref
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from nba_terminal.services import fantasy_planner_adapter as adapter
from nba_terminal.services.espn_fantasy import EspnError

MAX_SEARCHES = 8
IDLE_TTL = 180
_registry = weakref.WeakSet()
_registry_lock = threading.Lock()


class WaiverSearch:
    def __init__(self, conn, snapshot, preferences):
        self.id = secrets.token_urlsafe(24)
        self.source = conn.cached
        self.team_id = conn.team_id
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.touched = time.monotonic()
        self.finished = False
        self.latest = None
        now = adapter.datetime.now(timezone.utc)
        tomorrow = now.astimezone(ZoneInfo("America/New_York")).date() + timedelta(days=1)
        self.valid_until = datetime.combine(tomorrow, datetime.min.time(), ZoneInfo("America/New_York"))
        # Any newly locked game or expired user declaration requires a new frozen
        # input. A progress request must never fetch actuals or reinterpret a lock.
        players = [p for t in snapshot["teams"] for p in t["roster"]] + snapshot.get("free_agents", [])
        for player in players:
            for game in player.get("schedule") or []:
                try:
                    start = datetime.fromisoformat(game["start_at"].replace("Z", "+00:00"))
                    if start > now:
                        self.valid_until = min(self.valid_until, start)
                except (KeyError, ValueError, TypeError, AttributeError):
                    # Adapter reports incomplete timing and withholds actions.
                    continue
        declaration = preferences.get("usage_declaration")
        expiry = declaration.get("expires_at") if isinstance(declaration, dict) else None
        if expiry:
            try:
                self.valid_until = min(self.valid_until, datetime.fromisoformat(expiry.replace("Z", "+00:00")))
            except (ValueError, TypeError):
                self.valid_until = now
        self.iterator = adapter.iter_snapshot_waivers(
            copy.deepcopy(snapshot),
            copy.deepcopy(preferences),
            now,
            progressive=True,
            cancelled=self.cancelled.is_set,
        )

    def valid(self, conn):
        return (
            conn.search is self
            and conn.active
            and conn.expires > time.time()
            and conn.cached is self.source
            and conn.team_id == self.team_id
            and adapter.datetime.now(timezone.utc) < self.valid_until
        )

    def cancel(self):
        self.cancelled.set()
        # Never close a generator while another thread is advancing it.
        if self.lock.acquire(blocking=False):
            try:
                self.iterator.close()
            finally:
                self.lock.release()

    def advance(self, conn):
        if not self.lock.acquire(blocking=False):
            raise EspnError("busy", "This local search is already advancing.", 503)
        try:
            if time.monotonic() - self.touched > IDLE_TTL:
                self.cancelled.set()
                self.iterator.close()
                raise EspnError("search_expired", "Local search expired. Start a new analysis.", 409)
            self.touched = time.monotonic()
            if not self.valid(conn):
                self.cancelled.set()
                self.iterator.close()
                raise EspnError("snapshot_changed", "League facts or game locks changed. Refresh analysis.", 409)
            if not self.cancelled.is_set() and not self.finished:
                value = next(self.iterator, None)
                if value is not None:
                    self.latest = value
                self.finished = value is None or value.get("search", {}).get("phase") != "searching"
            # Refresh, disconnect and preference replacement can race CPU work.
            if not self.valid(conn):
                self.cancelled.set()
                self.iterator.close()
                raise EspnError("snapshot_changed", "League facts changed during analysis.", 409)
            if self.latest is None:
                raise EspnError("search_cancelled", "Local search was cancelled.", 409)
            result = copy.deepcopy(self.latest)
            result.setdefault("search", {}).update(
                job_id=self.id,
                phase="cancelled" if self.cancelled.is_set() else "finished" if self.finished else "searching",
                complete=self.finished and not self.cancelled.is_set(),
            )
            if conn.refresh_failed:
                result.update(status="incomplete", read_only=True, freshness="saved_after_refresh_failure")
                result.setdefault("reasons", []).append(
                    "Provider refresh failed; retained frozen-input result is read-only."
                )
            return result
        finally:
            if self.cancelled.is_set() or self.finished:
                self.iterator.close()
            self.lock.release()


def start_search(conn, snapshot, preferences):
    """At most one retained continuation per session, eight across the process."""
    previous = getattr(conn, "search", None)
    if previous:
        previous.cancel()
    with _registry_lock:
        for job in list(_registry):
            if time.monotonic() - job.touched > IDLE_TTL:
                job.cancel()
        live = [j for j in _registry if not j.cancelled.is_set() and not j.finished]
        if len(live) >= MAX_SEARCHES:
            raise EspnError("busy", "Local search workers are full. Retry shortly.", 503)
        job = WaiverSearch(conn, snapshot, preferences)
        _registry.add(job)
        conn.search = job
    return job
