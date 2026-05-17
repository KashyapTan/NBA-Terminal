"""Player game-log fetchers and stat summaries for terminal pages."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats, playerdashboardbyshootingsplits, playergamelog
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
    "PRA": (20, 25, 30, 35, 40, 45, 50, 55),
    "PR": (15, 20, 25, 30, 35, 40, 45),
    "PA": (15, 20, 25, 30, 35, 40, 45),
    "RA": (10, 15, 20, 25, 30, 35),
    "FG3M": (1, 2, 3, 4, 5, 6),
}

PLAYER_PROFILE_MEASURES = ("Base", "Advanced", "Misc", "Scoring", "Usage", "Defense")
PLAYER_PROFILE_WINDOWS = (5, 10, 20)
PLAYER_PROFILE_CACHE_VERSION = 1
PLAYER_PROFILE_HIT_STATS = ("PTS", "REB", "AST", "PRA", "PR", "PA", "RA", "FG3M")
PLAYER_PROFILE_GAME_STATS = (
    ("MIN", "MIN", "number"),
    ("PTS", "PTS", "number"),
    ("REB", "REB", "number"),
    ("AST", "AST", "number"),
    ("PRA", "PRA", "number"),
    ("PR", "PTS+REB", "number"),
    ("PA", "PTS+AST", "number"),
    ("RA", "REB+AST", "number"),
    ("STL", "STL", "number"),
    ("BLK", "BLK", "number"),
    ("STOCKS", "STL+BLK", "number"),
    ("TOV", "TOV", "number"),
    ("FG3M", "3PM", "number"),
    ("FG3A", "3PA", "number"),
    ("FG_PCT", "FG%", "pct"),
    ("FG3_PCT", "3P%", "pct"),
    ("FT_PCT", "FT%", "pct"),
    ("EFG_PCT", "eFG%", "pct"),
    ("TS_PCT", "TS%", "pct"),
    ("FG3A_RATE", "3PAr", "pct"),
    ("FTA_RATE", "FTr", "pct"),
    ("PTS_PER_FGA", "PTS/FGA", "number"),
    ("PLUS_MINUS", "+/-", "number"),
)
SHOOTING_SPLIT_TABLES = {
    "Overall": "overall_player_dashboard",
    "Shot Area": "shot_area_player_dashboard",
    "Distance 5ft": "shot5_ft_player_dashboard",
    "Distance 8ft": "shot8_ft_player_dashboard",
    "Assisted": "assited_shot_player_dashboard",
    "Shot Type Summary": "shot_type_summary_player_dashboard",
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
    numeric_columns = (
        "MIN",
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "TOV",
        "FGM",
        "FGA",
        "FG3M",
        "FG3A",
        "FTM",
        "FTA",
        "OREB",
        "DREB",
        "PF",
        "PLUS_MINUS",
    )
    for column in numeric_columns:
        if column in enriched:
            enriched[column] = pd.to_numeric(enriched[column], errors="coerce").fillna(0)
    if {"PTS", "REB", "AST"}.issubset(enriched.columns):
        enriched["PRA"] = enriched["PTS"] + enriched["REB"] + enriched["AST"]
        enriched["PR"] = enriched["PTS"] + enriched["REB"]
        enriched["PA"] = enriched["PTS"] + enriched["AST"]
        enriched["RA"] = enriched["REB"] + enriched["AST"]
    if {"STL", "BLK"}.issubset(enriched.columns):
        enriched["STOCKS"] = enriched["STL"] + enriched["BLK"]
    if {"FGM", "FG3M", "FGA"}.issubset(enriched.columns):
        denominator = enriched["FGA"].where(enriched["FGA"] > 0, 1)
        enriched["EFG_PCT"] = (enriched["FGM"] + (0.5 * enriched["FG3M"])) / denominator
        enriched["FG3A_RATE"] = enriched["FG3A"] / denominator if "FG3A" in enriched.columns else 0
        enriched["PTS_PER_FGA"] = enriched["PTS"] / denominator if "PTS" in enriched.columns else 0
    if {"FTA", "FGA"}.issubset(enriched.columns):
        denominator = enriched["FGA"].where(enriched["FGA"] > 0, 1)
        enriched["FTA_RATE"] = enriched["FTA"] / denominator
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


def fetch_player_stat_profile(
    player_name: str,
    season: str,
    season_type: str,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Fetch all-around player profile data for one season."""
    player_id = find_player_id(player_name)
    if use_cache:
        cached = _load_player_profile_cache(player_id, season, season_type)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    warnings: list[str] = []

    game_log = fetch_player_game_log(player_name, season, season_type)
    if game_log.empty:
        warnings.append("No game-log rows returned for this player, season, and season type.")

    measures = {}
    for measure in PLAYER_PROFILE_MEASURES:
        try:
            row, warning = _fetch_league_dashboard_row(player_id, player_name, season, season_type, measure)
            measures[measure] = row
            if warning:
                warnings.append(f"{measure}: {warning}")
        except Exception as exc:
            measures[measure] = {}
            warnings.append(f"{measure} dashboard unavailable: {exc}")

    shooting_splits = {}
    try:
        shooting_splits = fetch_player_shooting_splits(player_id, season, season_type)
    except Exception as exc:
        warnings.append(f"Shooting splits unavailable: {exc}")

    base = measures.get("Base", {})
    resolved_name = str(base.get("PLAYER_NAME") or player_name)
    team = str(base.get("TEAM_ABBREVIATION") or "")
    profile = {
        "player": resolved_name,
        "player_id": player_id,
        "team": team,
        "season": season,
        "season_type": season_type,
        "cache_hit": False,
        "game_log": game_log,
        "measures": measures,
        "game_summary": summarize_profile_game_stats(game_log),
        "hit_rate_rows": profile_hit_rate_rows(game_log),
        "shooting_splits": shooting_splits,
        "warnings": warnings,
    }
    if use_cache:
        _write_player_profile_cache(player_id, season, season_type, profile)
    return profile


def clear_player_profile_cache() -> int:
    """Delete cached player profile payloads and return the number of files removed."""
    cache_dir = _player_profile_cache_dir()
    if not cache_dir.exists():
        return 0
    removed = 0
    for path in cache_dir.glob("*.json"):
        if not path.is_file():
            continue
        path.unlink()
        removed += 1
    return removed


def fetch_player_shooting_splits(player_id: int, season: str, season_type: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch player shooting split tables from the shooting dashboard endpoint."""
    endpoint = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
        player_id=player_id,
        season=season,
        season_type_playoffs=season_type,
        per_mode_detailed="Totals",
        timeout=60,
    )
    split_tables = {}
    for label, attribute in SHOOTING_SPLIT_TABLES.items():
        frame = getattr(endpoint, attribute).get_data_frame()
        split_tables[label] = _records_from_frame(frame)
    return split_tables


def summarize_profile_game_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarize game-log stats, volatility, and recent form windows."""
    rows = []
    for column, label, value_type in PLAYER_PROFILE_GAME_STATS:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.empty:
            average = std = cv = 0.0
        else:
            average = float(values.mean())
            std = float(values.std()) if len(values) > 1 else 0.0
            cv = std / average if average > 0 else 0.0
        row: dict[str, Any] = {
            "column": column,
            "label": label,
            "type": value_type,
            "avg": average,
            "std": std,
            "cv": cv,
        }
        for window in PLAYER_PROFILE_WINDOWS:
            recent = values.head(window)
            row[f"last_{window}"] = float(recent.mean()) if not recent.empty else 0.0
        rows.append(row)
    return rows


def profile_hit_rate_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Build hit-rate rows for betting-facing player stat thresholds."""
    rows = []
    for stat in PLAYER_PROFILE_HIT_STATS:
        if stat not in frame:
            continue
        values = pd.to_numeric(frame[stat], errors="coerce").fillna(0)
        for threshold in HIT_THRESHOLDS.get(stat, ()):
            row: dict[str, Any] = {"market": f"{_market_label(stat)} {threshold}+"}
            row["season"] = _hit_rate_for_values(values, threshold)
            for window in PLAYER_PROFILE_WINDOWS:
                recent = values.head(window)
                row[f"last_{window}"] = _hit_rate_for_values(recent, threshold)
            rows.append(row)
    return rows


def _player_profile_cache_dir() -> Path:
    root = os.environ.get("NBA_TERMINAL_CACHE_DIR")
    if root:
        return Path(root) / "player_profiles"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "NBA Terminal" / "cache" / "player_profiles"
    return Path.home() / ".nba_terminal" / "cache" / "player_profiles"


def _player_profile_cache_path(player_id: int, season: str, season_type: str) -> Path:
    key = _cache_slug(f"{player_id}_{season}_{season_type}_{date.today().isoformat()}")
    return _player_profile_cache_dir() / f"{key}.json"


def _cache_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "player_profile"


def _load_player_profile_cache(player_id: int, season: str, season_type: str) -> dict[str, Any] | None:
    path = _player_profile_cache_path(player_id, season, season_type)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("version") != PLAYER_PROFILE_CACHE_VERSION:
            return None
        return _profile_from_cache_payload(payload["profile"])
    except (OSError, KeyError, TypeError, ValueError):
        return None


def _write_player_profile_cache(player_id: int, season: str, season_type: str, profile: dict[str, Any]) -> None:
    path = _player_profile_cache_path(player_id, season, season_type)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PLAYER_PROFILE_CACHE_VERSION,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "profile": _profile_to_cache_payload(profile),
        }
        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        temp_path.replace(path)
    except OSError:
        return


def _profile_to_cache_payload(profile: dict[str, Any]) -> dict[str, Any]:
    payload = dict(profile)
    game_log = payload.get("game_log")
    if isinstance(game_log, pd.DataFrame):
        payload["game_log"] = game_log.to_json(orient="split", date_format="iso")
    payload["cache_hit"] = False
    return payload


def _profile_from_cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    profile = dict(payload)
    game_log = profile.get("game_log")
    if isinstance(game_log, str):
        profile["game_log"] = pd.read_json(StringIO(game_log), orient="split")
        if "GAME_DATE" in profile["game_log"]:
            profile["game_log"]["GAME_DATE"] = pd.to_datetime(profile["game_log"]["GAME_DATE"], errors="coerce")
    return profile


def _fetch_league_dashboard_row(
    player_id: int,
    player_name: str,
    season: str,
    season_type: str,
    measure: str,
) -> tuple[dict[str, Any], str | None]:
    endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star=season_type,
        measure_type_detailed_defense=measure,
        per_mode_detailed="PerGame",
        timeout=60,
    )
    frame = endpoint.get_data_frames()[0]
    return _select_player_row(frame, player_id, player_name)


def _select_player_row(frame: pd.DataFrame, player_id: int, player_name: str) -> tuple[dict[str, Any], str | None]:
    if frame.empty:
        return {}, "league dashboard returned no rows."

    matches = pd.DataFrame()
    if "PLAYER_ID" in frame:
        player_ids = pd.to_numeric(frame["PLAYER_ID"], errors="coerce")
        matches = frame[player_ids == player_id]
    if matches.empty and "PLAYER_NAME" in frame:
        lowered = player_name.strip().lower()
        matches = frame[frame["PLAYER_NAME"].astype(str).str.lower() == lowered]
    if matches.empty:
        return {}, "player was not present in the league dashboard response."

    warning = None
    if len(matches) > 1 and "GP" in matches:
        warning = "multiple rows matched; using the row with the most games played."
        matches = matches.assign(_GP_SORT=pd.to_numeric(matches["GP"], errors="coerce").fillna(0))
        matches = matches.sort_values("_GP_SORT", ascending=False).drop(columns=["_GP_SORT"])
    return _clean_record(matches.iloc[0]), warning


def _records_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    return [_clean_record(row) for _, row in frame.iterrows()]


def _clean_record(row: pd.Series) -> dict[str, Any]:
    record = {}
    for key, value in row.items():
        if pd.isna(value):
            record[str(key)] = ""
        elif hasattr(value, "item"):
            record[str(key)] = value.item()
        else:
            record[str(key)] = value
    return record


def _hit_rate_for_values(values: pd.Series, threshold: int) -> float:
    if values.empty:
        return 0.0
    return float((values >= threshold).mean() * 100)


def _market_label(stat: str) -> str:
    return "3PM" if stat == "FG3M" else stat
