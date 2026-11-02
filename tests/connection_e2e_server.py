"""Isolated lifecycle HTTP server: production routes with controlled provider I/O.

Synthetic only. Never reads a private account or imports in production.
"""
import asyncio
import threading
import time

import fantasy_e2e_server as fixture
import uvicorn
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn

app = fixture.webapp.app
lock = threading.Lock()
control = {"delay": 0.0, "failures": [], "calls": {}, "plan_delays": [], "snapshot_delays": []}
original = espn.EspnClient.league


def provider(self):
    with lock:
        delay = control["delay"]
        failure = control["failures"].pop(0) if control["failures"] else None
    if delay:
        time.sleep(delay)
    if failure:
        raise espn.EspnError("synthetic_provider_failure", "Synthetic provider failure.", failure)
    return original(self)


espn.EspnClient.league = provider


@app.middleware("http")
async def count(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/fantasy/espn"):
        with lock:
            control["calls"][path] = control["calls"].get(path, 0) + 1
    with lock:
        key = "plan_delays" if path.endswith("/plan") else "snapshot_delays"
        delays = control[key] if path.endswith(("/plan", "/snapshot")) else []
        delay = delays.pop(0) if delays else 0
    response = await call_next(request)
    if delay:
        await asyncio.sleep(delay)
    return response


@app.post("/__test__/connection-control")
async def configure(request: Request):
    data = await request.json()
    with lock:
        control["delay"] = float(data.get("delay", 0))
        control["failures"] = list(data.get("failures", []))
        control["plan_delays"] = list(data.get("plan_delays", []))
        control["snapshot_delays"] = list(data.get("snapshot_delays", []))
    return {"synthetic": True}


@app.get("/__test__/connection-control")
def counters():
    with lock:
        return {"synthetic": True, "calls": dict(control["calls"])}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8212, access_log=False, log_level="warning")
