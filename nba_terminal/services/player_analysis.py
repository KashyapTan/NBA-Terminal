"""Game-specific player analysis with explicit NBA data availability states."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import boxscoreadvancedv2, playergamelog

from nba_terminal.services import game_center, player_data

ADVANCED_COLUMNS = (
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
    "AST_PCT",
    "AST_TO",
    "AST_RATIO",
    "OREB_PCT",
    "DREB_PCT",
    "REB_PCT",
    "TM_TOV_PCT",
    "EFG_PCT",
    "TS_PCT",
    "USG_PCT",
    "PACE",
    "POSS",
    "PIE",
)
HISTORY_COLUMNS = (
    "GAME_ID",
    "GAME_DATE",
    "MATCHUP",
    "WL",
    "MIN",
    "FGM",
    "FGA",
    "FG_PCT",
    "FG3M",
    "FG3A",
    "FG3_PCT",
    "FTM",
    "FTA",
    "FT_PCT",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
    "PTS",
    "PLUS_MINUS",
    "PRA",
    "PR",
    "PA",
    "RA",
    "STOCKS",
    "EFG_PCT",
    "TS_PCT",
    "FG3A_RATE",
    "FTA_RATE",
    "PTS_PER_FGA",
)


def fetch_player_game_analysis(game_id: str, player_id: int, season: str, phase: str) -> dict[str, Any]:
    """Return the selected game's line, advanced stats, shot map and separate season samples."""
    result = game_center.fetch_player_game_analysis(game_id, player_id, season, phase)
    result["advanced_stats"], result["advanced_stats_state"], result["advanced_stats_note"] = _fetch_advanced_stats(
        game_id, player_id
    )
    history, context = _fetch_history(
        player_id,
        season,
        phase,
        result.get("game_context") or {},
        game_id,
    )
    result["history"] = history
    result["history_state"] = history["state"]
    result["game_context"] = context
    return result


def _fetch_advanced_stats(game_id: str, player_id: int) -> tuple[dict[str, Any], str, str]:
    try:
        endpoint = boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=game_id, timeout=12)
        frames = endpoint.get_data_frames()
        frame = frames[0] if frames else pd.DataFrame()
    except Exception:
        return {}, "error", "NBA Stats could not return advanced stats for this game."

    if frame.empty or "PLAYER_ID" not in frame:
        return {}, "unavailable", "Advanced stats are not available for this game."
    matches = frame[pd.to_numeric(frame["PLAYER_ID"], errors="coerce") == player_id]
    if matches.empty:
        return {}, "unavailable", "NBA Stats returned no advanced line for this player."

    row = matches.iloc[0]
    values = {
        column.lower(): _clean_value(row.get(column))
        for column in ADVANCED_COLUMNS
        if column in frame.columns and _clean_value(row.get(column)) is not None
    }
    if not values:
        return {}, "unavailable", "NBA Stats returned no advanced metrics for this player."
    return values, "available", ""


def _fetch_history(
    player_id: int,
    season: str,
    phase: str,
    game_context: dict[str, Any],
    game_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = dict(game_context)
    try:
        frame = _fetch_game_log(player_id, season, phase)
    except Exception:
        return _empty_history(season, phase, "error", "Season game logs could not be loaded from NBA Stats."), context

    if frame.empty:
        return (
            _empty_history(
                season,
                phase,
                "unavailable",
                "NBA Stats returned no season game-log rows for this player.",
            ),
            context,
        )

    frame = frame.copy()
    if "GAME_DATE" in frame:
        frame = frame.sort_values("GAME_DATE", ascending=False, kind="stable", na_position="last")
    current_rows = frame[frame["GAME_ID"].astype(str) == str(game_id)] if "GAME_ID" in frame else frame.iloc[0:0]
    current = current_rows.iloc[0].to_dict() if not current_rows.empty else {}

    opponent = _opponent_abbreviation(context, current)
    context.update(
        {
            "season": season,
            "phase": phase,
            "game_id": str(game_id),
            "game_date": _date_value(current.get("GAME_DATE")),
            "matchup": _clean_value(current.get("MATCHUP")),
            "result": _clean_value(current.get("WL")),
        }
    )
    if opponent:
        context["opponent_abbreviation"] = opponent

    if opponent and "MATCHUP" in frame:
        matchup_pattern = rf"(?<![A-Z0-9]){re.escape(opponent)}(?![A-Z0-9])"
        opponent_frame = frame[frame["MATCHUP"].astype(str).str.upper().str.contains(matchup_pattern, regex=True)]
    else:
        opponent_frame = frame.iloc[0:0]

    history = {
        "state": "available",
        "note": "",
        "season": season,
        "phase": phase,
        "opponent": opponent,
        "games_played": int(len(frame)),
        "opponent_games_played": int(len(opponent_frame)),
        "summary": _summaries(frame),
        "games": _records(frame),
        "opponent_games": _records(opponent_frame),
    }
    return history, context


def _fetch_game_log(player_id: int, season: str, phase: str) -> pd.DataFrame:
    """Read a game log without converting missing box-score values to real zeroes."""
    endpoint = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star=phase,
        timeout=12,
    )
    frames = endpoint.get_data_frames()
    frame = frames[0] if frames else pd.DataFrame()
    if frame.empty:
        return frame

    frame = frame.copy()
    if "GAME_DATE" in frame:
        frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="coerce")
    for column in (
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
    ):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "MIN" in frame:
        frame["MIN"] = frame["MIN"].map(_nullable_minutes)
    return _add_derived_columns(frame)


def _add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the retained player-analysis calculations while preserving unknown inputs."""
    enriched = frame.copy()
    combinations = {
        "PRA": ("PTS", "REB", "AST"),
        "PR": ("PTS", "REB"),
        "PA": ("PTS", "AST"),
        "RA": ("REB", "AST"),
        "STOCKS": ("STL", "BLK"),
    }
    for target, sources in combinations.items():
        if all(source in enriched for source in sources):
            enriched[target] = enriched[list(sources)].sum(axis=1, min_count=len(sources))
    if {"FGM", "FG3M", "FGA"}.issubset(enriched.columns):
        denominator = enriched["FGA"].where(enriched["FGA"] > 0)
        enriched["EFG_PCT"] = (enriched["FGM"] + (0.5 * enriched["FG3M"])) / denominator
        if "FG3A" in enriched:
            enriched["FG3A_RATE"] = enriched["FG3A"] / denominator
        if "PTS" in enriched:
            enriched["PTS_PER_FGA"] = enriched["PTS"] / denominator
    if {"FTA", "FGA"}.issubset(enriched.columns):
        denominator = enriched["FGA"].where(enriched["FGA"] > 0)
        enriched["FTA_RATE"] = enriched["FTA"] / denominator
    if {"PTS", "FGA", "FTA"}.issubset(enriched.columns):
        denominator = 2 * (enriched["FGA"] + (0.44 * enriched["FTA"]))
        enriched["TS_PCT"] = enriched["PTS"] / denominator.where(denominator > 0)
    return enriched


def _nullable_minutes(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if ":" in text:
        minutes, seconds = text.split(":", maxsplit=1)
        try:
            return float(minutes) + (float(seconds) / 60)
        except ValueError:
            return None
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if not pd.isna(numeric) else None


def _empty_history(season: str, phase: str, state: str, note: str) -> dict[str, Any]:
    return {
        "state": state,
        "note": note,
        "season": season,
        "phase": phase,
        "opponent": None,
        "games_played": 0,
        "opponent_games_played": 0,
        "summary": {},
        "games": [],
        "opponent_games": [],
    }


def _opponent_abbreviation(context: dict[str, Any], current: dict[str, Any]) -> str | None:
    opponent = context.get("opponent")
    if isinstance(opponent, dict) and opponent.get("abbreviation"):
        return str(opponent["abbreviation"]).upper()

    matchup = str(current.get("MATCHUP") or "")
    team = context.get("team")
    team_abbreviation = str(team.get("abbreviation") or "").upper() if isinstance(team, dict) else ""
    parts = re.split(r"\s+(?:VS\.?|@)\s+", matchup, flags=re.IGNORECASE)
    if len(parts) == 2 and team_abbreviation:
        candidate = next((part.strip().upper() for part in parts if part.strip().upper() != team_abbreviation), "")
        return candidate or None
    return None


def _summaries(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for column, label, _value_type in player_data.PLAYER_PROFILE_GAME_STATS:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.empty:
            continue
        mean = float(values.mean())
        std = float(values.std()) if len(values) > 1 else 0.0
        item = {
            "label": label,
            "mean": mean,
            "std": std,
            "consistency_cv": std / mean if mean > 0 else 0.0,
            "games": int(len(values)),
        }
        for window in (5, 10, 20):
            recent = values.head(window)
            item[f"last_{window}"] = float(recent.mean()) if not recent.empty else None
            item[f"last_{window}_games"] = int(len(recent))
        summary[column] = item
    return summary


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [column for column in HISTORY_COLUMNS if column in frame.columns]
    return [
        {
            column.lower(): _date_value(value) if column == "GAME_DATE" else _clean_value(value)
            for column, value in row.items()
        }
        for row in frame.loc[:, columns].to_dict(orient="records")
    ]


def _date_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _clean_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)
