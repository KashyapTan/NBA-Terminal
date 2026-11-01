"""Test-only production app with provider-shaped NBA transport and captured public tables.

No production module imports this file. Mixed captured/synthetic fixtures are not
live-provider or private-account success evidence.
"""

import json
import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import uvicorn
from nba_api.stats.library.http import NBAStatsHTTP, NBAStatsResponse

from nba_terminal import webapp
from nba_terminal.services import game_center

FIXTURES = Path(__file__).parent / "fixtures"
SCHEDULE = json.loads((FIXTURES / "nba_schedule_2026_11_01.json").read_text())["rows"]
FINAL = dict(
    SCHEDULE[0],
    gameDateEst="2025-06-22",
    gameDateTimeUTC="2025-06-23T00:00:00Z",
    gameId="0042400407",
    gameStatus=3,
    gameStatusText="Final",
    homeTeam_teamId=1610612760,
    homeTeam_teamName="Thunder",
    homeTeam_teamCity="Oklahoma City",
    homeTeam_teamTricode="OKC",
    homeTeam_score=103,
    awayTeam_teamId=1610612754,
    awayTeam_teamName="Pacers",
    awayTeam_teamCity="Indiana",
    awayTeam_teamTricode="IND",
    awayTeam_score=91,
)
FRAME = pd.DataFrame([*SCHEDULE, FINAL])
game_center.nba_today = lambda: date(2026, 11, 1)
game_center.scheduleleaguev2.ScheduleLeagueV2 = lambda **kwargs: SimpleNamespace(
    season_games=SimpleNamespace(get_data_frame=lambda: FRAME)
)


def rowset(name, records):
    headers = list(records[0])
    return {"name": name, "headers": headers, "rowSet": [[row.get(key) for key in headers] for row in records]}


def fixture_request(self, endpoint, parameters, **kwargs):
    if endpoint == "boxscoreadvancedv3":
        raw = (FIXTURES / "nba_boxscoreadvancedv3_finals_2025.json").read_text()
        return NBAStatsResponse(response=raw, status_code=200, url="captured-public-fixture")
    if endpoint == "leaguedashplayerstats":
        measure = parameters.get("MeasureType", "Base")
        if measure == "Advanced":
            payload = {
                "resultSets": [
                    rowset(
                        "LeagueDashPlayerStats",
                        [
                            {
                                "PLAYER_ID": player,
                                "GP": 23,
                                "MIN": 37.0,
                                "OFF_RATING": 111.7,
                                "DEF_RATING": 100.0,
                                "NET_RATING": 11.7,
                                "USG_PCT": 0.362,
                                "TS_PCT": 0.65,
                                "PIE": 0.178,
                                "PACE": 98.0,
                                "POSS": 77,
                            }
                            for player in (1628983, 203999)
                        ],
                    )
                ]
            }
        else:
            payload = json.loads((FIXTURES / f"nba_player_season_{measure.lower()}_2025.json").read_text())
            table = payload["resultSets"][0]
            extra = list(table["rowSet"][0])
            extra[table["headers"].index("PLAYER_ID")] = 203999
            table["rowSet"].append(extra)  # Explicitly synthetic second-player dashboard copy.
    elif endpoint == "playerdashboardbyshootingsplits":
        payload = json.loads((FIXTURES / "nba_player_shooting_splits_2025.json").read_text())
    elif endpoint == "playergamelog":
        second = int(parameters["PlayerID"]) == 203999
        records = []
        for i in range(20):
            records.append(
                {
                    "Game_ID": "0042400407" if i == 0 else f"00424003{i:02d}",
                    "GAME_DATE": f"2025-06-{22 - i:02d}",
                    "MATCHUP": "OKC vs. IND",
                    "WL": "W",
                    "MIN": 37,
                    "PTS": (30 if second else 20) + i % 9,
                    "REB": 9 if second else 5,
                    "AST": 7,
                    "STL": 1,
                    "BLK": 1,
                    "TOV": 2,
                    "FGM": 9,
                    "FGA": 18,
                    "FG3M": 2,
                    "FG3A": 5,
                    "FTM": 4,
                    "FTA": 5,
                    "PLUS_MINUS": 12,
                }
            )
        payload = {"resultSets": [rowset("PlayerGameLog", records)]}
    elif endpoint == "boxscoretraditionalv2":
        payload = {
            "resultSets": [
                rowset(
                    "PlayerStats",
                    [
                        {
                            "PLAYER_ID": 1628983,
                            "PLAYER_NAME": "Shai Gilgeous-Alexander",
                            "TEAM_ID": 1610612760,
                            "START_POSITION": "G",
                            "MIN": "37:00",
                            "PTS": 29,
                            "REB": 5,
                            "AST": 12,
                            "STL": 1,
                            "BLK": 2,
                            "TOV": 2,
                            "FGM": 8,
                            "FGA": 16,
                            "FG3M": 2,
                            "FG3A": 5,
                            "FTM": 11,
                            "FTA": 12,
                            "PLUS_MINUS": 12,
                        },
                    ],
                ),
                rowset("TeamStats", [{"TEAM_ID": 1610612760, "PTS": 103}, {"TEAM_ID": 1610612754, "PTS": 91}]),
                {"name": "TeamStarterBenchStats", "headers": ["TEAM_ID"], "rowSet": []},
            ]
        }
    elif endpoint == "shotchartdetail":
        payload = {
            "resultSets": [
                rowset(
                    "Shot_Chart_Detail",
                    [{"LOC_X": 30, "LOC_Y": 80, "SHOT_MADE_FLAG": 1, "ACTION_TYPE": "Jump Shot", "PERIOD": 1}],
                ),
                {"name": "LeagueAverages", "headers": ["FGA"], "rowSet": []},
            ]
        }
    else:
        raise RuntimeError(f"Unmocked NBA endpoint in deterministic V5 server: {endpoint}")
    return NBAStatsResponse(response=json.dumps(payload), status_code=200, url="synthetic-provider-transport")


NBAStatsHTTP.send_api_request = fixture_request


@webapp.app.get("/__test__/v5-fixture")
def marker():
    return {"synthetic": True, "captured": "V3 and public season/shooting tables", "live": False}


if __name__ == "__main__":
    uvicorn.run(
        webapp.app,
        host="127.0.0.1",
        port=int(os.environ.get("V5_E2E_PORT", "8195")),
        access_log=False,
        log_level="warning",
    )
