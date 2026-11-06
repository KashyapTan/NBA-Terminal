"""Owned 8218: actual HTTP routes/normalizer/adapter/optimizer, controlled transports.

ESPN observed public schedule reused from V7; rosters, rates and NBA transport synthetic.
Never accesses private ESPN or changes a fantasy roster. No fake plan route.
"""

import copy
import os

import uvicorn
import v7_e2e_server as transport
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn

app = transport.app
BASE_PAYLOAD = transport.payload
BASE_RATES = transport.rate_rows
STATE = {"players": 13, "out": False, "rate_change": False, "pickup_boost": False}


def payload():
    raw = BASE_PAYLOAD()
    league = raw["league"]
    league["settings"]["name"] = "V8 synthetic ten-slot league"
    league["settings"]["rosterSettings"]["lineupSlotCounts"] = {
        "0": 1,
        "1": 1,
        "2": 1,
        "3": 1,
        "4": 1,
        "5": 1,
        "6": 1,
        "11": 3,
        "12": 3,
        "13": 2,
    }
    for team in league["teams"]:
        seed = copy.deepcopy(team["roster"]["entries"][0])
        count = STATE["players"] if team["id"] == 1 else 12
        entries = []
        for i in range(count):
            entry = copy.deepcopy(seed)
            p = espn.player_body(entry)
            p.update(
                id=10000 * team["id"] + i,
                fullName=f"{'Owned' if team['id'] == 1 else 'Opponent'} Player {i + 1}",
                proTeamId=11,
                eligibleSlots=[0, 1, 5, 11, 12] if i < 7 else [2, 3, 6, 11, 12] if i < 10 else [4, 3, 6, 11, 12],
                injured=STATE["out"] and i == 0,
                injuryStatus="OUT" if STATE["out"] and i == 0 else "ACTIVE",
            )
            entry["lineupSlotId"] = 12
            entries.append(entry)
        team["roster"]["entries"] = entries
    # Actuals are deliberately different and nonzero for both sides.
    for match in league["schedule"]:
        if match["matchupPeriodId"] == 3:
            for side in (match.get("home", {}), match.get("away", {})):
                for key, stat in side.get("cumulativeScore", {}).get("scoreByStat", {}).items():
                    stat["score"] = {
                        "0": 100,
                        "1": 5,
                        "2": 4,
                        "3": 32,
                        "6": 25,
                        "11": 15,
                        "13": 20,
                        "14": 40,
                        "15": 10,
                        "16": 15,
                        "17": 12,
                        "40": 120,
                        "42": 4,
                    }.get(key, 0) * (1 if side["teamId"] == 1 else 2)
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for team in league["teams"] for e in team["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    return raw


def rate_rows():
    rows = BASE_RATES()
    for row in rows:
        if STATE["pickup_boost"] and row["PLAYER_ID"] in {300100, 300101}:
            row.update(PTS=60, REB=30, AST=25, STL=10, BLK=8, FG3M=8, TOV=0.1, FGM=20, FGA=25, FTM=10, FTA=11)
        if row["PLAYER_NAME"].startswith(("Owned", "Opponent")):
            i = int(row["PLAYER_NAME"].split()[-1]) - 1
            row.update(
                PTS=30 - i, REB=4, AST=2 + i, STL=1, BLK=1, FG3M=i / 2, TOV=0.2, FGM=4, FGA=8, FTM=2, FTA=3, MIN=30
            )
            if STATE["rate_change"] and i == 0:
                row.update(AST=0, PTS=0, STL=0, BLK=0, REB=0, TOV=20)
    return rows


transport.payload = payload
transport.rate_rows = rate_rows


@app.post("/__test__/v8-control")
async def configure(request: Request):
    data = await request.json()
    STATE.update({key: data[key] for key in STATE if key in data})
    transport.nba._CACHE.clear()
    return {"synthetic": True, **STATE}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("FANTASY_E2E_PORT", "8218")),
        access_log=False,
        log_level="warning",
    )
