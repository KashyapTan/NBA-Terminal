"""Pure formatting and ranking helpers used across terminal pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from statistics import fmean
from typing import Any

DEFENSE_COLUMNS = (
    "OPP_FG_PCT",
    "OPP_FG3_PCT",
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Corner 3",
    "Above the Break 3",
)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Return a finite float for display and ranking calculations."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in {float("inf"), float("-inf")}:
        return default
    return number


def format_percentage(value: Any) -> str:
    """Format a ratio as a one-decimal percentage string."""
    return f"{safe_float(value) * 100:.1f}%"


def format_signed(value: Any, digits: int = 1) -> str:
    """Format a signed decimal with a configurable precision."""
    return f"{safe_float(value):+.{digits}f}"


def defense_rank_tier(rank: int) -> tuple[str, str]:
    """Return a display tier and theme color key for a 1-based team rank."""
    if rank <= 0:
        raise ValueError("rank must be 1 or greater")
    if rank <= 5:
        return "Elite", "success"
    if rank <= 15:
        return "Good", "accent"
    if rank <= 20:
        return "Average", "text_primary"
    if rank <= 25:
        return "Below Avg", "warning"
    return "Poor", "danger"


def sort_team_defense(
    teams_data: Iterable[Mapping[str, Any]],
    key: str = "OPP_FG_PCT",
) -> list[dict[str, Any]]:
    """Sort team defense rows by a numeric stat in ascending order."""
    return sorted((dict(row) for row in teams_data), key=lambda row: safe_float(row.get(key)))


def league_averages(teams_data: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Calculate league averages for known defensive percentage columns."""
    if not teams_data:
        return {column: 0.0 for column in DEFENSE_COLUMNS}
    averages = {}
    for column in DEFENSE_COLUMNS:
        averages[column] = fmean(safe_float(row.get(column)) for row in teams_data)
    return averages


def consistency_label(cv_ratio: Any) -> tuple[str, str]:
    """Return a consistency label and theme color key for a CV ratio."""
    cv_percent = safe_float(cv_ratio) * 100
    if cv_percent < 30:
        return "Elite", "success"
    if cv_percent < 50:
        return "Good", "accent"
    if cv_percent < 70:
        return "Average", "warning"
    return "Variable", "danger"


def flatten_consistency_results(
    results: Mapping[int, Mapping[str, Sequence[Mapping[str, Any]]]],
    window: int,
    stat: str,
    limit: int | None = 10,
) -> list[dict[str, Any]]:
    """Extract and rank consistency rows for one game window and stat."""
    rows = [dict(row) for row in results.get(window, {}).get(stat, [])]
    rows.sort(key=lambda row: safe_float(row.get("cv")))
    if limit is not None:
        rows = rows[:limit]
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["cv_percent"] = safe_float(row.get("cv")) * 100
        row["label"], row["color_key"] = consistency_label(row.get("cv"))
    return rows


def summarize_consistency(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build summary stats for a list of consistency rows."""
    if not rows:
        return {"count": 0, "best_player": "N/A", "best_cv": 0.0, "avg_cv": 0.0}
    cvs = [safe_float(row.get("cv")) * 100 for row in rows]
    return {
        "count": len(rows),
        "best_player": str(rows[0].get("name", "N/A")),
        "best_cv": min(cvs),
        "avg_cv": fmean(cvs),
    }


def normalize_bet_direction(diff: Any) -> str:
    """Return OVER when a prediction beats the season average, otherwise UNDER."""
    return "OVER" if safe_float(diff) > 0 else "UNDER"


def sort_confident_bets(bets: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Sort confident bets by absolute model edge descending and normalize direction."""
    rows = [dict(row) for row in bets]
    rows.sort(key=lambda row: abs(safe_float(row.get("diff"))), reverse=True)
    for row in rows:
        row["direction"] = row.get("direction") or normalize_bet_direction(row.get("diff"))
    return rows


def parse_pick_date_from_name(filename: str) -> tuple[int, int, int] | None:
    """Parse a pick filename like 12_31_2025.MD into a sortable date tuple."""
    stem = filename.rsplit(".", 1)[0]
    parts = stem.split("_")
    if len(parts) != 3:
        return None
    try:
        month, day, year = (int(part) for part in parts)
    except ValueError:
        return None
    if not 1 <= month <= 12 or not 1 <= day <= 31 or year < 2000:
        return None
    return year, month, day
