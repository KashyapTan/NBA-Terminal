"""Game-specific player analysis with explicit NBA data availability states."""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import (
    boxscoreadvancedv3,
    leaguedashplayerstats,
    playerdashboardbyshootingsplits,
    playergamelog,
)
from nba_api.stats.static import players

from nba_terminal.services import game_center, player_data

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
    result["advanced_stats_source"] = "BoxScoreAdvancedV3"
    result["derived_game_shooting"] = _aggregate_shooting([result.get("player") or {}])
    result["history"] = history
    result["history_state"] = history["state"]
    result["game_context"] = context
    return result


# V3 uses camelCase, decimal fraction percentages, and per-100-play assist/turnover ratios.
V3_COLUMNS = {
    "off_rating": "offensiveRating",
    "def_rating": "defensiveRating",
    "net_rating": "netRating",
    "ast_pct": "assistPercentage",
    "ast_to": "assistToTurnover",
    "ast_ratio": "assistRatio",
    "oreb_pct": "offensiveReboundPercentage",
    "dreb_pct": "defensiveReboundPercentage",
    "reb_pct": "reboundPercentage",
    "tov_ratio": "turnoverRatio",
    "efg_pct": "effectiveFieldGoalPercentage",
    "ts_pct": "trueShootingPercentage",
    "usg_pct": "usagePercentage",
    "pace": "pace",
    "poss": "possessions",
    "pie": "PIE",
}
logger = logging.getLogger(__name__)


def _fetch_advanced_stats(game_id: str, player_id: int) -> tuple[dict[str, Any], str, str]:
    try:
        endpoint = boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id, timeout=12)
        frames = endpoint.get_data_frames()
        frame = frames[0] if frames else pd.DataFrame()
    except Exception:
        logger.warning("AdvancedV3 request/parse failed for game %s", game_id, exc_info=True)
        return (
            {},
            "error",
            (
                "NBA Stats could not return advanced stats for this game. "
                "The V3 request or response parsing failed; retry later."
            ),
        )
    if frame.empty:
        return {}, "unavailable", "NBA Stats returned no advanced rows for this game."
    if "personId" not in frame:
        return {}, "error", "NBA Stats returned an unexpected advanced player schema (missing personId)."
    matches = frame[pd.to_numeric(frame["personId"], errors="coerce") == player_id]
    if "gameId" in matches:
        matches = matches[matches["gameId"].astype(str).str.zfill(10) == str(game_id).zfill(10)]
    if matches.empty:
        return {}, "unavailable", "NBA Stats returned no advanced line for this player."
    row = matches.iloc[0]
    # Do not present provider placeholder zeroes for a DNP as measured efficiency.
    if "minutes" in row and (_nullable_minutes(row.get("minutes")) or 0) <= 0:
        return {}, "unavailable", "No played minutes were returned for this player's advanced line."
    values = {
        key.lower(): _clean_value(row.get(column))
        for key, column in V3_COLUMNS.items()
        if column in frame and _clean_value(row.get(column)) is not None
    }
    if not values:
        return {}, "unavailable", "NBA Stats returned no advanced metrics for this player."
    return values, "available", ""


def fetch_season_advanced(season: str, phase: str, measure: str = "Advanced") -> dict[str, Any]:
    """One batch dashboard per season/phase, shared across independently browsed players."""
    try:
        endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season,
            season_type_all_star=phase,
            measure_type_detailed_defense=measure,
            per_mode_detailed="PerGame",
            timeout=12,
        )
        frames = endpoint.get_data_frames()
        frame = frames[0] if frames else pd.DataFrame()
    except Exception:
        logger.warning("Season dashboard failed: %s %s %s", season, phase, measure, exc_info=True)
        return {"state": "error", "note": f"{measure} season request or parsing failed; retry later.", "players": {}}
    if not frame.empty and "PLAYER_ID" not in frame:
        return {"state": "error", "note": "Unexpected season dashboard schema (missing PLAYER_ID).", "players": {}}
    rows = {}
    for row in frame.to_dict(orient="records"):
        identifier = pd.to_numeric(row.get("PLAYER_ID"), errors="coerce")
        if pd.isna(identifier):
            continue
        key = str(int(identifier))
        if key not in rows or float(row.get("GP") or 0) > float(rows[key].get("GP") or 0):
            rows[key] = {column: _clean_value(value) for column, value in row.items()}
    return {"state": "available" if rows else "unavailable", "note": "", "players": rows}


def fetch_player_profile(player_id: int, season: str, phase: str) -> dict[str, Any]:
    """Game-log profile independent of any selected game; advanced data is batched by the route."""
    player = players.find_player_by_id(player_id)
    if not player:
        raise ValueError("Player ID was not found in the bundled NBA player directory.")
    history, _ = _fetch_history(player_id, season, phase, {}, "")
    return {
        "player_id": player_id,
        "player_name": player["full_name"],
        "season": season,
        "phase": phase,
        "history": history,
        "history_state": history["state"],
        "shooting": _aggregate_shooting(history["games"]),
    }


def fetch_player_shooting_tables(player_id: int, season: str, phase: str) -> dict[str, Any]:
    """One on-demand request returns the retained six shooting tables, in provider Totals units."""
    try:
        endpoint = playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
            player_id=player_id,
            season=season,
            season_type_playoffs=phase,
            per_mode_detailed="Totals",
            timeout=12,
        )
    except Exception:
        logger.warning("Player shooting request failed: %s %s %s", player_id, season, phase, exc_info=True)
        return {"state": "error", "note": "Shooting splits request or parsing failed; retry later.", "tables": {}}
    tables = {}
    for label, attribute in player_data.SHOOTING_SPLIT_TABLES.items():
        try:
            frame = getattr(endpoint, attribute).get_data_frame()
            if not frame.empty and "GROUP_VALUE" not in frame:
                raise ValueError("Shooting split schema is missing GROUP_VALUE")
            rows = [
                {str(column): _clean_value(value) for column, value in row.items()}
                for row in frame.to_dict(orient="records")
            ]
            for row in rows:
                for attempts, percentages in (("FGA", ("FG_PCT", "EFG_PCT")), ("FG3A", ("FG3_PCT",))):
                    if row.get(attempts) == 0:
                        for column in percentages:
                            if column in row:
                                row[column] = None
            for row in rows:
                for attempts, percentages in (("FGA", ("FG_PCT", "EFG_PCT")), ("FG3A", ("FG3_PCT",))):
                    if row.get(attempts) == 0:
                        for column in percentages:
                            if column in row:
                                row[column] = None
            tables[label] = {
                "state": "available" if rows else "unavailable",
                "note": "" if rows else "NBA Stats returned no rows for this breakdown.",
                "rows": rows,
            }
        except Exception:
            logger.warning("Shooting split schema failed: %s %s", player_id, label, exc_info=True)
            tables[label] = {"state": "error", "note": "This shooting breakdown could not be parsed.", "rows": []}
    state = (
        "error"
        if any(t["state"] == "error" for t in tables.values())
        else "available"
        if any(t["rows"] for t in tables.values())
        else "unavailable"
    )
    return {
        "state": state,
        "note": "",
        "tables": tables,
        "source": "PlayerDashboardByShootingSplits · Totals",
        "season": season,
        "phase": phase,
    }


def _aggregate_shooting(games: list[dict[str, Any]]) -> dict[str, Any]:
    """Ratio of totals from jointly complete games; never an unweighted mean of percentages."""
    definitions = {
        "efg_pct": (["fgm", "fg3m", "fga"], lambda r: r["fgm"] + 0.5 * r["fg3m"], lambda r: r["fga"]),
        "ts_pct": (["pts", "fga", "fta"], lambda r: r["pts"], lambda r: 2 * (r["fga"] + 0.44 * r["fta"])),
        "fg3a_rate": (["fg3a", "fga"], lambda r: r["fg3a"], lambda r: r["fga"]),
        "fta_rate": (["fta", "fga"], lambda r: r["fta"], lambda r: r["fga"]),
    }
    result = {}
    for key, (columns, numerator, denominator) in definitions.items():
        rows = [r for r in games if all(isinstance(r.get(c), (int, float)) for c in columns)]
        total = sum(denominator(r) for r in rows)
        result[key] = {"value": sum(numerator(r) for r in rows) / total if total > 0 else None, "games": len(rows)}
    return result


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

    if not {"GAME_ID", "GAME_DATE"}.issubset(frame.columns):
        return _empty_history(season, phase, "error", "Unexpected game-log schema: missing game ID or date."), context

    frame = frame.copy()
    if "GAME_ID" in frame:
        frame["GAME_ID"] = frame["GAME_ID"].map(lambda value: _game_id(value))
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
        opponent_frame = frame[frame["MATCHUP"].map(_matchup_opponent) == opponent]
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
    # Installed/reference schemas use Game_ID/Player_ID; some provider responses
    # already use uppercase. Normalize both before required-field validation.
    frame.columns = [str(column).upper() for column in frame.columns]
    if "GAME_ID" in frame:
        frame["GAME_ID"] = frame["GAME_ID"].map(lambda value: _game_id(value))
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


def _matchup_opponent(value: Any) -> str | None:
    """NBA logs place the player's team first, including games before a trade."""
    match = re.fullmatch(r"\s*[A-Z0-9]{2,5}\s+(?:VS\.?|@)\s+([A-Z0-9]{2,5})\s*", str(value), re.IGNORECASE)
    return match.group(1).upper() if match else None


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
            column.lower(): (
                _date_value(value)
                if column == "GAME_DATE"
                else _game_id(value)
                if column == "GAME_ID"
                else _clean_value(value)
            )
            for column, value in row.items()
        }
        for row in frame.loc[:, columns].to_dict(orient="records")
    ]


def _game_id(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return str(int(float(text))).zfill(10)
    return text


def _date_value(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _clean_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)
