"""NBA game-center queries and normalization for the web API."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv2, scheduleleaguev2, shotchartdetail
from nba_api.stats.static import teams

SUPPORTED_FROM = "1996-97"
PHASES = ("Pre Season", "Regular Season", "Playoffs", "All Star", "Play In", "NBA Cup Final")
GAME_ID_PHASES = {
    "001": "Pre Season",
    "002": "Regular Season",
    "003": "All Star",
    "004": "Playoffs",
    "005": "Play In",
    "006": "NBA Cup Final",
}
GAME_PHASES = (*PHASES, "PlayIn", "NBA Cup")
NBA_SCHEDULE_CDN = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
logger = logging.getLogger(__name__)


def phase_for_game_id(game_id: str) -> str:
    """Read a known NBA game type from its Stats game-ID prefix."""
    return GAME_ID_PHASES.get(str(game_id)[:3], "Phase unavailable")


def current_season(today: date | None = None) -> str:
    """Return the NBA season containing today (seasons roll over in October)."""
    today = today or nba_today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def nba_today() -> date:
    """Return today's date in the Eastern time zone used by NBA schedules."""
    return datetime.now(ZoneInfo("America/New_York")).date()


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
            "logo_url": f"https://cdn.nba.com/logos/nba/{int(team['id'])}/primary/L/logo.svg",
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


def _required_schedule_date(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise RuntimeError("NBA schedule returned a game without a valid Eastern game date.")
    return parsed.strftime("%Y-%m-%d")


def _utc_start_time(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _cdn_schedule_dataframe(season: str) -> pd.DataFrame:
    """Read the current season schedule from the official NBA.com CDN."""
    request = Request(
        NBA_SCHEDULE_CDN,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        },
    )
    with urlopen(request, timeout=8) as response:
        payload = json.load(response)
    schedule = payload.get("leagueSchedule") if isinstance(payload, dict) else None
    season_year = str(schedule.get("seasonYear")) if isinstance(schedule, dict) else ""
    if not isinstance(schedule, dict) or season_year not in {season, season[:4]}:
        raise RuntimeError("NBA CDN schedule did not contain the requested season.")
    game_dates = schedule.get("gameDates")
    if not isinstance(game_dates, list):
        raise RuntimeError("NBA CDN schedule response is missing its game-date list.")
    rows = []
    for date_entry in game_dates:
        if not isinstance(date_entry, dict) or not isinstance(date_entry.get("games"), list):
            raise RuntimeError("NBA CDN schedule contains a malformed game-date entry.")
        for game in date_entry["games"]:
            if not isinstance(game, dict):
                raise RuntimeError("NBA CDN schedule contains a malformed game entry.")
            row = {
                "gameDateEst": game.get("gameDateEst") or date_entry.get("gameDate"),
                "gameDateTimeUTC": game.get("gameDateTimeUTC"),
                "gameId": game.get("gameId"),
                "gameStatus": game.get("gameStatus"),
                "gameStatusText": game.get("gameStatusText"),
            }
            for side in ("home", "away"):
                team = game.get(f"{side}Team")
                if not isinstance(team, dict):
                    raise RuntimeError(f"NBA CDN schedule is missing the {side} team for a game.")
                row.update({
                    f"{side}Team_teamId": team.get("teamId"),
                    f"{side}Team_teamName": team.get("teamName"),
                    f"{side}Team_teamCity": team.get("teamCity"),
                    f"{side}Team_teamTricode": team.get("teamTricode"),
                    f"{side}Team_score": team.get("score"),
                })
            rows.append(row)
    columns = [
        "gameDateEst", "gameDateTimeUTC", "gameId", "gameStatus", "gameStatusText",
        "homeTeam_teamId", "homeTeam_teamName", "homeTeam_teamCity", "homeTeam_teamTricode",
        "homeTeam_score", "awayTeam_teamId", "awayTeam_teamName", "awayTeam_teamCity",
        "awayTeam_teamTricode", "awayTeam_score",
    ]
    return pd.DataFrame(rows, columns=columns)


def _validate_schedule_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Require the fields used by the game feed before accepting a schedule response."""
    required = {
        "gameDateEst", "gameDateTimeUTC", "gameId", "gameStatus", "gameStatusText",
        "homeTeam_teamId", "homeTeam_teamName", "homeTeam_teamCity", "homeTeam_teamTricode",
        "homeTeam_score", "awayTeam_teamId", "awayTeam_teamName", "awayTeam_teamCity",
        "awayTeam_teamTricode", "awayTeam_score",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"NBA schedule response is missing expected fields: {', '.join(missing)}.")
    return frame


def fetch_season_schedule(season: str) -> pd.DataFrame:
    """Fetch the NBA's season schedule, with the official CDN fallback for the current season."""
    if _season_start(season) < 1996:
        return pd.DataFrame()
    return _schedule_dataframe(season, allow_current_cdn_fallback=season == current_season(nba_today()))


def _schedule_dataframe(season: str, *, allow_current_cdn_fallback: bool = False) -> pd.DataFrame:
    """Fetch and validate one season schedule, with an optional official CDN fallback."""
    try:
        endpoint = scheduleleaguev2.ScheduleLeagueV2(season=season, timeout=12)
        return _validate_schedule_dataframe(endpoint.season_games.get_data_frame())
    except Exception:
        if not allow_current_cdn_fallback:
            raise
        logger.warning("NBA Stats schedule failed for %s; trying NBA.com schedule CDN", season, exc_info=True)
        try:
            return _validate_schedule_dataframe(_cdn_schedule_dataframe(season))
        except Exception:
            logger.exception("NBA.com schedule CDN fallback failed for season=%s", season)
            raise


def _schedule_team(row: pd.Series, side: str, lookup: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Normalize a schedule team, including NBA All-Star teams outside the 30-team lookup."""
    prefix = f"{side}Team_"
    raw_id = _serial(row.get(f"{prefix}teamId"))
    try:
        team_id = int(raw_id)
    except (TypeError, ValueError):
        raise RuntimeError(f"NBA schedule returned an invalid {side} team ID.") from None
    if team_id in lookup:
        return lookup[team_id]
    nickname = row.get(f"{prefix}teamName")
    city = row.get(f"{prefix}teamCity")
    abbreviation = row.get(f"{prefix}teamTricode")
    if any(pd.isna(value) or not str(value).strip() for value in (nickname, abbreviation)):
        raise RuntimeError(f"NBA schedule returned incomplete details for the {side} team.")
    name = " ".join(str(value).strip() for value in (city, nickname) if not pd.isna(value) and str(value).strip())
    return {
        "id": team_id,
        "abbreviation": str(abbreviation).strip(),
        "name": name or str(nickname).strip(),
        "nickname": str(nickname).strip(),
        "logo_url": None,
    }


def _schedule_status_id(row: pd.Series) -> int:
    """Read a schedule row's status before normalizing its team details."""
    status = _serial(row.get("gameStatus"))
    try:
        return int(status)
    except (TypeError, ValueError):
        game_id = _serial(row.get("gameId"))
        raise RuntimeError(f"NBA schedule returned an invalid status for game {game_id}.") from None


def _schedule_game(row: pd.Series, lookup: dict[int, dict[str, Any]]) -> dict[str, Any]:
    game_id = _serial(row.get("gameId"))
    if not isinstance(game_id, str) or not game_id.isdigit() or len(game_id) != 10:
        raise RuntimeError("NBA schedule returned a game without a valid 10-digit ID.")
    status_id = _schedule_status_id(row)
    status_text = _serial(row.get("gameStatusText"))
    status_label = str(status_text).strip() if status_text is not None else ""
    return {
        "game_id": game_id,
        "date": _required_schedule_date(row.get("gameDateEst")),
        "start_time": _utc_start_time(row.get("gameDateTimeUTC")),
        "status": status_label or {1: "Scheduled", 2: "In progress", 3: "Final"}.get(status_id, "Status unavailable"),
        "status_id": status_id,
        "phase": phase_for_game_id(game_id),
        "home_team": _schedule_team(row, "home", lookup),
        "away_team": _schedule_team(row, "away", lookup),
        "home_score": _serial(row.get("homeTeam_score")),
        "away_score": _serial(row.get("awayTeam_score")),
    }


def _season_start(season: str) -> int:
    if not isinstance(season, str):
        raise ValueError("Season must use YYYY-YY format.")
    try:
        start, end = season.split("-")
        if len(start) != 4 or len(end) != 2 or int(end) != (int(start) + 1) % 100:
            raise ValueError
        return int(start)
    except (TypeError, ValueError):
        raise ValueError("Season must use YYYY-YY format.") from None


def fetch_upcoming_games(start: date | None = None, schedule_frame: pd.DataFrame | None = None) -> dict[str, Any]:
    """Read all games from today through the next two Eastern league dates."""
    start = start or nba_today()
    lookup = _team_lookup()
    days = [start + timedelta(days=offset) for offset in range(3)]
    day_keys = {day.isoformat() for day in days}
    season = current_season(start)
    frame = schedule_frame if schedule_frame is not None else fetch_season_schedule(season)
    games = [
        _schedule_game(row, lookup) for _, row in frame.iterrows()
        if _required_schedule_date(row.get("gameDateEst")) in day_keys
    ]
    games.sort(key=lambda game: (game["date"], game["start_time"] or "", game["game_id"]))
    return {"games": games, "days": [day.isoformat() for day in days]}


def fetch_recent_games(season: str, schedule_frame: pd.DataFrame | None = None) -> dict[str, Any]:
    """Fetch completed games for every phase in the official season schedule."""
    start_year = _season_start(season)
    if start_year < 1996:
        return {"season": season, "supported": False, "games": [], "phases": list(PHASES)}
    lookup = _team_lookup()
    frame = schedule_frame if schedule_frame is not None else fetch_season_schedule(season)
    games = [
        _schedule_game(row, lookup) for _, row in frame.iterrows()
        if _schedule_status_id(row) == 3
    ]
    games.sort(key=lambda item: (item["date"], item["game_id"]), reverse=True)
    return {"season": season, "supported": True, "games": games[:150], "phases": list(PHASES)}


def _season_from_game_id(game_id: str) -> str:
    season_code = int(game_id[3:5])
    start_year = 1900 + season_code if season_code >= 96 else 2000 + season_code
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _traditional_record(row: pd.Series) -> dict[str, Any]:
    """Normalize provider TO/TOV aliases without turning unknown turnovers into zero."""
    item = {str(key).lower(): _serial(value) for key, value in row.items()}
    item["tov"] = next((item[key] for key in ("tov", "to", "turnovers") if item.get(key) is not None), None)
    return item


def fetch_game_boxscore(game_id: str, season: str | None = None) -> dict[str, Any]:
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
        item = _traditional_record(row)
        team = lookup.get(int(row.get("TEAM_ID", 0)))
        item["team"] = team
        players_out.append(item)
    teams_out = []
    for _, row in team_frame.iterrows():
        item = _traditional_record(row)
        item["team"] = lookup.get(int(row.get("TEAM_ID", 0)))
        teams_out.append(item)
    selected_season = season or _season_from_game_id(game_id)
    if _season_start(selected_season) < 1996:
        raise ValueError(f"Game box scores are supported from {SUPPORTED_FROM} onward.")
    schedule = _schedule_dataframe(
        selected_season,
        allow_current_cdn_fallback=selected_season == current_season(nba_today()),
    )
    match = schedule.loc[schedule["gameId"].astype(str) == game_id]
    away_team = home_team = None
    if not match.empty:
        scheduled_game = _schedule_game(match.iloc[0], lookup)
        away_team = scheduled_game["away_team"]
        home_team = scheduled_game["home_team"]
        side_order = {away_team["id"]: 0, home_team["id"]: 1}
        side_teams = {away_team["id"]: away_team, home_team["id"]: home_team}
        for item in (*players_out, *teams_out):
            if item.get("team_id") in side_teams:
                item["team"] = side_teams[item["team_id"]]
        teams_out.sort(key=lambda item: side_order.get(item.get("team_id"), 2))
    return {
        "game_id": game_id,
        "away_team": away_team,
        "home_team": home_team,
        "players": players_out,
        "teams": teams_out,
    }


def fetch_player_game_analysis(
    game_id: str, player_id: int, season: str, phase: str = "Regular Season"
) -> dict[str, Any]:
    """Return a single player's game line and shot locations when provided."""
    box = fetch_game_boxscore(game_id, season)
    player = next((item for item in box["players"] if item.get("player_id") == player_id), None)
    if player is None:
        raise ValueError("That player does not appear in this game's box score.")
    shots = []
    chart_state = "unavailable"
    try:
        frame = shotchartdetail.ShotChartDetail(
            team_id=0,
            player_id=player_id,
            game_id_nullable=game_id,
            season_nullable=season,
            season_type_all_star=phase,
            context_measure_simple="FGA",
            timeout=12,
        ).get_data_frames()[0]
        required = {"LOC_X", "LOC_Y", "SHOT_MADE_FLAG"}
        if required.issubset(frame.columns):
            for _, row in frame.iterrows():
                x, y = pd.to_numeric(row["LOC_X"], errors="coerce"), pd.to_numeric(row["LOC_Y"], errors="coerce")
                made = pd.to_numeric(row["SHOT_MADE_FLAG"], errors="coerce")
                if pd.isna(x) or pd.isna(y) or pd.isna(made):
                    continue
                period = pd.to_numeric(row.get("PERIOD"), errors="coerce")
                minutes_remaining = pd.to_numeric(row.get("MINUTES_REMAINING"), errors="coerce")
                seconds_remaining = pd.to_numeric(row.get("SECONDS_REMAINING"), errors="coerce")
                shots.append(
                    {
                        "x": float(x),
                        "y": float(y),
                        "made": bool(int(made)),
                        "description": str(row.get("ACTION_TYPE", "")),
                        "period": int(period) if not pd.isna(period) else None,
                        "distance": _serial(row.get("SHOT_DISTANCE")),
                        "event_type": _serial(row.get("EVENT_TYPE")),
                        "shot_type": _serial(row.get("SHOT_TYPE")),
                        "minutes_remaining": int(minutes_remaining) if not pd.isna(minutes_remaining) else None,
                        "seconds_remaining": int(seconds_remaining) if not pd.isna(seconds_remaining) else None,
                        "zone": _serial(row.get("SHOT_ZONE_BASIC")),
                    }
                )
            chart_state = "available" if shots else "unavailable"
    except Exception:
        # Some game/season combinations do not expose shot locations. Box score remains useful.
        chart_state = "error"
    player_team_id = player.get("team_id")
    team_rows = box.get("teams", [])
    player_team_row = next((item for item in team_rows if item.get("team_id") == player_team_id), {})
    opponent_team_row = next((item for item in team_rows if item.get("team_id") != player_team_id), {})
    opponent_team = next(
        (
            item.get("team")
            for item in box["players"]
            if item.get("team_id") != player_team_id and item.get("team") is not None
        ),
        None,
    )
    return {
        "game_id": game_id,
        "player": player,
        "stats": player,
        "shots": shots,
        "shot_chart_state": chart_state,
        "game_context": {
            "game_id": game_id,
            "team": player.get("team"),
            "opponent": opponent_team,
            "team_score": player_team_row.get("pts"),
            "opponent_score": opponent_team_row.get("pts"),
            "season": season,
            "phase": phase,
        },
    }
