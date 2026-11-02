"""Production web build + real routes/normalizer/optimizer; synthetic boundary only."""

import copy
import os
from datetime import datetime

import fantasy_e2e_server as base
import uvicorn
from week_reset_fixture import NOW, new_week_payload


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def get(self, views, *args, **kwargs):
    data = new_week_payload()
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


base.nba.load = lambda *args, **kwargs: {
    "rates": [],
    "schedule": None,
    "rates_status": "unavailable",
    "schedule_status": "unavailable",
}
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
