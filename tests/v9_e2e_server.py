"""Owned 8219 only: real HTTP/provider normalizer/adapter/optimizer, synthetic rates.

Original screenshot names/dates are illustrative fixtures, not private-account facts.
"""

import copy
from datetime import datetime, timezone

import uvicorn
import v7_e2e_server as transport
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba

app = transport.app
BASE = transport.payload
STATE = {"interim": 0.0, "mode": ""}


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 11, 6, 17, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def payload():
    raw = BASE()
    league = raw["league"]
    league.update(scoringPeriodId=18)
    league["settings"]["name"] = "V9 controlled chain fixture"
    for team in league["teams"]:
        for entry in team["roster"]["entries"]:
            p = espn.player_body(entry)
            p.update(fullName="Jalen Green" if team["id"] == 1 else "Fixture opponent", proTeamId=11)
    for entry in raw["pool"]["players"]:
        p = espn.player_body(entry)
        p.update(
            fullName="Sam Merrill" if p["id"] == 100 else "Derrick Jones Jr.", proTeamId=1 if p["id"] == 100 else 12
        )
    if STATE["mode"] == "quota":
        league["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {"3": 1}
    if STATE["mode"] == "locked":
        league["teams"][0]["isTransactionLocked"] = True
    for entry in raw["pool"]["players"]:
        if STATE["mode"] == "harmful":
            if espn.player_body(entry)["id"] == 100:
                entry["status"] = "WAIVERS"
            else:
                espn.player_body(entry)["proTeamId"] = 13
        if espn.player_body(entry)["id"] == 101:
            if STATE["mode"] == "waiver":
                entry["status"] = "WAIVERS"
            if STATE["mode"] == "other":
                entry.update(status="ONTEAM", onTeamId=3)
    if STATE["mode"] == "crowded":
        league["settings"]["rosterSettings"]["lineupSlotCounts"] = {"11": 10, "12": 3}
        own = league["teams"][0]
        for index in range(10):
            extra = copy.deepcopy(own["roster"]["entries"][0])
            espn.player_body(extra).update(
                id=500 + index, fullName=f"Fixture occupied {index}", proTeamId=1, droppable=False
            )
            own["roster"]["entries"].append(extra)
    for match in league["schedule"]:
        for side in (match.get("home", {}), match.get("away", {})):
            for key, value in side.get("cumulativeScore", {}).get("scoreByStat", {}).items():
                value["score"] = {
                    "0": 100,
                    "1": 8,
                    "2": 8,
                    "3": 20,
                    "6": 20,
                    "11": 10,
                    "13": 40,
                    "14": 80,
                    "15": 20,
                    "16": 25,
                    "17": 10,
                    "40": 300,
                    "42": 10,
                }.get(key, 0)
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for team in league["teams"] for e in team["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    raw["schedule"] = copy.deepcopy(transport.OBSERVED)
    return raw


def rate_rows():
    rows = []
    for entry in payload()["cards"]["players"]:
        p = espn.player_body(entry)
        value = STATE["interim"] if p["id"] == 100 else 3 if p["id"] == 101 else 0.1
        if p["id"] >= 500:
            value = 5
        rows.append(
            dict(
                PLAYER_ID=300000 + p["id"],
                PLAYER_NAME=p["fullName"],
                TEAM_ABBREVIATION=nba.ESPN_TEAMS[p["proTeamId"]],
                TEAM_ID=next(k for k, v in nba.NBA_TO_ESPN.items() if v == p["proTeamId"]),
                GP=8,
                MIN=28,
                PTS=value,
                REB=value,
                AST=value,
                STL=value / 2,
                BLK=value / 2,
                FG3M=value,
                TOV=0.01,
                FGM=1,
                FGA=2,
                FTM=1,
                FTA=2,
            )
        )
        if STATE["mode"] == "harmful" and p["id"] == 100:
            rows[-1].update(PTS=0, TOV=50, FGM=0, FGA=30, FTM=0, FTA=30)
        if STATE["mode"] == "harmful" and p["id"] == 1:
            rows[-1].update(PTS=12)
        if STATE["mode"] == "harmful" and p["id"] == 101:
            rows[-1].update(PTS=0, REB=10, AST=10, STL=5, BLK=5, TOV=5, FGM=0, FGA=10, FTM=0, FTA=10)
    return rows


transport.payload = payload
transport.rate_rows = rate_rows
transport.espn.datetime = Clock
transport.nba.datetime = Clock
transport.lifecycle.fixture.adapter.datetime = Clock


@app.post("/__test__/v9-control")
async def configure(request: Request):
    data = await request.json()
    STATE["interim"] = float(data.get("interim", 0))
    STATE["mode"] = data.get("mode", "")
    transport.STATE.update(league=901, changed=False, failed=False, seconds=0)
    transport.nba._CACHE.clear()
    return {"synthetic": True, **STATE}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8219, access_log=False, log_level="warning")
