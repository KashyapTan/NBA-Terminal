"""Owned8219: actual provider normalization/adapter/optimizer, controlled transports."""

import copy
from datetime import datetime

import requests
import uvicorn
import v7_e2e_server as transport
from fastapi import Request

from tests.fantasy_v10_fixture import provider_payload, provider_rates

app = transport.app
BASE = transport.payload
STATE = {"phase": "after-first", "day": "2026-11-06", "beneficial": False, "now": None}


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime.fromisoformat(STATE["now"] or STATE["day"] + "T17:00:00+00:00")
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def payload():
    raw = provider_payload(BASE(), STATE["phase"], STATE["day"])
    raw["schedule"] = copy.deepcopy(transport.OBSERVED)
    return raw


def rates():
    return provider_rates(payload(), STATE["beneficial"])


def unavailable_schedule(**kwargs):
    raise requests.Timeout("Controlled NBA schedule outage; exercise verified ESPN fallback")


transport.payload = payload
transport.rate_rows = rates
transport.espn.datetime = Clock
transport.nba.datetime = Clock
transport.lifecycle.fixture.adapter.datetime = Clock
transport.nba.scheduleleaguev2.ScheduleLeagueV2 = unavailable_schedule


@app.post("/__test__/v10-control")
async def configure(request: Request):
    data = await request.json()
    STATE.update({key: data[key] for key in STATE if key in data})
    transport.STATE.update(league=1001, changed=False, failed=False, seconds=0)
    transport.nba._CACHE.clear()
    return {"synthetic": True, **STATE}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8219, access_log=False, log_level="warning")
