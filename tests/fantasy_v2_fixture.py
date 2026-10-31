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
    # One expendable low-minute stream slot, twelve long-term core players per team.
    for team in raw["league"]["teams"]:
        roster = []
        team["transactionCounter"]["matchupAcquisitionTotals"] = {"2": 5}
        for slot in range(13):
            entry = copy.deepcopy(template)
            player = entry["playerPoolEntry"]["player"]
            player["id"] = team["id"] if slot == 0 else team["id"] * 1000 + slot
            player["fullName"] = f"Fixture Player {player['id']}"
            player["droppable"] = slot == 0
            entry["lineupSlotId"] = 0 if slot == 0 else (slot % 5 if slot < 10 else 12)
            roster.append(entry)
        team["roster"]["entries"] = roster
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
