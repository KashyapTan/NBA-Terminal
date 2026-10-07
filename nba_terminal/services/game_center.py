"""NBA game-center queries and normalization for the web API."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv2, leaguegamefinder, scoreboardv2, shotchartdetail
from nba_api.stats.static import teams

SUPPORTED_FROM = "1996-97"
PHASES = ("Pre Season", "Regular Season", "Playoffs")


def current_season(today: date | None = None) -> str:
    """Return the NBA season containing today (seasons roll over in October)."""
    today = today or date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def available_seasons(today: date | None = None) -> list[str]:
    season = current_season(today)
    year = int(season[:4])
    return [f"{start}-{str(start + 1)[-2:]}" for start in range(year, 1995, -1)]


def _team_lookup() -> dict[int, dict[str, Any]]:
    return {
        int(team["id"]): {
            "id": int(team["id"]),
            "abbreviation": team["abbreviation"],
            "name": team["full_name"],
            "nickname": team["nickname"],
        }
        for team in teams.get_teams()
    }


def _serial(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _date_string(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else str(value)


def _season_start(season: str) -> int:
    try:
        start, end = season.split("-")
        if len(start) != 4 or len(end) != 2 or int(end) != (int(start) + 1) % 100:
            raise ValueError
        return int(start)
    except (TypeError, ValueError):
        raise ValueError("Season must use YYYY-YY format.") from None


def fetch_upcoming_games(start: date | None = None) -> dict[str, Any]:
    """Read today's and tomorrow's scoreboards; an empty slate is valid data."""
    start = start or date.today()
    lookup = _team_lookup()
    games = []
    for offset in range(2):
        game_date = start + timedelta(days=offset)
        frame = scoreboardv2.ScoreboardV2(game_date=game_date.isoformat(), timeout=12).game_header.get_data_frame()
        for _, row in frame.iterrows():
            status_id = int(_serial(row.get("GAME_STATUS_ID")) or 0)
            if status_id != 1:
                continue
            home = lookup.get(int(row.get("HOME_TEAM_ID", 0)))
            away = lookup.get(int(row.get("VISITOR_TEAM_ID", 0)))
            if home is None or away is None:
                continue
            games.append({
                "game_id": str(row.get("GAME_ID", "")),
                "date": game_date.isoformat(),
                "start_time": str(row.get("GAME_STATUS_TEXT", "Scheduled")),
                "status": str(row.get("GAME_STATUS_TEXT", "Scheduled")),
                "status_id": status_id,
                "phase": "Scheduled",
                "home_team": home,
                "away_team": away,
                "home_score": None,
                "away_score": None,
            })
    return {"games": games, "days": [start.isoformat(), (start + timedelta(days=1)).isoformat()]}


def fetch_recent_games(season: str) -> dict[str, Any]:
    """Fetch completed game rows for all supported season phases."""
    start_year = _season_start(season)
    if start_year < 1996:
        return {"season": season, "supported": False, "games": [], "phases": list(PHASES)}
    lookup = _team_lookup()
    by_id: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        frame = leaguegamefinder.LeagueGameFinder(
            league_id_nullable="00", season_nullable=season,
            season_type_nullable=phase, player_or_team_abbreviation="T", timeout=12,
        ).get_data_frames()[0]
        if frame.empty:
            continue
        for game_id, rows in frame.groupby("GAME_ID", sort=False):
            home_row = next((r for _, r in rows.iterrows() if "vs." in str(r.get("MATCHUP", ""))), None)
            away_row = next((r for _, r in rows.iterrows() if "@" in str(r.get("MATCHUP", ""))), None)
            if home_row is None or away_row is None:
                continue
            if pd.isna(home_row.get("WL")) or pd.isna(away_row.get("WL")):
                continue
            home_team = lookup.get(int(home_row.get("TEAM_ID", 0)))
            away_team = lookup.get(int(away_row.get("TEAM_ID", 0)))
            if home_team is None or away_team is None:
                continue
            by_id[str(game_id)] = {
                "game_id": str(game_id), "date": _date_string(home_row.get("GAME_DATE")),
                "phase": phase, "status": "Final", "home_team": home_team, "away_team": away_team,
                "home_score": _serial(home_row.get("PTS")), "away_score": _serial(away_row.get("PTS")),
            }
    games = sorted(by_id.values(), key=lambda item: (item["date"], item["game_id"]), reverse=True)
    return {"season": season, "supported": True, "games": games[:150], "phases": list(PHASES)}


def fetch_game_boxscore(game_id: str) -> dict[str, Any]:
    """Return traditional player and team box-score rows for one game."""
    if not game_id.isdigit() or len(game_id) != 10:
        raise ValueError("Game ID must be a 10-digit NBA game identifier.")
    endpoint = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id, timeout=12)
    frames = endpoint.get_data_frames()
    players_frame = frames[0] if frames else pd.DataFrame()
    team_frame = frames[1] if len(frames) > 1 else pd.DataFrame()
    lookup = _team_lookup()
    players_out = []
    for _, row in players_frame.iterrows():
        item = {str(k).lower(): _serial(v) for k, v in row.items()}
        team = lookup.get(int(row.get("TEAM_ID", 0)))
        item["team"] = team
        players_out.append(item)
    teams_out = []
    for _, row in team_frame.iterrows():
        item = {str(k).lower(): _serial(v) for k, v in row.items()}
        item["team"] = lookup.get(int(row.get("TEAM_ID", 0)))
        teams_out.append(item)
    return {"game_id": game_id, "players": players_out, "teams": teams_out}


def fetch_player_game_analysis(
    game_id: str, player_id: int, season: str, phase: str = "Regular Season"
) -> dict[str, Any]:
    """Return a single player's game line and shot locations when provided."""
    box = fetch_game_boxscore(game_id)
    player = next((item for item in box["players"] if item.get("player_id") == player_id), None)
    if player is None:
        raise ValueError("That player does not appear in this game's box score.")
    shots = []
    chart_state = "unavailable"
    try:
        frame = shotchartdetail.ShotChartDetail(
            team_id=0, player_id=player_id, game_id_nullable=game_id,
            season_nullable=season, season_type_all_star=phase,
            context_measure_simple="FGA", timeout=12,
        ).get_data_frames()[0]
        required = {"LOC_X", "LOC_Y", "SHOT_MADE_FLAG"}
        if required.issubset(frame.columns):
            for _, row in frame.iterrows():
                x, y = pd.to_numeric(row["LOC_X"], errors="coerce"), pd.to_numeric(row["LOC_Y"], errors="coerce")
                made = pd.to_numeric(row["SHOT_MADE_FLAG"], errors="coerce")
                if pd.isna(x) or pd.isna(y) or pd.isna(made):
                    continue
                shots.append({
                    "x": float(x), "y": float(y), "made": bool(int(made)),
                    "description": str(row.get("ACTION_TYPE", "")),
                    "period": _serial(row.get("PERIOD")),
                    "distance": _serial(row.get("SHOT_DISTANCE")),
                })
            chart_state = "available" if shots else "unavailable"
    except Exception:
        # Some game/season combinations do not expose shot locations. Box score remains useful.
        chart_state = "error"
    return {"game_id": game_id, "player": player, "stats": player, "shots": shots,
            "shot_chart_state": chart_state}
