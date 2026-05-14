"""Native player-points projection service for the terminal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, leaguegamefinder, scoreboardv2
from nba_api.stats.static import teams

from nba_terminal.services.player_data import fetch_player_game_log, find_team_abbreviation


def _team_by_abbreviation(abbrev: str) -> dict[str, Any]:
    team = teams.find_team_by_abbreviation(abbrev.upper())
    if not team:
        raise ValueError(f"Team not found: {abbrev}")
    return team


def fetch_matchup_context(
    player_team: str,
    opponent_team: str,
    season: str,
    game_date: str | None = None,
) -> dict[str, Any]:
    """Fetch opponent defense, pace, home/away, and rest context."""
    date = game_date or datetime.today().strftime("%Y-%m-%d")
    team = _team_by_abbreviation(find_team_abbreviation(player_team))
    opponent = _team_by_abbreviation(find_team_abbreviation(opponent_team))

    rest_days = 3
    try:
        games = leaguegamefinder.LeagueGameFinder(team_id_nullable=team["id"], timeout=60).get_data_frames()[0]
        games["GAME_DATE"] = pd.to_datetime(games["GAME_DATE"], errors="coerce")
        completed = games.dropna(subset=["WL"]).sort_values("GAME_DATE", ascending=False)
        if not completed.empty:
            rest_days = max(0, min(5, (pd.to_datetime(date) - completed.iloc[0]["GAME_DATE"]).days - 1))
    except Exception:
        rest_days = 3

    is_home = 0
    try:
        scoreboard = scoreboardv2.ScoreboardV2(game_date=date, timeout=60).game_header.get_data_frame()
        team_game = scoreboard[
            (scoreboard["HOME_TEAM_ID"] == team["id"]) | (scoreboard["VISITOR_TEAM_ID"] == team["id"])
        ]
        if not team_game.empty:
            is_home = 1 if int(team_game.iloc[0]["HOME_TEAM_ID"]) == int(team["id"]) else 0
    except Exception:
        is_home = 0

    advanced = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        measure_type_detailed_defense="Advanced",
        timeout=60,
    ).get_data_frames()[0]
    id_to_abbrev = {item["id"]: item["abbreviation"] for item in teams.get_teams()}
    advanced = advanced.copy()
    advanced["TEAM_ABBREVIATION"] = advanced["TEAM_ID"].map(id_to_abbrev)
    opponent_row = advanced[advanced["TEAM_ABBREVIATION"] == opponent["abbreviation"]]
    league_def = float(pd.to_numeric(advanced["DEF_RATING"], errors="coerce").mean())
    league_pace = float(pd.to_numeric(advanced["PACE"], errors="coerce").mean())
    if opponent_row.empty:
        def_rating = league_def
        pace = league_pace
    else:
        def_rating = float(opponent_row.iloc[0]["DEF_RATING"])
        pace = float(opponent_row.iloc[0]["PACE"])

    return {
        "player_team": team["abbreviation"],
        "opponent": opponent["abbreviation"],
        "opponent_name": opponent["full_name"],
        "is_home": is_home,
        "rest_days": rest_days,
        "def_rating": def_rating,
        "league_def_rating": league_def,
        "pace": pace,
        "league_pace": league_pace,
    }


def project_points(
    player_name: str,
    player_team: str,
    opponent_team: str,
    season: str,
    projected_minutes: float,
    season_type: str = "Regular Season",
) -> dict[str, Any]:
    """Build a transparent weighted points projection."""
    game_log = fetch_player_game_log(player_name, season, season_type)
    if game_log.empty or "PTS" not in game_log:
        raise ValueError(f"No points game log found for {player_name} in {season}.")

    points = pd.to_numeric(game_log["PTS"], errors="coerce").dropna()
    minutes = pd.to_numeric(game_log.get("MIN", pd.Series(dtype=float)), errors="coerce").dropna()
    season_avg = float(points.mean())
    last_5 = float(points.head(5).mean()) if len(points) >= 5 else season_avg
    last_10 = float(points.head(10).mean()) if len(points) >= 10 else season_avg
    avg_minutes = float(minutes.mean()) if not minutes.empty else projected_minutes
    context = fetch_matchup_context(player_team, opponent_team, season)

    minute_factor = projected_minutes / avg_minutes if avg_minutes > 0 else 1.0
    baseline = (season_avg * 0.45) + (last_5 * 0.35) + (last_10 * 0.20)
    defense_adjustment = (context["def_rating"] - context["league_def_rating"]) * 0.10
    pace_adjustment = (context["pace"] - context["league_pace"]) * (projected_minutes / 48.0) * 0.35
    rest_adjustment = 0.4 if context["rest_days"] >= 2 else -0.4
    home_adjustment = 0.35 if context["is_home"] else -0.15
    projection = max(
        0.0,
        (baseline * minute_factor)
        + defense_adjustment
        + pace_adjustment
        + rest_adjustment
        + home_adjustment,
    )

    return {
        "player_name": player_name,
        "season": season,
        "projection": projection,
        "season_avg": season_avg,
        "last_5": last_5,
        "last_10": last_10,
        "avg_minutes": avg_minutes,
        "projected_minutes": projected_minutes,
        "minute_factor": minute_factor,
        "defense_adjustment": defense_adjustment,
        "pace_adjustment": pace_adjustment,
        "rest_adjustment": rest_adjustment,
        "home_adjustment": home_adjustment,
        "context": context,
    }
