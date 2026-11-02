"""Synthetic new-week boundary using retained public ESPN field shapes, not private data."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 11, 2, 17, 2, 22, 264988, tzinfo=timezone.utc)


def new_week_payload():
    data = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    raw = data["league"]
    raw.update(id=604550749, scoringPeriodId=13)
    raw["status"]["currentMatchupPeriod"] = 3
    raw["settings"]["scheduleSettings"]["matchupPeriods"]["3"] = list(range(13, 20))
    raw["settings"]["acquisitionSettings"].update(
        matchupAcquisitionLimit=1, matchupLimitPerScoringPeriod=True, acquisitionLimit=-1
    )
    raw["teams"][0].update(name="Kashyap", location="Kashyap", nickname="")
    for team in raw["teams"]:
        team["transactionCounter"] = {"acquisitions": 21}  # Whole map missing; explicit user fallback required.
    for match in raw["schedule"]:
        if match["matchupPeriodId"] == 2:
            match["matchupPeriodId"] = 3
            for side in (match.get("home", {}), match.get("away", {})):
                for value in side.get("cumulativeScore", {}).get("scoreByStat", {}).values():
                    value["score"] = 0
    for entry in raw["teams"][0]["roster"]["entries"]:
        for split in entry["playerPoolEntry"]["player"].get("stats", []):
            for key in ("0", "1", "2", "3", "6", "11", "13", "14", "15", "16", "17"):
                split["stats"][key] *= 0.05
    template = copy.deepcopy(data["schedule"]["settings"]["proTeams"][0])
    pro_teams = []
    for tid in range(1, 31):
        team = copy.deepcopy(template)
        team.update(id=tid, proGamesByScoringPeriod={})
        for i in range(7):
            start = datetime(2026, 11, 3, 0, tzinfo=timezone.utc) + timedelta(days=i)
            team["proGamesByScoringPeriod"][str(13 + i)] = [
                {
                    "date": start.timestamp() * 1000,
                    "homeProTeamId": tid,
                    "awayProTeamId": tid % 30 + 1,
                    "id": f"synthetic-{tid}-{i}",
                }
            ]
        pro_teams.append(team)
    data["schedule"]["settings"]["proTeams"] = pro_teams
    for collection in (data["pool"], data["cards"]):
        for entry in collection["players"]:
            player = entry.get("player", entry.get("playerPoolEntry", {}).get("player", {}))
            if player.get("id") == 1:
                # A weak, unprotected starter makes beneficial automatic moves
                # deterministic without bypassing the production core guard.
                for split in player.get("stats", []):
                    for key in ("0", "1", "2", "3", "6", "11", "13", "14", "15", "16", "17"):
                        split["stats"][key] *= 0.05
            if player.get("id") == 100:
                for split in player.get("stats", []):
                    split["stats"]["3"] = 120
                    split["stats"]["2"] = 30
    return data
