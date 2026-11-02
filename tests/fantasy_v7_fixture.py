"""Synthetic NBA transport shape converted from the explicit full-season ESPN fixture."""

import json
from pathlib import Path

from nba_terminal.services import fantasy_nba as nba


def full_nba_schedule():
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    from datetime import datetime, timezone

    espn_to_nba = {v: k for k, v in nba.NBA_TO_ESPN.items()}
    games = {}
    for team in raw["schedule"]["settings"]["proTeams"]:
        for entries in team["proGamesByScoringPeriod"].values():
            for game in entries:
                gid = "002" + str(game["id"]).zfill(7)
                games[gid] = {
                    "gameId": gid,
                    "gameDateTimeUTC": datetime.fromtimestamp(game["date"] / 1000, timezone.utc).isoformat(),
                    "gameStatus": 1,
                    "postponedStatus": "A",
                    "homeTeam": {"teamId": espn_to_nba[game["homeProTeamId"]]},
                    "awayTeam": {"teamId": espn_to_nba[game["awayProTeamId"]]},
                }
    return {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [{"games": list(games.values())}]}}


def pad_synthetic_inventory(schedule, anchor, protected_periods=()):
    """Preserve synthetic matchup rows and add reciprocal out-of-matchup season rows."""
    from datetime import datetime, time, timedelta, timezone

    by = {t["id"]: t for t in schedule["settings"]["proTeams"]}
    for home in range(1, 31, 2):
        away = home + 1
        mapping = by[home]["proGamesByScoringPeriod"]
        periods = set(map(int, mapping))
        for p in range(1, 175):
            if len(periods) >= 80:
                break
            if p not in protected_periods:
                periods.add(p)
        for p in sorted(periods, reverse=True):
            if len(periods) <= 80:
                break
            if p not in protected_periods:
                periods.remove(p)
        shared = {}
        for period in sorted(periods):
            start = datetime.combine(anchor + timedelta(days=period), time(23), timezone.utc)
            original = mapping.get(str(period), [{}])[0]
            shared[str(period)] = [
                {
                    "id": 900000 + home * 1000 + period,
                    "date": original.get("date", start.timestamp() * 1000),
                    "scoringPeriodId": period,
                    "homeProTeamId": home,
                    "awayProTeamId": away,
                    "validForLocking": True,
                    "startTimeTBD": False,
                    "statsOfficial": False,
                }
            ]
        for tid in (home, away):
            by[tid]["proGamesByScoringPeriod"] = json.loads(json.dumps(shared))
