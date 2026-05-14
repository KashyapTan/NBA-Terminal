"""Team consistency calculations for the terminal."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from nba_api.stats.endpoints import commonteamroster, playergamelog
from nba_api.stats.static import teams

from nba_terminal.services.player_data import find_team_abbreviation

GAME_WINDOWS = (5, 10, 15, 20)
STATS_MAP = {
    "Points": "PTS",
    "Rebounds": "REB",
    "Assists": "AST",
    "Steals": "STL",
    "Blocks": "BLK",
}


def fetch_team_consistency(team_name: str, season: str) -> tuple[dict[int, dict[str, list[dict[str, Any]]]], str]:
    """Calculate CV rankings for roster players on one team."""
    team_abbrev = find_team_abbreviation(team_name)
    team = teams.find_team_by_abbreviation(team_abbrev)
    if not team:
        raise ValueError(f"Team not found: {team_name}")

    roster = commonteamroster.CommonTeamRoster(team_id=team["id"], season=season, timeout=60).get_data_frames()[0]
    results: dict[int, dict[str, list[dict[str, Any]]]] = {
        window: {stat: [] for stat in STATS_MAP} for window in GAME_WINDOWS
    }

    for _, player in roster.iterrows():
        time.sleep(0.25)
        try:
            games = playergamelog.PlayerGameLog(
                player_id=player["PLAYER_ID"],
                season=season,
                season_type_all_star="Regular Season",
                timeout=60,
            ).get_data_frames()[0]
        except Exception:
            continue
        if games.empty:
            continue
        for window in GAME_WINDOWS:
            if len(games) < window:
                continue
            recent = games.head(window)
            for stat_name, column in STATS_MAP.items():
                values = pd.to_numeric(recent[column], errors="coerce").dropna()
                mean = float(values.mean()) if not values.empty else 0.0
                std = float(values.std()) if len(values) > 1 else 0.0
                if mean <= 0 or std <= 0:
                    continue
                cv = std / mean
                if not np.isnan(cv) and not np.isinf(cv):
                    results[window][stat_name].append(
                        {
                            "name": player["PLAYER"],
                            "cv": float(cv),
                            "mean": mean,
                            "std": std,
                            "games": window,
                        }
                    )

    for window_data in results.values():
        for rows in window_data.values():
            rows.sort(key=lambda row: row["cv"])
    return results, str(team["full_name"])
