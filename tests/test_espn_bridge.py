"""Real ASGI bridge routes, synthetic ESPN/browser boundaries only."""

import asyncio
import json
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path

import httpx2 as httpx
import pytest

from nba_terminal import espn_fantasy_api as api
from nba_terminal import webapp
from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services.espn_bridge import BridgeStore

P = "/api/fantasy/espn"
H = {"X-Fantasy-Request": "1"}
CONFIG = {"league_id": 123, "season_id": 2027, "team_id": 1}
PRIVATE = {"league_id": 123, "season_id": 2027, "swid": "fixture-owner-0001", "espn_s2": "synthetic-secret"}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())["league"]
    monkeypatch.setattr(webapp.app.state, "espn_sessions", api.SessionStore(), raising=False)
    monkeypatch.setattr(webapp.app.state, "espn_bridges", BridgeStore(), raising=False)
    monkeypatch.setattr(webapp.app.state, "espn_slots", asyncio.Semaphore(4))
    monkeypatch.setattr(espn.EspnClient, "league", lambda self: raw)
    return raw


def browser():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=webapp.app), base_url="http://127.0.0.1")


async def pair(b, data=None):
    r = await b.post(P + "/bridge/pair", json=CONFIG if data is None else data, headers=H)
    assert r.status_code == 200, r.text
    assert "HttpOnly" in r.headers["set-cookie"]
    return r


async def ticket(b):
    r = await b.post(P + "/bridge/challenge", json={}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()["nonce"]


async def refresh(b, **changes):
    return await b.post(P + "/bridge/refresh", headers=H, json={**PRIVATE, "nonce": await ticket(b), **changes})


def test_existing_login_renewal_selection_rotation_and_replay():
    async def run():
        async with browser() as b, browser() as other:
            assert (await b.get(P + "/bridge/status")).json() == {"enabled": False}
            await pair(b)
            first = await refresh(b)
            assert first.status_code == 200
            assert first.json()["state"] == "connected"
            token = b.cookies.get(api.COOKIE)
            conn = webapp.app.state.espn_sessions.get(token)
            assert (await b.get(P + "/status")).json()["ownership_verified"]
            assert not (await other.get(P + "/status")).json()["connected"]
            assert (await other.post(P + "/bridge/challenge", json={}, headers=H)).status_code == 401
            # Submitted team_id cannot override user's server-owned selection.
            response = await refresh(b, team_id=2)
            assert response.status_code == 200 and response.json()["team_id"] == 1
            assert b.cookies.get(api.COOKIE) != token and not conn.active
            nonce = await ticket(b)
            response = await b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce}, headers=H)
            assert response.status_code == 200
            replay = await b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce}, headers=H)
            assert replay.status_code == 409
            text = response.text + (await b.get(P + "/bridge/status")).text
            assert PRIVATE["swid"] not in text and PRIVATE["espn_s2"] not in text
            await b.delete(P + "/connection", headers=H)
            assert (await b.get(P + "/bridge/status")).json() == {"enabled": False}
            assert (await b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce}, headers=H)).status_code == 401

    asyncio.run(run())


@pytest.mark.parametrize("state", ["permission_denied", "no_espn_session", "account_changed", "error"])
def test_missing_permission_logout_or_missing_cookie_revokes(state):
    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            data = {"league_id": 123, "season_id": 2027, "nonce": await ticket(b), "state": state}
            r = await b.post(P + "/bridge/refresh", json=data, headers=H)
            assert r.status_code == 200 and r.json()["state"] == state
            assert not (await b.get(P + "/status")).json()["connected"]

    asyncio.run(run())


def test_account_change_expired_and_unauthorized_revoke(monkeypatch):
    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            changed = await refresh(b, swid="different-owner-0001")
            assert changed.status_code == 409
            assert (await b.get(P + "/bridge/status")).json()["state"] == "account_changed"
            assert not (await b.get(P + "/status")).json()["connected"]
            await pair(b, {"league_id": 123, "season_id": 2027})
            denied = await refresh(b, swid="different-owner-0001")
            assert denied.status_code == 403
            assert not (await b.get(P + "/status")).json()["connected"]

            def expired(self):
                raise espn.EspnError("access_denied", "ESPN denied access.", 401)

            monkeypatch.setattr(espn.EspnClient, "league", expired)
            assert (await refresh(b)).status_code == 401
            assert (await b.get(P + "/bridge/status")).json()["state"] == "error"

    asyncio.run(run())


def test_forgery_cross_origin_invalid_body_and_expired_tickets():
    async def run():
        async with browser() as b:
            assert (await b.post(P + "/bridge/pair", json=CONFIG)).status_code == 403
            for origin in ["https://evil.example", "moz-extension://fake", "http://localhost:5173"]:
                r = await b.post(P + "/bridge/pair", json=CONFIG, headers={**H, "Origin": origin})
                assert r.status_code == 403
            assert (await b.post(P + "/bridge/pair", json={**CONFIG, "espn_s2": "no"}, headers=H)).status_code == 400
            await pair(b)
            for data in [{**PRIVATE, "nonce": "forged"}, {**PRIVATE, "nonce": 1}, {**PRIVATE, "extra": "secret"}]:
                assert (await b.post(P + "/bridge/refresh", json=data, headers=H)).status_code in (400, 409)
            nonce = await ticket(b)
            pairing = next(iter(webapp.app.state.espn_bridges.pairs.values()))
            pairing.nonce_until = time.time() - 1
            assert (await b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce}, headers=H)).status_code == 409
            nonce = await ticket(b)
            r = await b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce, "league_id": 124}, headers=H)
            assert r.status_code == 409
            pairing.expires = time.time() - 1
            assert (await b.get(P + "/bridge/status")).json() == {"enabled": False}

    asyncio.run(run())


def test_disconnect_during_worker_cannot_resurrect_and_concurrent_refresh(monkeypatch, isolated):
    entered, release = threading.Event(), threading.Event()

    def slow(self):
        entered.set()
        assert release.wait(5)
        return isolated

    monkeypatch.setattr(espn.EspnClient, "league", slow)

    async def run():
        async with browser() as b:
            await pair(b)
            nonce = await ticket(b)
            pending = asyncio.create_task(b.post(P + "/bridge/refresh", json={**PRIVATE, "nonce": nonce}, headers=H))
            assert await asyncio.to_thread(entered.wait, 3)
            concurrent = await b.post(P + "/bridge/challenge", json={}, headers=H)
            assert concurrent.status_code == 409
            await b.delete(P + "/connection", headers=H)
            release.set()
            assert (await pending).status_code == 409
            assert not (await b.get(P + "/status")).json()["connected"]
            assert not webapp.app.state.espn_sessions.connections

    try:
        asyncio.run(run())
    finally:
        release.set()


def test_real_downloaded_packages_are_allowlisted_and_complete():
    async def run():
        async with browser() as b:
            for target in ["firefox", "chromium"]:
                response = await b.get(P + f"/bridge/setup/{target}.zip")
                assert response.status_code == 200
                with zipfile.ZipFile(BytesIO(response.content)) as z:
                    manifest = json.loads(z.read("manifest.json"))
                    assert manifest["manifest_version"] == 3
                    assert manifest["optional_permissions"] == ["cookies"]
                    assert "externally_connectable" not in manifest
                    assert "https://*.espn.com/*" in manifest["optional_host_permissions"]
                    assert {"background.js", "content.js", "popup.html", "popup.js"} <= set(z.namelist())
            assert (await b.get(P + "/bridge/setup/instructions.md")).status_code == 200
            assert (await b.get(P + "/bridge/setup/arbitrary.txt")).status_code == 404

    asyncio.run(run())


def test_transient_failure_preserves_prior_valid_session_and_manual_fallback_disables_bridge(monkeypatch):
    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            original = espn.EspnClient.league

            def unavailable(self):
                raise espn.EspnError("upstream_error", "ESPN is unavailable.", 502)

            monkeypatch.setattr(espn.EspnClient, "league", unavailable)
            assert (await refresh(b)).status_code == 502
            assert (await b.get(P + "/status")).json()["connected"]
            monkeypatch.setattr(espn.EspnClient, "league", original)
            assert (await b.post(P + "/connect", json=CONFIG, headers=H)).status_code == 200
            assert (await b.get(P + "/bridge/status")).json() == {"enabled": False}

    asyncio.run(run())


def test_account_change_latches_and_successful_team_selection_survives_expiry(monkeypatch, isolated):
    isolated["teams"][1]["owners"] = ["fixture-owner-0001"]

    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            assert (await b.put(P + "/team", json={"team_id": 2}, headers=H)).status_code == 200
            conn = webapp.app.state.espn_sessions.get(b.cookies.get(api.COOKIE))
            conn.expires = time.time() - 1
            assert (await refresh(b)).json()["team_id"] == 2
            assert (await refresh(b, swid="different-owner-0001")).status_code == 409
            # Returning to original account still requires explicit pair consent.
            assert (await refresh(b)).status_code == 409
            assert not (await b.get(P + "/status")).json()["connected"]

    asyncio.run(run())


def test_pair_capacity_and_bound_origin():
    from nba_terminal.services.espn_bridge import Pair

    pairs = BridgeStore()
    token, item = pairs.add("http://localhost:5173", CONFIG)
    assert pairs.get(token, "http://localhost:5174") is None
    assert pairs.get(token, "http://localhost:5173") is item
    for n in range(63):
        pairs.pairs[str(n)] = Pair("http://localhost:5173", 1, 2027, None)
    with pytest.raises(espn.EspnError, match="Disconnect"):
        pairs.add("http://localhost:5173", CONFIG)
    assert pairs.remove(token) is item and not item.active


def test_bridge_malformed_state_and_unicode_nonce_are_safe_errors():
    async def run():
        async with browser() as b:
            await pair(b)
            for changes in [{"state": {}}, {"state": []}, {"state": "unsupported"}, {"nonce": "é"}]:
                response = await b.post(
                    P + "/bridge/refresh", headers=H, json={**PRIVATE, "nonce": await ticket(b), **changes}
                )
                assert response.status_code in (400, 409)
                assert PRIVATE["espn_s2"] not in response.text

    asyncio.run(run())
