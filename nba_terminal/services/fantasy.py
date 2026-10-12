"""Batched NBA season statistics for the Fantasy workspace."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats
from nba_api.stats.static import teams

MIN_SUPPORTED_SEASON = 1946
_SEASON_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
_COUNT_COLUMNS = {
    "games": "GP",
    "minutes_total": "MIN",
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    "threes_made": "FG3M",
    "three_attempts": "FG3A",
    "field_goals_made": "FGM",
    "field_goal_attempts": "FGA",
    "free_throws_made": "FTM",
    "free_throw_attempts": "FTA",
}
_REQUIRED_COLUMNS = {"PLAYER_ID", "PLAYER_NAME", *_COUNT_COLUMNS.values()}


def season_start_year(season: str) -> int:
    """Validate and return a season's starting year."""
    match = _SEASON_PATTERN.fullmatch(season) if isinstance(season, str) else None
    if match is None:
        raise ValueError("Season must use YYYY-YY format.")
    start, end = match.groups()
    start_year = int(start)
    if int(end) != (start_year + 1) % 100:
        raise ValueError("Season must use YYYY-YY format.")
    return start_year


def _number(value: Any) -> float | None:
    """Convert a source cell to a finite number while preserving missing values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _player_record(row: pd.Series) -> dict[str, Any] | None:
    player_id = _number(row.get("PLAYER_ID"))
    player_name = _text(row.get("PLAYER_NAME"))
    if player_id is None or not player_name:
        return None
    record: dict[str, Any] = {
        "player_id": int(player_id),
        "player_name": player_name,
        "team_id": int(_number(row.get("TEAM_ID")) or 0) or None,
        "team_abbreviation": _text(row.get("TEAM_ABBREVIATION")) or None,
    }
    record.update({key: _number(row.get(column)) for key, column in _COUNT_COLUMNS.items()})
    return record


def _merge_team_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine a traded player's team splits only when NBA Stats omitted a total row."""
    total_rows = [row for row in rows if row["team_abbreviation"] == "TOT"]
    if total_rows:
        return max(total_rows, key=lambda row: row["games"] or 0)
    if len(rows) == 1:
        return rows[0]

    merged = dict(rows[0])
    for key in _COUNT_COLUMNS:
        values = [row[key] for row in rows]
        merged[key] = (
            sum(values)
            if all(value is not None for value in values)
            else None
        )
    merged["team_id"] = None
    merged["team_abbreviation"] = "2TM"
    return merged


def normalize_player_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Normalize totals from the league-wide response into stable JSON rows."""
    if frame.empty:
        return []
    missing_columns = _REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        raise RuntimeError("NBA Stats returned player totals with an unsupported schema.")

    by_player: dict[int, list[dict[str, Any]]] = {}
    for _, source_row in frame.iterrows():
        record = _player_record(source_row)
        if record is not None:
            by_player.setdefault(record["player_id"], []).append(record)

    players = [_merge_team_rows(rows) for rows in by_player.values()]
    players.sort(key=lambda row: row["player_name"].casefold())
    return players


def fetch_fantasy_season(season: str) -> dict[str, Any]:
    """Fetch regular-season player totals with one league-wide NBA Stats request."""
    start_year = season_start_year(season)
    if start_year < MIN_SUPPORTED_SEASON:
        return {
            "season": season,
            "supported": False,
            "phase": "Regular Season",
            "players": [],
        }

    endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="Totals",
        timeout=12,
    )
    frames = endpoint.get_data_frames()
    frame = frames[0] if frames else pd.DataFrame()
    players = normalize_player_rows(frame)
    team_names = {team["abbreviation"]: team["full_name"] for team in teams.get_teams()}
    for player in players:
        abbreviation = player["team_abbreviation"]
        player["team_name"] = (
            team_names.get(abbreviation)
            if abbreviation and abbreviation not in {"TOT", "2TM"}
            else ("Multiple teams" if abbreviation in {"TOT", "2TM"} else None)
        )
    return {
        "season": season,
        "supported": True,
        "phase": "Regular Season",
        "players": players,
    }
