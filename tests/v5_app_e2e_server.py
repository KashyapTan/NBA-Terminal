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
from nba_terminal.services import game_center, legacy_tools

FIXTURES = Path(__file__).parent / "fixtures"
SCHEDULE = json.loads((FIXTURES / "nba_schedule_2026_11_01.json").read_text())["rows"]
FINAL = dict(
    SCHEDULE[0],
    gameDateEst="2025-06-22T00:00:00Z",
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
    if endpoint == "playergamelog" and int(parameters["PlayerID"]) == 1628983:
        raw = (FIXTURES / "nba_playergamelog_playoffs_2025.json").read_text()
        return NBAStatsResponse(response=raw, status_code=200, url="captured-public-playergamelog")
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
            if "PLAYER_NAME" in table["headers"]:
                extra[table["headers"].index("PLAYER_NAME")] = "Nikola Jokić"
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
                            "TO": 2,
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


# Synthetic provider DataFrames for the standalone batched endpoints. The actual
# LegacyToolsService/cache/router/formulas still run; no normalized tool result is mocked.
def provider_frame(frame):
    return SimpleNamespace(get_data_frames=lambda: [frame])


BATCH_LOGS = pd.DataFrame(
    [
        {
            "PLAYER_ID": player,
            "TEAM_ID": 1610612760,
            "GAME_ID": f"00424003{i:02d}",
            "GAME_DATE": f"2025-06-{21 - i:02d}",
            "PTS": 40 + i % 5,
            "MIN": 37,
            "REB": 5 + i % 4,
            "AST": 6 + i % 3,
            "STL": i % 2,
            "BLK": i % 3,
        }
        for player in (1628983, 203999)
        for i in range(20)
    ]
)
legacy_tools.playergamelogs.PlayerGameLogs = lambda **kwargs: provider_frame(BATCH_LOGS.copy())
legacy_tools.commonteamroster.CommonTeamRoster = lambda **kwargs: provider_frame(
    pd.DataFrame(
        [
            {"PLAYER_ID": 1628983, "PLAYER": "Shai Gilgeous-Alexander"},
            {"PLAYER_ID": 203999, "PLAYER": "Nikola Jokić"},
        ]
    )
)
legacy_tools.leaguedashteamstats.LeagueDashTeamStats = lambda **kwargs: provider_frame(
    pd.DataFrame(
        [
            {"TEAM_ID": 1610612760, "DEF_RATING": 108, "PACE": 98, "OPP_FG_PCT": 0.45, "OPP_FG3_PCT": 0.34},
            {"TEAM_ID": 1610612754, "DEF_RATING": 114, "PACE": 102, "OPP_FG_PCT": 0.48, "OPP_FG3_PCT": 0.37},
        ]
    )
)
ZONE_NAMES = [
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Left Corner 3",
    "Right Corner 3",
    "Above the Break 3",
]
ZONE_FRAME = pd.DataFrame(
    [[1610612760, 0.6, 0.45, 0.4, 0.3, 0.4, 0.35], [1610612754, 0.65, 0.5, 0.45, 0.35, 0.4, 0.38]],
    columns=pd.MultiIndex.from_tuples([("", "TEAM_ID"), *[(name, "OPP_FG_PCT") for name in ZONE_NAMES]]),
)
legacy_tools.leaguedashteamshotlocations.LeagueDashTeamShotLocations = lambda **kwargs: provider_frame(
    ZONE_FRAME.copy()
)


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
