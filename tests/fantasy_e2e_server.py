"""Explicit test-only server: real routes/normalizer/planner with synthetic ESPN transport.

Run only from the repository for deterministic Playwright tests. Never installed
as a production entry point; no fixture code is imported by nba_terminal.
"""

import copy
import os
from datetime import datetime, timezone

import uvicorn
from fantasy_v2_fixture import league_payload

from nba_terminal import webapp
from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy as fantasy_stats
from nba_terminal.services import fantasy_planner_adapter as adapter

NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
RAW = league_payload()


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def synthetic_get(self, views, *args, **kwargs):
    if self.league_id == 126:
        raise espn.EspnError("upstream_timeout", "Synthetic ESPN timeout.", 504)
    data = copy.deepcopy(RAW)
    data["league"]["id"] = self.league_id
    data["league"]["settings"]["name"] = "Deterministic test league"
    current = data["league"]["status"]["currentMatchupPeriod"]
    own = next(
        side["cumulativeScore"]
        for match in data["league"]["schedule"]
        if match["matchupPeriodId"] == current
        for side in (match["home"], match["away"])
        if side["teamId"] == 1
    )
    for match in data["league"]["schedule"]:
        if match["matchupPeriodId"] == current:
            for side in (match["home"], match["away"]):
                if side["teamId"] == 14:
                    side["cumulativeScore"] = copy.deepcopy(own)
    if self.league_id == 125:
        data["league"]["settings"]["scoringSettings"]["scoringType"] = "H2H_POINTS"
    if self.league_id == 124:
        data["schedule"] = {}
    for collection in (data["pool"], data["cards"]):
        for entry in collection.get("players", []):
            player = espn.player_body(entry)
            if player.get("id") == 100:
                for split in player.get("stats", []):
                    if "stats" in split:
                        split["stats"]["3"] = 60  # deliberate synthetic streaming improvement
                        split["stats"]["2"] = 12
    return data[
        {
            "mSettings": "league",
            "proTeamSchedules_wl": "schedule",
            "kona_player_info": "pool",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
        }[views[0]]
    ]


espn.datetime = Clock
adapter.datetime = Clock
espn.EspnClient.get = synthetic_get
webapp.game_center.current_season = lambda today: "2026-27"
webapp.game_center.available_seasons = lambda today: ["2026-27", "2025-26"]
# Small real-shaped NBA season test sample, separate from league ownership/results.
PLAYERS = [
    {
        "player_id": 1,
        "player_name": "Synthetic season starter",
        "team_id": 1,
        "team_abbreviation": "TST",
        "team_name": "Test",
        "games": 10,
        "minutes_total": 320,
        "points": 200,
        "rebounds": 80,
        "assists": 60,
        "steals": 20,
        "blocks": 10,
        "turnovers": 30,
        "threes_made": 20,
        "three_attempts": 50,
        "field_goals_made": 60,
        "field_goal_attempts": 120,
        "free_throws_made": 30,
        "free_throw_attempts": 40,
    }
]
# The ordinary service boundary is mocked; HTTP serialization/cache/routes are production.
fantasy_stats.fetch_fantasy_season = lambda season, phase="Regular Season": {
    "season": season,
    "supported": True,
    "phase": phase,
    "players": PLAYERS,
}

if __name__ == "__main__":
    uvicorn.run(
        webapp.app,
        host="127.0.0.1",
        port=int(os.environ.get("FANTASY_E2E_PORT", "8197")),
        access_log=False,
        log_level="warning",
    )
