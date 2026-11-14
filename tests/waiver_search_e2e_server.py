"""Real HTTP/provider pipeline with a large synthetic market; no planner stubs."""

import copy

import uvicorn
import v9_e2e_server as base
from fastapi import Request

app = base.app
COUNTS = {}
STATE = {"adds": 4}
BASE_PAYLOAD = base.payload


def payload():
    raw = BASE_PAYLOAD()
    raw["league"]["settings"]["acquisitionSettings"]["matchupAcquisitionLimit"] = 7
    own = raw["league"]["teams"][0]
    own["transactionCounter"]["matchupAcquisitionTotals"] = {"3": 7 - STATE["adds"]}
    template = raw["pool"]["players"][0]
    for i in range(900):
        entry = copy.deepcopy(template)
        base.espn.player_body(entry).update(id=1000 + i, fullName=f"Synthetic pickup {i}")
        raw["pool"]["players"].append(entry)
    raw["cards"]["players"] = [
        copy.deepcopy(e["playerPoolEntry"]) for team in raw["league"]["teams"] for e in team["roster"]["entries"]
    ] + copy.deepcopy(raw["pool"]["players"])
    return raw


base.payload = payload
base.transport.payload = payload


def get(self, views, filters=None, *args, **kwargs):
    COUNTS[views[0]] = COUNTS.get(views[0], 0) + 1
    raw = payload()
    if views[0] == "kona_player_info":
        spec = (filters or {}).get("players", {})
        offset, limit = spec.get("offset", 0), spec.get("limit", 500)
        rows = raw["pool"]["players"]
        return {"players": rows[offset : offset + limit], "totalPlayers": len(rows)}
    return raw[
        {
            "proTeamSchedules_wl": "schedule",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
        }.get(views[0], "league")
    ]


BASE_RATES = base.rate_rows


def rate_rows():
    rows = BASE_RATES()
    for row in rows:
        if row["PLAYER_NAME"].startswith("Synthetic pickup"):
            row.update(PTS=1, REB=1, AST=1, STL=0.1, BLK=0.1, FG3M=0.1, TOV=0.01, FGM=0.1, FGA=0.2, FTM=0.05, FTA=0.1)
    return rows


base.transport.rate_rows = rate_rows
base.espn.EspnClient.get = get
CDN_GET = base.nba.requests.get


def cdn_get(*args, **kwargs):
    COUNTS["nba_cdn"] = COUNTS.get("nba_cdn", 0) + 1
    return CDN_GET(*args, **kwargs)


base.nba.requests.get = cdn_get
for module, endpoint in (
    (base.nba.leaguedashplayerstats, "LeagueDashPlayerStats"),
    (base.nba.leaguedashteamstats, "LeagueDashTeamStats"),
    (base.nba.scheduleleaguev2, "ScheduleLeagueV2"),
):
    original = getattr(module, endpoint)

    def counted(*args, _original=original, _name=endpoint, **kwargs):
        COUNTS[_name] = COUNTS.get(_name, 0) + 1
        return _original(*args, **kwargs)

    setattr(module, endpoint, counted)


@app.get("/__test__/search-counts")
async def counts():
    return dict(COUNTS)


@app.post("/__test__/search-control")
async def configure(request: Request):
    data = await request.json()
    STATE["adds"] = data.get("adds", 4)
    base.transport.STATE.update(league=901, changed=False, failed=False, seconds=0)
    COUNTS.clear()
    base.transport.nba._CACHE.clear()
    return dict(STATE)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8219, access_log=False, log_level="warning")
