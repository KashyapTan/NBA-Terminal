"""Today-slate scanner implemented inside the terminal package."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats, playergamelog, scoreboardv2
from nba_api.stats.static import teams

SEASON = "2025-26"
MIN_MINUTES = 25.0
EDGE_THRESHOLD = 3.0


def fetch_todays_games(game_date: str | None = None) -> list[dict[str, Any]]:
    """Fetch today's scheduled NBA games."""
    date = game_date or datetime.today().strftime("%Y-%m-%d")
    frame = scoreboardv2.ScoreboardV2(game_date=date, timeout=60).game_header.get_data_frame()
    id_to_team = {team["id"]: team for team in teams.get_teams()}
    games = []
    for _, row in frame.iterrows():
        home = id_to_team.get(row["HOME_TEAM_ID"])
        away = id_to_team.get(row["VISITOR_TEAM_ID"])
        if home and away:
            games.append({"home_team": home, "away_team": away, "date": date})
    return games


def fetch_qualified_players(team_ids: set[int], season: str = SEASON) -> dict[int, dict[str, Any]]:
    """Fetch players on slate teams who meet the minutes threshold."""
    frame = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        timeout=60,
    ).get_data_frames()[0]
    filtered = frame[
        (frame["TEAM_ID"].isin(team_ids))
        & (pd.to_numeric(frame["MIN"], errors="coerce") >= MIN_MINUTES)
        & (pd.to_numeric(frame["GP"], errors="coerce") >= 5)
    ]
    return {
        int(row["PLAYER_ID"]): {
            "name": row["PLAYER_NAME"],
            "team_id": int(row["TEAM_ID"]),
            "team_abbrev": row["TEAM_ABBREVIATION"],
            "avg_min": float(row["MIN"]),
            "season_avg": float(row["PTS"]),
        }
        for _, row in filtered.iterrows()
    }


def scan_slate_edges(season: str = SEASON, game_date: str | None = None) -> list[dict[str, Any]]:
    """Find players whose recent scoring trend differs meaningfully from season average."""
    games = fetch_todays_games(game_date)
    if not games:
        return []

    team_lookup: dict[int, tuple[dict[str, Any], dict[str, Any], bool]] = {}
    team_ids: set[int] = set()
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        team_ids.update({home["id"], away["id"]})
        team_lookup[home["id"]] = (home, away, True)
        team_lookup[away["id"]] = (away, home, False)

    players = fetch_qualified_players(team_ids, season)
    edges = []
    for player_id, player in players.items():
        try:
            logs = playergamelog.PlayerGameLog(player_id=player_id, season=season, timeout=60).get_data_frames()[0]
        except Exception:
            continue
        if logs.empty or "PTS" not in logs or len(logs) < 5:
            continue
        points = pd.to_numeric(logs["PTS"], errors="coerce").dropna()
        if points.empty:
            continue
        last_5 = float(points.head(5).mean())
        last_10 = float(points.head(10).mean()) if len(points) >= 10 else last_5
        season_avg = player["season_avg"]
        projection = (last_5 * 0.60) + (last_10 * 0.25) + (season_avg * 0.15)
        diff = projection - season_avg
        if abs(diff) < EDGE_THRESHOLD:
            continue
        team, opponent, is_home = team_lookup[player["team_id"]]
        edges.append(
            {
                "player_name": player["name"],
                "team_abbrev": team["abbreviation"],
                "opponent_abbrev": opponent["abbreviation"],
                "is_home": is_home,
                "direction": "OVER" if diff > 0 else "UNDER",
                "season_avg": season_avg,
                "prediction": projection,
                "diff": diff,
                "last_5": last_5,
                "last_10": last_10,
                "proj_minutes": player["avg_min"],
            }
        )
    edges.sort(key=lambda row: abs(row["diff"]), reverse=True)
    return edges
