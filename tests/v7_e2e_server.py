"""V7 real HTTP app with controlled provider transports; no private/live-account proof.

Observed public ESPN schedule dates; NBA shape/IDs and league/rates are synthetic.
Only this owned server8217 is started. No route or optimizer result is replaced.
"""

import copy
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import connection_e2e_server as lifecycle
import requests
import uvicorn
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba
from tests.test_fantasy_v7_schedule import synthetic_nba_transport

app = lifecycle.app
START = time.monotonic()
STATE = {"league": 701, "seconds": 0, "changed": False, "failed": False}
OBSERVED = json.loads((Path(__file__).parents[1] / "docs/evidence/v7-schedule/espn-season.response").read_text())
RAW = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        base = datetime(2026, 11, 5 if STATE["league"] in {703, 710} else 2, 17, tzinfo=timezone.utc)
        result = base + timedelta(seconds=STATE["seconds"] + time.monotonic() - START)
        return result.astimezone(tz) if tz else result.replace(tzinfo=None)


def payload():
    raw = copy.deepcopy(RAW)
    league = raw["league"]
    league.update(id=STATE["league"], scoringPeriodId=17 if STATE["league"] in {703, 710} else 14)
    league["settings"]["name"] = "V7 controlled provider league"
    league["status"]["currentMatchupPeriod"] = 3
    league["settings"]["scheduleSettings"].update(periodTypeId=2, matchupPeriods={"3": [3]})
    league["settings"]["acquisitionSettings"].update(matchupAcquisitionLimit=2, matchupLimitPerScoringPeriod=False)
    league["settings"]["rosterSettings"]["lineupSlotCounts"] = {
        "11": 2 if STATE["league"] == 702 else 1,
        "12": 12,
        "13": 2,
    }
    for team in league["teams"]:
        team["transactionCounter"]["matchupAcquisitionTotals"] = {"3": 2 if STATE["league"] in {704, 705} else 0}
        for entry in team["roster"]["entries"]:
            entry["lineupSlotId"] = 13 if STATE["league"] == 704 and team["id"] == 1 else 11
            p = espn.player_body(entry)
            p.update(
                id=team["id"],
                proTeamId=11 if team["id"] == 1 and STATE["league"] != 710 else 2,
                injured=False,
                injuryStatus="ACTIVE",
                droppable=True,
            )
    if STATE["league"] in {702, 709, 710}:
        extra = copy.deepcopy(league["teams"][0]["roster"]["entries"][0])
        p = espn.player_body(extra)
        p.update(id=9001, fullName="Second roster guard")
        league["teams"][0]["roster"]["entries"].append(extra)
    if STATE["league"] == 708:
        league["teams"][0]["transactionCounter"].pop("matchupAcquisitionTotals", None)
    banked = {
        "0": 47,
        "1": 2,
        "2": 3,
        "3": 12,
        "6": 15,
        "11": 5,
        "13": 7,
        "14": 19,
        "15": 9,
        "16": 12,
        "17": 6,
        "40": 90,
        "42": 3,
    }
    for match in league["schedule"]:
        match["matchupPeriodId"] = 3
        for side in (match.get("home", {}), match.get("away", {})):
            side["pointsByScoringPeriod"] = {}
            for key, value in side.get("cumulativeScore", {}).get("scoreByStat", {}).items():
                value["score"] = banked.get(key, 0) if STATE["league"] in {703, 710} else 0
    raw["pool"]["players"] = [e for e in raw["pool"]["players"] if espn.player_body(e)["id"] in {100, 101}]
    for index, entry in enumerate(raw["pool"]["players"]):
        p = espn.player_body(entry)
        p.update(proTeamId=1 if index == 0 else 2, injured=False, injuryStatus="ACTIVE", droppable=True)
        entry.update(status="FREEAGENT", onTeamId=0)
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for team in league["teams"] for e in team["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    raw["schedule"] = copy.deepcopy(OBSERVED)
    # Crop ESPN ATL map: fresh complete NBA must replace its two observed games.
    if STATE["league"] != 707:
        for team in raw["schedule"]["settings"]["proTeams"]:
            if team["id"] == 1:
                team["proGamesByScoringPeriod"] = {
                    k: v for k, v in team["proGamesByScoringPeriod"].items() if int(k) <= 16
                }
    if STATE["league"] == 707 and STATE["changed"]:
        # A valid reschedule changes both reciprocal records and scoring-date anchors.
        for team in raw["schedule"]["settings"]["proTeams"]:
            moved = {}
            for period, entries in team["proGamesByScoringPeriod"].items():
                for game in entries:
                    day = (
                        datetime.fromtimestamp(game["date"] / 1000, timezone.utc)
                        .astimezone(ZoneInfo("America/New_York"))
                        .date()
                        .isoformat()
                    )
                    new_period = period
                    if day == "2026-11-07" and 1 in {game["homeProTeamId"], game["awayProTeamId"]}:
                        game["date"] = datetime(2026, 11, 10, 23, tzinfo=timezone.utc).timestamp() * 1000
                        game["scoringPeriodId"] = 22
                        new_period = "22"
                    moved.setdefault(new_period, []).append(game)
            team["proGamesByScoringPeriod"] = moved
    if STATE["league"] == 706:
        raw["schedule"] = {}
    return raw


def get(self, views, *args, **kwargs):
    return payload()[
        {
            "proTeamSchedules_wl": "schedule",
            "kona_player_info": "pool",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
        }.get(views[0], "league")
    ]


def rate_rows():
    raw = payload()
    rows = []
    for entry in raw["cards"]["players"]:
        p = espn.player_body(entry)
        pickup = p["id"] in {100, 101}
        rows.append(
            dict(
                PLAYER_ID=300000 + p["id"],
                PLAYER_NAME=p["fullName"],
                TEAM_ABBREVIATION=nba.ESPN_TEAMS[p["proTeamId"]],
                TEAM_ID=next(k for k, v in nba.NBA_TO_ESPN.items() if v == p["proTeamId"]),
                GP=8,
                MIN=28 if pickup else 24,
                PTS=20 if pickup else 8,
                REB=6 if pickup else 4,
                AST=7 if pickup else 2,
                STL=1.5 if pickup else 0.7,
                BLK=0.8 if pickup else 0.4,
                FG3M=2.5 if pickup else 1,
                TOV=2 if pickup else 1,
                FGM=7 if pickup else 3,
                FGA=14 if pickup else 8,
                FTM=3 if pickup else 1,
                FTA=4 if pickup else 2,
            )
        )
        if p["id"] == 2:
            rows[-1].update(PTS=25, REB=10, AST=8, STL=2, BLK=2, FG3M=3, TOV=3, FGM=9, FGA=20, FTM=4, FTA=5)

    return rows


def table(rows, name):
    headers = list(rows[0]) if rows else ["PLAYER_ID"]
    return {"resultSets": [{"name": name, "headers": headers, "rowSet": [[r[k] for k in headers] for r in rows]}]}


def schedule(**kwargs):
    if STATE["league"] in {706, 707} or STATE["failed"]:
        raise requests.Timeout("Controlled NBA schedule outage")
    data = synthetic_nba_transport()
    if STATE["changed"]:
        for date in data["leagueSchedule"]["gameDates"]:
            for game in date["games"]:
                day = (
                    datetime.fromisoformat(game["gameDateTimeUTC"])
                    .astimezone(ZoneInfo("America/New_York"))
                    .date()
                    .isoformat()
                )
                teams = {str(game["homeTeam"]["teamId"]), str(game["awayTeam"]["teamId"])}
                if day == "2026-11-07" and "1610612737" in teams:
                    game["gameDateTimeUTC"] = "2026-11-09T23:00:00+00:00"
    return SimpleNamespace(get_dict=lambda: data)


espn.EspnClient.get = get
espn.datetime = Clock
nba.datetime = Clock
nba.time = SimpleNamespace(monotonic=lambda: time.monotonic() + STATE["seconds"])
lifecycle.fixture.adapter.datetime = Clock
nba.leaguedashplayerstats.LeagueDashPlayerStats = lambda **kwargs: SimpleNamespace(
    get_dict=lambda: table(rate_rows(), "LeagueDashPlayerStats")
)
nba.leaguedashteamstats.LeagueDashTeamStats = lambda **kwargs: SimpleNamespace(
    get_dict=lambda: table([{"TEAM_ID": tid, "GP": 8} for tid in nba.NBA_TO_ESPN], "LeagueDashTeamStats")
)
nba.scheduleleaguev2.ScheduleLeagueV2 = schedule
# CDN transport is a controlled403 from the shared fixture. Real load/cache/fetch validation remains active.


@app.post("/__test__/v7-control")
async def configure(request: Request):
    data = await request.json()
    if "league" in data:
        STATE.update(league=int(data["league"]), seconds=0, changed=False, failed=False)
        nba._CACHE.clear()
    for key in ("seconds", "changed", "failed"):
        if key in data:
            STATE[key] = data[key]
    return {"controlled": True, **STATE, "now": Clock.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("FANTASY_E2E_PORT", "8217")),
        access_log=False,
        log_level="warning",
    )
