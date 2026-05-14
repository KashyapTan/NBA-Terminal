"""Player game-log fetchers and stat summaries for terminal pages."""

from __future__ import annotations

from typing import Any

import pandas as pd
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players, teams

STAT_COLUMNS = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "3pt": "FG3M",
}

HIT_THRESHOLDS = {
    "PTS": (10, 12, 15, 18, 20, 25, 30),
    "REB": (4, 5, 6, 7, 8, 9, 10, 11, 12),
    "AST": (4, 5, 6, 7, 8, 9, 10, 11, 12),
}


def find_player_id(player_name: str) -> int:
    """Resolve a player name through nba_api static data."""
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        raise ValueError(f"Player not found: {player_name}")
    return int(matches[0]["id"])


def find_team_abbreviation(team_input: str) -> str:
    """Resolve a team abbreviation, full name, nickname, or city."""
    query = team_input.strip()
    if not query:
        raise ValueError("Team is required.")
    if len(query) <= 3:
        match = teams.find_team_by_abbreviation(query.upper())
        if match:
            return str(match["abbreviation"])
    matches = teams.find_teams_by_full_name(query)
    if not matches:
        matches = teams.find_teams_by_nickname(query)
    if not matches:
        lowered = query.lower()
        matches = [
            team
            for team in teams.get_teams()
            if lowered in team["full_name"].lower()
            or lowered in team["nickname"].lower()
            or lowered == team["city"].lower()
        ]
    exact = [team for team in matches if team["nickname"].lower() == query.lower()]
    if exact:
        matches = exact
    if len(matches) != 1:
        raise ValueError(f"Could not resolve one NBA team from: {team_input}")
    return str(matches[0]["abbreviation"])


def fetch_player_game_log(
    player_name: str,
    season: str,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Fetch one player's game log for a season."""
    player_id = find_player_id(player_name)
    endpoint = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star=season_type,
        timeout=60,
    )
    frame = endpoint.get_data_frames()[0]
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="coerce")
    return add_derived_columns(frame)


def add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add terminal-friendly derived box-score columns."""
    enriched = frame.copy()
    for column in ("PTS", "REB", "AST", "FGA", "FTA"):
        if column in enriched:
            enriched[column] = pd.to_numeric(enriched[column], errors="coerce").fillna(0)
    if {"PTS", "REB", "AST"}.issubset(enriched.columns):
        enriched["PRA"] = enriched["PTS"] + enriched["REB"] + enriched["AST"]
        enriched["PR"] = enriched["PTS"] + enriched["REB"]
        enriched["PA"] = enriched["PTS"] + enriched["AST"]
        enriched["RA"] = enriched["REB"] + enriched["AST"]
    if {"PTS", "FGA", "FTA"}.issubset(enriched.columns):
        denominator = 2 * (enriched["FGA"] + (0.44 * enriched["FTA"]))
        enriched["TS_PCT"] = enriched["PTS"].where(denominator > 0, 0) / denominator.where(denominator > 0, 1)
    return enriched


def filter_vs_team(frame: pd.DataFrame, team_input: str) -> pd.DataFrame:
    """Return games whose matchup contains the resolved opponent abbreviation."""
    if frame.empty:
        return frame
    abbrev = find_team_abbreviation(team_input)
    return frame[frame["MATCHUP"].str.contains(abbrev, case=False, na=False)].copy()


def summarize_stats(frame: pd.DataFrame) -> dict[str, Any]:
    """Summarize averages, standard deviations, and games played."""
    summary: dict[str, Any] = {"averages": {}, "std_devs": {}, "games_played": int(len(frame))}
    for stat_key, column in STAT_COLUMNS.items():
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        summary["averages"][stat_key] = float(values.mean()) if not values.empty else 0.0
        summary["std_devs"][stat_key] = float(values.std()) if len(values) > 1 else 0.0
    return summary


def rolling_summaries(frame: pd.DataFrame, windows: tuple[int, ...] = (5, 10, 15)) -> dict[int, dict[str, Any]]:
    """Build summaries for recent game windows."""
    return {
        window: summarize_stats(frame.head(window))
        for window in windows
        if not frame.empty and len(frame) >= window
    }


def hit_rates(
    frame: pd.DataFrame,
    stat_col: str,
    windows: tuple[int, ...] = (5, 10, 15),
) -> dict[int, dict[int, float]]:
    """Calculate hit rates for a stat over standard betting thresholds."""
    thresholds = HIT_THRESHOLDS.get(stat_col, ())
    output: dict[int, dict[int, float]] = {}
    if stat_col not in frame:
        return output
    for window in windows:
        if len(frame) < window:
            continue
        recent = pd.to_numeric(frame.head(window)[stat_col], errors="coerce").fillna(0)
        output[window] = {threshold: float((recent >= threshold).mean() * 100) for threshold in thresholds}
    return output


def visible_game_log_columns(frame: pd.DataFrame) -> list[str]:
    """Return terminal game-log columns present in a fetched frame."""
    preferred = [
        "GAME_DATE",
        "MATCHUP",
        "WL",
        "MIN",
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "PRA",
        "PR",
        "PA",
        "RA",
        "FGM",
        "FGA",
        "FG_PCT",
        "FG3M",
        "FG3A",
        "FG3_PCT",
        "FTM",
        "FTA",
        "FT_PCT",
        "TS_PCT",
        "PLUS_MINUS",
    ]
    return [column for column in preferred if column in frame.columns]
