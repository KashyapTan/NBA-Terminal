"""Memory-only, browser-cookie-bound extension pairing and single-use refresh tickets."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from nba_terminal.services.espn_fantasy import EspnError

PAIR_TTL = 30 * 24 * 3600


@dataclass(repr=False)
class Pair:
    origin: str
    league_id: int
    season_id: int
    team_id: int | None
    expires: float = field(default_factory=lambda: time.time() + PAIR_TTL)
    state: str = "waiting_extension"
    account: str | None = None
    nonce: str | None = None
    nonce_until: float = 0
    busy: bool = False
    active: bool = True
    session: str | None = None

    def status(self) -> dict:
        return {
            "enabled": True,
            "league_id": self.league_id,
            "season_id": self.season_id,
            "team_id": self.team_id,
            "state": self.state,
        }


class BridgeStore:
    def __init__(self):
        self.pairs: dict[str, Pair] = {}
        self.lock = threading.RLock()

    def get(self, token: str | None, origin: str) -> Pair | None:
        with self.lock:
            for key, pair in list(self.pairs.items()):
                if pair.expires <= time.time():
                    pair.active = False
                    del self.pairs[key]
            pair = self.pairs.get(token or "")
            return pair if pair and pair.active and pair.origin == origin else None

    def add(self, origin: str, data: dict) -> tuple[str, Pair]:
        with self.lock:
            self.get(None, origin)
            if len(self.pairs) >= 64:
                raise EspnError("sessions_full", "Disconnect unused local browser pairings.", 503)
            token = secrets.token_urlsafe(32)
            pair = Pair(origin, data["league_id"], data["season_id"], data.get("team_id"))
            self.pairs[token] = pair
            return token, pair

    def remove(self, token: str | None) -> Pair | None:
        with self.lock:
            pair = self.pairs.pop(token or "", None)
            if pair:
                pair.active, pair.nonce = False, None
            return pair

    def challenge(self, pair: Pair) -> str:
        with self.lock:
            if pair.busy:
                raise EspnError("busy", "An ESPN refresh is already in progress.", 409)
            pair.nonce = secrets.token_urlsafe(32)
            pair.nonce_until = time.time() + 30
            return pair.nonce

    def consume(self, pair: Pair, nonce: str) -> None:
        with self.lock:
            if (
                not pair.active
                or pair.busy
                or not pair.nonce
                or pair.nonce_until <= time.time()
                or not secrets.compare_digest(pair.nonce, nonce)
            ):
                raise EspnError("bridge_ticket_invalid", "Restart the local extension refresh.", 409)
            pair.nonce, pair.busy = None, True
