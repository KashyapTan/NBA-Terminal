"""Read-only loopback sessions: mocked ESPN, isolated cookies, no secret leakage."""

import asyncio
import json
import threading
import time
from pathlib import Path

import httpx2 as httpx
import pytest

from nba_terminal import espn_fantasy_api as api
from nba_terminal import webapp
from nba_terminal.services import espn_fantasy as espn

PREFIX = "/api/fantasy/espn"
HEADERS = {"X-Fantasy-Request": "1"}
S2 = "synthetic-cookie-never-return-this"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    raw = json.loads((Path(__file__).parent / "fixtures" / "espn_fantasy_synthetic.json").read_text())
    monkeypatch.setattr(webapp.app.state, "espn_sessions", api.SessionStore(), raising=False)
    monkeypatch.setattr(webapp.app.state, "espn_slots", asyncio.Semaphore(4))
    monkeypatch.setattr(espn.EspnClient, "league", lambda self: raw["league"])
    monkeypatch.setattr(
        espn.EspnClient,
        "snapshot",
        lambda self, league, selected: espn.normalize(
            league, raw["schedule"], raw["pool"], raw["cards"], raw["transactions"], selected, swid=self.swid
        ),
    )
    return raw


def client(**kwargs):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=webapp.app), base_url="http://127.0.0.1", **kwargs)


def connect_body(**kwargs):
    return {"league_id": 123, "season_id": 2027, "team_id": 1} | kwargs


def test_public_connect_cache_compare_refresh_select_and_disconnect(monkeypatch):
    calls = []
    original = espn.EspnClient.league

    def league(self):
        calls.append(self.league_id)
        return original(self)

    monkeypatch.setattr(espn.EspnClient, "league", league)

    async def scenario():
        async with client() as browser:
            assert (await browser.get(PREFIX + "/status")).json() == {"connected": False}
            connected = await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert connected.status_code == 200
            assert connected.json()["auth_mode"] == "public"
            assert not connected.json()["ownership_verified"]
            cookie = connected.headers["set-cookie"]
            assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Max-Age=28800" in cookie
            assert "Path=/api/fantasy/espn" in cookie
            assert connected.headers["cache-control"] == "no-store"
            one = await browser.get(PREFIX + "/snapshot")
            two = await browser.get(PREFIX + "/snapshot", params={"compare_team_id": 14})
            assert one.json()["fetched_at"] == two.json()["fetched_at"]
            assert two.json()["comparison"]["team_id"] == 14
            assert len(calls) == 2  # connect and one snapshot; comparison is pure.
            assert (await browser.get(PREFIX + "/snapshot?compare_team_id=999")).status_code == 400
            assert (await browser.get(PREFIX + "/snapshot?refresh=true")).status_code == 200
            assert len(calls) == 3
            selected = await browser.put(PREFIX + "/team", headers=HEADERS, json={"team_id": 2})
            assert selected.json()["team_id"] == 2
            assert (await browser.get(PREFIX + "/snapshot")).json()["selected_team_id"] == 2
            token = browser.cookies.get(api.COOKIE)
            conn = webapp.app.state.espn_sessions.get(token)
            assert conn is not None
            disconnected = await browser.delete(PREFIX + "/connection", headers=HEADERS)
            assert disconnected.json() == {"connected": False}
            assert conn.cached is None and conn.raw == {} and not conn.active
            assert (await browser.get(PREFIX + "/snapshot")).status_code == 401

    asyncio.run(scenario())


def test_private_isolation_ownership_and_secret_erase():
    async def scenario():
        async with client() as owner, client() as other:
            private = connect_body(swid="fixture-owner-0001", espn_s2=S2)
            response = await owner.post(PREFIX + "/connect", headers=HEADERS, json=private)
            assert response.status_code == 200
            assert response.json()["ownership_verified"]
            assert S2 not in response.text and "fixture-owner" not in response.text
            assert (await other.get(PREFIX + "/status")).json() == {"connected": False}
            assert (await other.get(PREFIX + "/snapshot")).status_code == 401
            wrong = await owner.put(PREFIX + "/team", headers=HEADERS, json={"team_id": 2})
            assert wrong.status_code == 403
            data = await owner.get(PREFIX + "/snapshot")
            assert S2 not in data.text and "fixture-owner" not in data.text
            token = owner.cookies.get(api.COOKIE)
            conn = webapp.app.state.espn_sessions.get(token)
            await owner.delete(PREFIX + "/connection", headers=HEADERS)
            assert conn.client.swid is None and conn.client.espn_s2 is None
            assert webapp.app.state.espn_sessions.get(token) is None

    asyncio.run(scenario())


def test_connect_without_team_then_select_and_reconnect_revokes_old_session():
    async def scenario():
        async with client() as browser:
            response = await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body(team_id=None))
            assert len(response.json()["teams"]) == 14
            assert (await browser.get(PREFIX + "/snapshot")).status_code == 409
            assert (await browser.put(PREFIX + "/team", headers=HEADERS, json={"team_id": 14})).status_code == 200
            old = browser.cookies.get(api.COOKIE)
            conn = webapp.app.state.espn_sessions.get(old)
            await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert webapp.app.state.espn_sessions.get(old) is None
            assert not conn.active and conn.raw == {}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"password": S2},
        connect_body(league_id=True),
        connect_body(season_id=2018),
        connect_body(team_id="1"),
        connect_body(swid=S2),
        connect_body(swid=123, espn_s2=S2),
        connect_body(swid="fixture-owner-0001", espn_s2="bad\ncookie"),
        connect_body(swid="fixture-owner-0001", espn_s2=S2 + ";"),
    ],
)
def test_invalid_body_never_echoes_secrets(payload):
    async def scenario():
        async with client() as browser:
            response = await browser.post(PREFIX + "/connect", headers=HEADERS, json=payload)
            assert response.status_code == 400
            assert S2 not in response.text

    asyncio.run(scenario())


def test_local_only_same_origin_json_and_csrf_header():
    async def scenario():
        async with client() as browser:
            wrong_host = await browser.get(PREFIX + "/status", headers={"Host": "evil.example"})
            assert wrong_host.status_code == 403
            assert wrong_host.headers["cache-control"] == "no-store"
            assert (await browser.get(PREFIX + "/status", headers={"Origin": "http://evil.example"})).status_code == 403
            assert (await browser.get(PREFIX + "/status", headers={"Sec-Fetch-Site": "cross-site"})).status_code == 403
            assert (await browser.post(PREFIX + "/connect", json=connect_body())).status_code == 403
            assert (await browser.post(PREFIX + "/connect", headers=HEADERS, content="bad")).status_code == 415
            assert (
                await browser.post(
                    PREFIX + "/connect", headers=HEADERS | {"Content-Type": "application/json"}, content="bad"
                )
            ).status_code == 400
            assert (
                await browser.post(
                    PREFIX + "/connect",
                    headers=HEADERS | {"Content-Type": "application/json"},
                    content='{"padding":"' + "a" * 17000 + '"}',
                )
            ).status_code == 413
        transport = httpx.ASGITransport(app=webapp.app, client=("192.0.2.1", 4444))
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as remote:
            assert (await remote.get(PREFIX + "/status")).status_code == 403

    asyncio.run(scenario())


def test_expired_session_is_erased():
    async def scenario():
        async with client() as browser:
            await browser.post(
                PREFIX + "/connect", headers=HEADERS, json=connect_body(swid="fixture-owner-0001", espn_s2=S2)
            )
            conn = webapp.app.state.espn_sessions.get(browser.cookies.get(api.COOKIE))
            conn.expires = time.time() - 1
            assert (await browser.get(PREFIX + "/status")).json() == {"connected": False}
            assert conn.client.espn_s2 is None and conn.raw == {}

    asyncio.run(scenario())


def test_refresh_failure_does_not_return_stale_success_and_errors_redacted(monkeypatch, caplog):
    async def scenario():
        async with client() as browser:
            await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert (await browser.get(PREFIX + "/snapshot")).status_code == 200

            def broken(self):
                raise RuntimeError(S2)

            monkeypatch.setattr(espn.EspnClient, "league", broken)
            response = await browser.get(PREFIX + "/snapshot?refresh=true")
            assert response.status_code == 502 and S2 not in response.text
            assert response.json()["detail"]["code"] == "schema_changed"

    asyncio.run(scenario())
    assert S2 not in caplog.text


def test_capacity_busy_and_exception_mapping(monkeypatch):
    async def scenario():
        async with client() as browser:
            monkeypatch.setattr(api, "MAX_SESSIONS", 0)
            assert (await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())).status_code == 503
            monkeypatch.setattr(api, "MAX_SESSIONS", 64)

            def denied(self):
                raise espn.EspnError("access_denied", "Safe denial", 401)

            monkeypatch.setattr(espn.EspnClient, "league", denied)
            denied_response = await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert denied_response.status_code == 401
            monkeypatch.setattr(webapp.app.state, "espn_slots", asyncio.Semaphore(0))
            response = await browser.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert response.status_code == 503 and response.json()["detail"]["code"] == "busy"

    asyncio.run(scenario())


def test_cancelled_worker_keeps_slot_until_actual_completion():
    started, release = threading.Event(), threading.Event()

    def blocking():
        started.set()
        assert release.wait(timeout=3)
        return 1

    async def scenario():
        slots = asyncio.Semaphore(1)
        webapp.app.state.espn_slots = slots
        request = type("Request", (), {"app": webapp.app})()
        task = asyncio.create_task(api.worker(request, blocking))
        while not started.is_set():
            await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert slots.locked()
        release.set()
        for _ in range(100):
            if not slots.locked():
                break
            await asyncio.sleep(0.005)
        assert not slots.locked()

    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_disconnect_during_failed_fetch_erases_secrets(monkeypatch):
    conn = api.connect_sync(connect_body(swid="fixture-owner-0001", espn_s2=S2))

    def fail_fetch(*args):
        conn.active = False  # Models disconnect while worker holds lock.
        raise espn.EspnError("timeout", "Safe timeout", 504)

    monkeypatch.setattr(conn.client, "snapshot", fail_fetch)
    with pytest.raises(espn.EspnError):
        api.snapshot_sync(conn, True, None)
    assert conn.client.espn_s2 is None and conn.raw == {}


@pytest.mark.parametrize(
    "query", ["refresh=yes", "compare_team_id=oops", "compare_team_id=0", "compare_team_id=99999999"]
)
def test_query_errors_are_static_and_uncached(query):
    async def scenario():
        async with client() as browser:
            response = await browser.get(PREFIX + "/snapshot?" + query)
            assert response.status_code == 400
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["detail"]["code"] == "invalid_query"

    asyncio.run(scenario())
