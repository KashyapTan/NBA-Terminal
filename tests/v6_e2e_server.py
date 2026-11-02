"""V6 integrated test-only HTTP server. Controlled provider transports, real app/model.

No private account/network access. Ports 8214/4214 are reserved to this suite.
"""

import copy
import json
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import connection_e2e_server as lifecycle
import requests
import uvicorn
from fastapi import Request

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba

OBSERVED_START = time.monotonic()


class ObservationClock(lifecycle.fixture.Clock):
    @classmethod
    def now(cls, tz=None):
        # Real elapsed observations, fixed synthetic basketball date. Samples
        # genuinely change timestamps at every refresh while facts remain equal.
        return lifecycle.fixture.NOW + timedelta(seconds=time.monotonic() - OBSERVED_START)


app = lifecycle.app
MODE = 601
RAW = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())


def payload(league_id):
    raw = copy.deepcopy(RAW)
    raw["league"]["id"] = league_id
    raw["league"]["settings"]["name"] = "V6 controlled provider league"
    raw["league"]["settings"]["rosterSettings"]["lineupSlotCounts"] = {"11": 2, "13": 2}
    for entry in raw["cards"]["players"] + raw["pool"]["players"]:
        body = espn.player_body(entry)
        for split in body.get("stats", []):
            if split["seasonId"] == 2027:
                split["stats"].update({"42": 2, "40": 30, "0": 16, "3": 12, "6": 10, "1": 2, "2": 2})
    own = raw["league"]["teams"][0]
    extra = copy.deepcopy(own["roster"]["entries"][0])
    extra["playerPoolEntry"]["player"]["id"] = 9001
    extra["playerPoolEntry"]["player"]["fullName"] = "Second roster drop"
    own["roster"]["entries"].append(extra)
    for entry in own["roster"]["entries"]:
        for split in entry["playerPoolEntry"]["player"]["stats"]:
            if split["seasonId"] == 2027:
                split["stats"].update({"42": 2, "40": 30, "0": 16, "3": 12, "6": 10, "1": 2, "2": 2})
        entry["lineupSlotId"] = 13  # actual IR slot; activation is not modeled
    own["transactionCounter"]["matchupAcquisitionTotals"] = {"2": 5 if league_id != 603 else 7}
    for entry in raw["pool"]["players"]:
        entry.update(status="FREEAGENT", onTeamId=0)
    low = copy.deepcopy(raw["pool"]["players"][0])
    low["player"]["id"] = 199
    low["player"]["fullName"] = "Low sample 11 minutes"
    for split in low["player"]["stats"]:
        if split["seasonId"] == 2027:
            split["stats"].update({"42": 1, "40": 11})
    raw["pool"]["players"].append(low)
    # Ensure card enrichment uses the same observations and ownership.
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for t in raw["league"]["teams"] for e in t["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    if league_id == 614:
        own["transactionCounter"]["matchupAcquisitionTotals"] = {"2": 0}
        base = raw["pool"]["players"][0]
        raw["pool"]["players"] = []
        for i in range(30):
            entry = copy.deepcopy(base)
            entry["player"]["id"] = 200 + i
            entry["player"]["fullName"] = f"Qualified bounded candidate {i + 1}"
            raw["pool"]["players"].append(entry)
        raw["pool"]["players"].append(low)
        raw["cards"]["players"] += copy.deepcopy(raw["pool"]["players"])
    if league_id == 602:
        raw["pool"]["players"] = raw["pool"]["players"][:1] + [low]
    if league_id == 604:
        raw["pool"]["players"] = [low]
    if league_id == 606:
        raw["schedule"] = {}
    if league_id == 615:
        for entry in own["roster"]["entries"]:
            entry["lineupSlotId"] = 11
        for entry in raw["pool"]["players"] + raw["cards"]["players"]:
            body = espn.player_body(entry)
            if body["id"] in {100, 101}:
                for split in body["stats"]:
                    if split["seasonId"] == 2027:
                        split["stats"].update({"0": 24, "6": 6, "3": 20, "1": 4, "2": 4, "17": 8})
    if league_id in {616, 617}:
        raw["league"]["settings"]["acquisitionSettings"].pop("matchupAcquisitionLimit", None)
    if league_id == 613:
        own["transactionCounter"].pop("matchupAcquisitionTotals", None)
    if league_id in {609, 610, 611, 612}:
        for entry in raw["pool"]["players"] + raw["cards"]["players"]:
            body = espn.player_body(entry)
            if body["id"] not in {100, 101}:
                continue
            if league_id == 612:
                body["stats"] = [row for row in body["stats"] if row["seasonId"] != 2027]
            for split in body["stats"]:
                if split["seasonId"] == 2027:
                    split["stats"].update({"42": 1 if league_id == 610 else 2, "40": 29.98 if league_id == 609 else 30})
    if league_id == 608:
        # All current sample players remain qualified; no future add can improve.
        for entry in own["roster"]["entries"]:
            entry["lineupSlotId"] = 11
    return raw


def synthetic_get(self, views, *args, **kwargs):
    global MODE
    MODE = self.league_id
    raw = payload(self.league_id)
    return raw[
        {
            "mSettings": "league",
            "mTeam": "league",
            "mMatchupScore": "league",
            "proTeamSchedules_wl": "schedule",
            "kona_player_info": "pool",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
        }[views[0]]
    ]


def team_table():
    rows = [] if MODE == 605 else [[tid, 5 if MODE == 611 else 4] for tid in nba.NBA_TO_ESPN]
    return {"resultSets": [{"name": "LeagueDashTeamStats", "headers": ["TEAM_ID", "GP"], "rowSet": rows}]}


espn.EspnClient.get = synthetic_get
nba.datetime = ObservationClock
espn.datetime = ObservationClock
lifecycle.fixture.adapter.datetime = ObservationClock
nba.leaguedashteamstats.LeagueDashTeamStats = lambda **kwargs: SimpleNamespace(get_dict=team_table)
nba.leaguedashplayerstats.LeagueDashPlayerStats = lambda **kwargs: SimpleNamespace(
    get_dict=lambda: {"resultSets": [{"name": "LeagueDashPlayerStats", "headers": ["PLAYER_ID"], "rowSet": []}]}
)


# Optional NBA unavailable; complete official ESPN actuals remain authoritative.
def optional_outage(*args, **kwargs):
    raise requests.Timeout("Synthetic optional NBA outage")


nba.scheduleleaguev2.ScheduleLeagueV2 = optional_outage


@app.post("/__test__/v6-reset")
async def reset(request: Request):
    global MODE
    MODE = int((await request.json()).get("league_id", 601))
    nba._CACHE.clear()
    return {"synthetic": True, "league_id": MODE}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8214, access_log=False, log_level="warning")
