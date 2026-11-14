"""Real ASGI HTTP routes, normalizer and local search; synthetic provider transport."""

import asyncio

from nba_terminal.services import espn_fantasy as espn
from tests.test_espn_fantasy_api import HEADERS, PREFIX, client, connect_body
from tests.test_espn_fantasy_api import isolated as isolated


def test_http_progress_is_local_session_scoped_cancellable_and_invalidated(monkeypatch):
    calls = []
    league = espn.EspnClient.league

    def counted(self):
        calls.append("league")
        return league(self)

    monkeypatch.setattr(espn.EspnClient, "league", counted)

    async def scenario():
        async with client() as owner, client() as other:
            assert (await owner.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())).status_code == 200
            snapshot = (await owner.get(PREFIX + "/snapshot")).json()
            preferences = {
                "context": {
                    "league_id": 123,
                    "season_id": 2027,
                    "team_id": 1,
                    "matchup_period_id": snapshot["period"]["matchup_period_id"],
                }
            }
            initial_calls = list(calls)
            result = await owner.post(
                PREFIX + "/plan", headers=HEADERS | {"X-Fantasy-Search": "progressive"}, json=preferences
            )
            assert result.status_code == 200
            job = result.json()["search"]["job_id"]
            assert result.json()["search"]["publication"] == 1
            for _ in range(3):
                progress = await owner.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})
                assert progress.status_code == 200
            assert calls == initial_calls
            assert (await other.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})).status_code == 401
            await other.post(PREFIX + "/connect", headers=HEADERS, json=connect_body())
            assert (await other.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})).status_code == 404
            assert (await owner.post(PREFIX + "/plan/" + job, json={})).status_code == 403
            assert (await owner.delete(PREFIX + "/plan/" + job, headers=HEADERS)).json()["phase"] == "cancelled"
            assert (await owner.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})).json()["search"][
                "phase"
            ] == "cancelled"

            def unavailable(self):
                raise espn.EspnError("timeout", "Synthetic transient refresh failure", 504)

            monkeypatch.setattr(espn.EspnClient, "league", unavailable)
            assert (await owner.get(PREFIX + "/snapshot?refresh=true")).status_code == 504
            saved = (await owner.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})).json()
            assert saved["search"]["publication"] == progress.json()["search"]["publication"]
            assert saved["read_only"] is True
            assert saved["freshness"] == "saved_after_refresh_failure"
            assert saved["actions"] == progress.json()["actions"]
            monkeypatch.setattr(espn.EspnClient, "league", counted)
            await owner.get(PREFIX + "/snapshot?refresh=true")
            assert (await owner.post(PREFIX + "/plan/" + job, headers=HEADERS, json={})).status_code == 409

    asyncio.run(scenario())


def test_obsolete_running_generation_cannot_publish_and_cancel_is_nonblocking(monkeypatch):
    import threading
    import time
    from types import SimpleNamespace

    from nba_terminal.services import waiver_search as search

    entered, release = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        yield {"status": "ready", "actions": [], "search": {"phase": "searching"}}

    monkeypatch.setattr(search.adapter, "iter_snapshot_waivers", slow)
    snapshot = {"teams": [], "free_agents": []}
    conn = SimpleNamespace(
        cached=snapshot, active=True, team_id=1, expires=time.time() + 60, search=None, refresh_failed=False
    )
    job = search.start_search(conn, snapshot, {})
    errors = []

    def advance():
        try:
            job.advance(conn)
        except espn.EspnError as exc:
            errors.append(exc.code)

    thread = threading.Thread(target=advance)
    thread.start()
    assert entered.wait(3)
    begin = time.monotonic()
    replacement = search.start_search(conn, snapshot, {})
    assert time.monotonic() - begin < 0.1
    release.set()
    thread.join(3)
    assert not thread.is_alive()
    assert errors == ["snapshot_changed"]
    assert conn.search is replacement
    assert job.cancelled.is_set()
    replacement.cancel()


def test_job_capacity_idle_expiry_and_tipoff_invalidation(monkeypatch):
    import time
    from datetime import timedelta, timezone
    from types import SimpleNamespace

    import pytest

    from nba_terminal.services import waiver_search as search

    monkeypatch.setattr(search, "MAX_SEARCHES", 1)
    for job in list(search._registry):
        job.cancel()
    snapshot = {"teams": [], "free_agents": []}

    def make():
        return SimpleNamespace(
            cached=snapshot, active=True, team_id=1, expires=time.time() + 60, search=None, refresh_failed=False
        )

    conn = make()
    first = search.start_search(conn, snapshot, {})
    with pytest.raises(espn.EspnError, match="full"):
        search.start_search(make(), snapshot, {})
    first.touched -= search.IDLE_TTL + 1
    with pytest.raises(espn.EspnError, match="expired"):
        first.advance(conn)
    second = search.start_search(conn, snapshot, {})
    second.valid_until = search.adapter.datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(espn.EspnError, match="locks"):
        second.advance(conn)
    second.cancel()
