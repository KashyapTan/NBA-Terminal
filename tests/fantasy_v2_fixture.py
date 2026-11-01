"""Synthetic 14-team, 13-player league for the full HTTP/browser chain. No private data."""

import copy
import json
from pathlib import Path


def league_payload():
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    template = copy.deepcopy(raw["league"]["teams"][0]["roster"]["entries"][0])
    base_player = template["playerPoolEntry"]["player"]
    base_player["droppable"] = True
    for split in base_player["stats"]:
        stats = split["stats"]
        stats.update(
            {
                "0": 100,
                "1": 2,
                "2": 4,
                "3": 12,
                "6": 16,
                "11": 6,
                "13": 35,
                "14": 75,
                "15": 20,
                "16": 25,
                "17": 10,
                "40": 180,
                "42": 10,
            }
        )
    # Two legally droppable options per team, including one first-round player.
    for team in raw["league"]["teams"]:
        roster = []
        team["transactionCounter"]["matchupAcquisitionTotals"] = {"2": 6}
        for slot in range(13):
            entry = copy.deepcopy(template)
            player = entry["playerPoolEntry"]["player"]
            player["id"] = team["id"] if slot == 0 else team["id"] * 1000 + slot
            player["fullName"] = f"Fixture Player {player['id']}"
            player["droppable"] = slot in (0, 2)
            if team["id"] == 1 and slot == 0:
                player.update(injured=True, injuryStatus="DAY_TO_DAY")
            if slot > 0:
                for split in player["stats"]:
                    split["stats"].update({"40": 320, "0": 200})
            entry["lineupSlotId"] = 0 if slot == 0 else (slot % 5 if slot < 10 else 12)
            roster.append(entry)
        team["roster"]["entries"] = roster
    raw["league"]["draftDetail"] = {"picks": [{"playerId": 1002, "overallPickNumber": 1, "roundId": 1}]}
    raw["pool"]["players"] = []
    for index in range(9):
        entry = copy.deepcopy(template["playerPoolEntry"])
        entry["status"] = "FREEAGENT"
        player = entry["player"]
        player["id"] = 100 + index
        player["fullName"] = f"Fixture Pickup {index + 1}"
        player["proTeamId"] = 2
        # Actual per-game totals span several strategically distinct upgrades.
        for split in player["stats"]:
            split["stats"].update(
                {"0": 150 + index * 2, "3": 55 + index, "2": 15, "6": 45, "1": 12, "17": 24, "40": 280, "42": 10}
            )
        raw["pool"]["players"].append(entry)
    raw["cards"] = {
        "players": [
            copy.deepcopy(row["playerPoolEntry"])
            for team in raw["league"]["teams"]
            for row in team["roster"]["entries"]
        ]
        + copy.deepcopy(raw["pool"]["players"])
    }
    return raw


def nba_rates_payload():
    """Official endpoint table; test values only, matching stable name + team."""
    headers = [
        "PLAYER_ID",
        "PLAYER_NAME",
        "TEAM_ID",
        "TEAM_ABBREVIATION",
        "GP",
        "MIN",
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "FG3M",
        "TOV",
        "FGM",
        "FGA",
        "FTM",
        "FTA",
    ]
    return {
        "resultSets": [
            {
                "name": "LeagueDashPlayerStats",
                "headers": headers,
                "rowSet": [
                    [
                        990100,
                        "Fixture Pickup 1",
                        1610612738,
                        "BOS",
                        10,
                        28,
                        15,
                        4.5,
                        5.5,
                        1.5,
                        1.2,
                        2.4,
                        0.6,
                        5,
                        10,
                        2,
                        2.5,
                    ]
                ],
            }
        ]
    }


def nba_schedule_payload():
    """Actual-shape regular-season schedule with a deterministic daily anchor."""
    return {
        "leagueSchedule": {
            "seasonYear": "2026-27",
            "gameDates": [
                {
                    "games": [
                        {
                            "gameId": f"00226000{index}",
                            "gameDateTimeUTC": date,
                            "homeTeam": {"teamId": 1610612737},
                            "awayTeam": {"teamId": 1610612738},
                            "gameStatus": 1,
                        }
                    ]
                }
                for index, date in enumerate(["2026-10-22T23:00:00Z", "2026-10-31T23:00:00Z", "2026-11-01T23:00:00Z"])
            ],
        }
    }
