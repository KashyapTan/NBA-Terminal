"""Production web build + real routes/normalizer/optimizer; synthetic boundary only."""

import copy
import os
from datetime import datetime, timedelta

import fantasy_e2e_server as base
import uvicorn
from fantasy_v6_fixture import team_bundle
from week_reset_fixture import NOW, new_week_payload

CLOCK_SHIFT = 0
COUNTER = None


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW + timedelta(minutes=40, seconds=CLOCK_SHIFT)


def get(self, views, *args, **kwargs):
    data = new_week_payload()
    if COUNTER is not None:
        data["league"]["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {"3": COUNTER}
    key = {
        "mSettings": "league",
        "mTeam": "league",
        "proTeamSchedules_wl": "schedule",
        "kona_player_info": "pool",
        "kona_playercard": "cards",
        "mTransactions2": "transactions",
        "mMatchupScore": "league",
    }[views[0]]
    return copy.deepcopy(data[key])


@base.webapp.app.post("/__test__/week-clock")
def advance(seconds: int):
    global CLOCK_SHIFT
    CLOCK_SHIFT += seconds
    return {"synthetic": True}


@base.webapp.app.post("/__test__/week-counter")
def counter(used: int | None = None):
    global COUNTER
    COUNTER = used
    return {"synthetic": True}


base.nba.load = lambda *args, **kwargs: (
    team_bundle(Clock.now().isoformat(), games=4)
    | {
        "schedule": None,
        "schedule_status": "unavailable",
    }
)
base.nba.load_prior_rates = lambda *args: {"prior_rates": [], "prior_rates_status": "unavailable"}
base.espn.datetime = Clock
base.adapter.datetime = Clock
base.espn.EspnClient.get = get
if __name__ == "__main__":
    uvicorn.run(
        base.webapp.app,
        host="127.0.0.1",
        port=int(os.environ.get("FANTASY_E2E_PORT", "8196")),
        access_log=False,
        log_level="warning",
    )
