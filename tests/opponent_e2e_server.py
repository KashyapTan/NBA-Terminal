"""Owned opponent HTTP regression: real routes, synthetic external transports only."""

import copy
import os

import uvicorn
import v8_e2e_server as base
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn

app = base.app
BASE_PAYLOAD = base.payload
BASE_RATES = base.rate_rows
STATE = {"bench": True, "count": 8, "rate_change": False}


def payload():
    raw = BASE_PAYLOAD()
    # Other synthetic teams share display names in V8; isolate this matchup so
    # the real name/team identity adapter can resolve our controlled rate rows.
    raw["league"]["teams"] = [t for t in raw["league"]["teams"] if t["id"] in (1, 2)]
    raw["league"]["settings"]["size"] = 2
    for team in raw["league"]["teams"]:
        if team["id"] != 2:
            continue
        team["roster"]["entries"] = team["roster"]["entries"][: STATE["count"]]
        for i, entry in enumerate(team["roster"]["entries"]):
            entry["lineupSlotId"] = 12 if STATE["bench"] else 11
            p = espn.player_body(entry)
            # Broad eligibility permits all eight; >10 still has actual position contention.
            if STATE["count"] <= 10:
                p["eligibleSlots"] = [0, 1, 2, 3, 4, 5, 6, 11, 12]
            p.update(injured=False, injuryStatus="ACTIVE")
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for team in raw["league"]["teams"] for e in team["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    return raw


def rate_rows():
    rows = BASE_RATES()
    for row in rows:
        if row["PLAYER_NAME"].startswith("Opponent"):
            row.update(TOV=8, FGM=2, FGA=12, FTM=1, FTA=5)
            if STATE["rate_change"]:
                row["PTS"] += 10
    return rows


base.transport.payload = payload
base.transport.rate_rows = rate_rows


@app.post("/__test__/opponent-control")
async def configure(request: Request):
    data = await request.json()
    STATE.update({k: data[k] for k in STATE if k in data})
    base.transport.nba._CACHE.clear()
    return {"synthetic": True, **STATE}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("FANTASY_E2E_PORT", "8219")),
        access_log=False,
        log_level="warning",
    )
