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
            assert b.cookies.get(api.COOKIE) == token and conn.active
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


@pytest.mark.parametrize("state", ["permission_denied", "no_espn_session", "account_changed"])
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


def test_generic_extension_refresh_error_retains_valid_context_and_recovers(monkeypatch):
    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            before = await b.get(P + "/snapshot")
            assert before.status_code == 200
            data = {"league_id": 123, "season_id": 2027, "nonce": await ticket(b), "state": "error"}
            assert (await b.post(P + "/bridge/refresh", json=data, headers=H)).status_code == 200
            status = (await b.get(P + "/status")).json()
            assert status["connected"] and status["refresh_failed"]
            # Recovery uses existing server-owned auth/team; no new browser login.
            recovered = await b.get(P + "/snapshot")
            assert recovered.status_code == 200
            assert recovered.json()["selected_team_id"] == before.json()["selected_team_id"]
            assert not (await b.get(P + "/status")).json()["refresh_failed"]

    asyncio.run(run())


@pytest.mark.parametrize("status", [409, 429, 503, 504])
def test_transient_refresh_preserves_session_identity_and_prior_cache(monkeypatch, status):
    async def run():
        async with browser() as b:
            await pair(b)
            assert (await refresh(b)).status_code == 200
            token = b.cookies.get(api.COOKIE)
            conn = webapp.app.state.espn_sessions.get(token)
            cached = {"selected_team_id": 1, "source_fact": "retained"}
            conn.cached = cached
            identity = conn.status()["context_id"]

            def failed(data):
                raise espn.EspnError("transient", "Safe synthetic transient", status)

            with monkeypatch.context() as patch:
                patch.setattr(api, "bridge_connect_sync", failed)
                assert (await refresh(b)).status_code == status
            health = (await b.get(P + "/status")).json()
            assert health["connected"] and health["refresh_failed"]
            assert conn.active and conn.cached == cached
            assert (await refresh(b)).status_code == 200
            health = (await b.get(P + "/status")).json()
            assert health["context_id"] == identity
            assert health["refresh_failed"]
            monkeypatch.setattr(conn.client, "snapshot", lambda raw, team: cached)
            assert (await b.get(P + "/snapshot?refresh=true")).status_code == 200
            assert not (await b.get(P + "/status")).json()["refresh_failed"]
            assert b.cookies.get(api.COOKIE) == token
            assert conn.cached == cached

    asyncio.run(run())


def test_status_does_not_wait_for_model_lock_or_worker_pool():
    async def run():
        async with browser() as b:
            await pair(b)
            await refresh(b)
            conn = webapp.app.state.espn_sessions.get(b.cookies.get(api.COOKIE))
            conn.lock.acquire()
            webapp.app.state.espn_slots = asyncio.Semaphore(0)
            try:
                result = await asyncio.wait_for(b.get(P + "/status"), timeout=0.2)
                assert result.status_code == 200 and result.json()["connected"]
            finally:
                conn.lock.release()

    asyncio.run(run())


def test_bridge_session_cannot_outlive_pairing_lease(monkeypatch):
    async def run():
        async with browser() as b:
            await pair(b)
            pairing = webapp.app.state.espn_bridges.get(b.cookies.get(api.BRIDGE_COOKIE), "http://127.0.0.1")
            now = time.time()
            pairing.expires = now + 60
            assert (await refresh(b)).status_code == 200
            conn = webapp.app.state.espn_sessions.get(b.cookies.get(api.COOKIE))
            assert conn.expires == pairing.expires
            monkeypatch.setattr(api.time, "time", lambda: now + 61)
            assert (await b.get(P + "/status")).json() == {"connected": False}
            assert (await b.get(P + "/bridge/status")).json() == {"enabled": False}
            assert not conn.active and conn.client.swid is None

    asyncio.run(run())
