"""Browser-facing retained analyses, with batched resources and explicit missing data.

No NBA I/O occurs until a worker invokes a service method. Existing Qt services
remain intact; these adapters preserve their formulas without their silent defaults.
"""

from __future__ import annotations

import inspect
import logging
import math
import threading
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from nba_api.stats import endpoints
from nba_api.stats.endpoints import (
    commonteamroster,
    leaguedashplayerstats,
    leaguedashteamshotlocations,
    leaguedashteamstats,
    playergamelogs,
)
from nba_api.stats.static import players, teams

from nba_terminal.analytics import consistency_label, defense_rank_tier
from nba_terminal.services import game_center
from nba_terminal.services.api_catalog import build_endpoint_infos
from nba_terminal.services.picks import DEFAULT_PICKS_DIR, list_pick_files

logger = logging.getLogger(__name__)

STATS = ("PTS", "REB", "AST", "STL", "BLK")
ZONES = ("Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3")
DEFENSE = ("OPP_FG_PCT", "OPP_FG3_PCT", *ZONES)


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def checked_frame(frame: pd.DataFrame, required: set[str]) -> pd.DataFrame:
    """Fail explicitly for identity/qualification schema loss; optional metrics stay null."""
    if not frame.empty and not required <= set(frame.columns):
        raise ValueError(f"NBA resource schema missing {sorted(required - set(frame.columns))}")
    return frame


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return (
        pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce")
        .replace([float("inf"), -float("inf")], float("nan"))
        .dropna()
    )


def ordered_logs(frame: pd.DataFrame, before: str | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame
    if "GAME_DATE" not in frame:
        raise ValueError("Game log schema missing GAME_DATE; chronology unavailable.")
    result = frame.copy()
    result["GAME_DATE"] = pd.to_datetime(result["GAME_DATE"], errors="coerce", utc=True)
    result = result.dropna(subset=["GAME_DATE"])
    if before:
        result = result[result["GAME_DATE"] < pd.Timestamp(before, tz="UTC")]
    result = result.sort_values("GAME_DATE", ascending=False)
    if {"PLAYER_ID", "GAME_ID"} <= set(result.columns):
        result = result.drop_duplicates(["PLAYER_ID", "GAME_ID"])
    return result


def points_projection(logs: pd.DataFrame, minutes: float, context: dict[str, Any]) -> dict[str, Any]:
    """Original .45/.35/.20 predictor; incomplete context cannot produce a total."""
    points = numeric(logs, "PTS")
    if points.empty:
        raise ValueError("No valid historical points for this player/season/date.")
    season_avg = float(points.mean())
    l5 = float(points.head(5).mean()) if len(points) >= 5 else season_avg
    l10 = float(points.head(10).mean()) if len(points) >= 10 else season_avg
    baseline = 0.45 * season_avg + 0.35 * l5 + 0.20 * l10
    avg_min = number(numeric(logs, "MIN").mean())
    factor = minutes / avg_min if avg_min and avg_min > 0 else 1.0
    defense = (
        None
        if any(context.get(k) is None for k in ("def_rating", "league_def_rating"))
        else (0.10 * (context["def_rating"] - context["league_def_rating"]))
    )
    pace = (
        None
        if any(context.get(k) is None for k in ("pace", "league_pace"))
        else (0.35 * (context["pace"] - context["league_pace"]) * minutes / 48)
    )
    rest = None if context.get("rest_days") is None else (0.4 if context["rest_days"] >= 2 else -0.4)
    home = None if context.get("is_home") is None else (0.35 if context["is_home"] else -0.15)
    adjustments = [defense, pace, rest, home]
    return {
        "season_avg": season_avg,
        "last_5": l5,
        "last_10": l10,
        "valid_games": len(points),
        "avg_minutes": avg_min,
        "projected_minutes": minutes,
        "minute_factor": factor,
        "baseline": baseline,
        "minutes_adjustment": baseline * (factor - 1),
        "defense_adjustment": defense,
        "pace_adjustment": pace,
        "rest_adjustment": rest,
        "home_adjustment": home,
        "projection": max(0.0, baseline * factor + sum(adjustments)) if None not in adjustments else None,
        "minutes_estimated": avg_min is None or avg_min <= 0,
        "last_5_fallback": len(points) < 5,
        "last_10_fallback": len(points) < 10,
    }


def consistency_rows(roster: pd.DataFrame, logs: pd.DataFrame, stat: str, window: int) -> dict[str, Any]:
    """Window first, null removal second, sample SD; exclude mean<=0/SD<=0."""
    rows = []
    excluded = {"insufficient_games": 0, "missing_stat": 0, "zero_mean_or_sd": 0}
    for _, player in roster.iterrows():
        recent = logs[logs["PLAYER_ID"] == player["PLAYER_ID"]].head(window)
        if len(recent) < window:
            excluded["insufficient_games"] += 1
            continue
        values = numeric(recent, stat)
        if values.empty:
            excluded["missing_stat"] += 1
            continue
        mean = float(values.mean())
        sd = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        if mean <= 0 or sd <= 0:
            excluded["zero_mean_or_sd"] += 1
            continue
        cv = sd / mean
        tier, color = consistency_label(cv)
        rows.append(
            {
                "player_id": int(player["PLAYER_ID"]),
                "player": str(player["PLAYER"]),
                "mean": mean,
                "sd": sd,
                "cv": cv,
                "window": window,
                "valid_games": len(values),
                "tier": tier,
                "color": color,
            }
        )
    rows.sort(key=lambda row: row["cv"])
    return {
        "rows": [{**row, "rank": i + 1} for i, row in enumerate(rows[:15])],
        "ranked_players": len(rows),
        "roster_players": len(roster),
        "excluded": excluded,
    }


def defense_rows(overall: pd.DataFrame, zones: pd.DataFrame) -> dict[str, Any]:
    """Handle both provider FG_PCT and retained OPP_FG_PCT MultiIndex schemas."""
    by_team = {}
    id_column = next(
        (c for c in zones.columns if (isinstance(c, tuple) and c[-1] == "TEAM_ID") or c == "TEAM_ID"), None
    )
    if id_column is not None:
        for _, row in zones.iterrows():
            values = {}
            corners = []
            for col in zones.columns:
                if not isinstance(col, tuple) or len(col) != 2 or col[1] not in {"FG_PCT", "OPP_FG_PCT"}:
                    continue
                value = number(row[col])
                attempts = next(
                    (
                        row[c]
                        for c in zones.columns
                        if isinstance(c, tuple) and c[0] == col[0] and c[1] in {"FGA", "OPP_FGA"}
                    ),
                    None,
                )
                if number(attempts) == 0:
                    value = None
                if col[0] in {"Left Corner 3", "Right Corner 3"}:
                    corners.append(value)
                elif col[0] in ZONES:
                    values[col[0]] = value
            if corners:
                # Both sides are required: a missing side is unknown, not a zero or one-sided average.
                values["Corner 3"] = sum(corners) / 2 if len(corners) == 2 and None not in corners else None
            by_team[int(row[id_column])] = values
    rows = []
    for _, row in overall.iterrows():
        team_id = int(row["TEAM_ID"])
        info = teams.find_team_name_by_id(team_id)
        rows.append(
            {
                "team_id": team_id,
                "team": info["abbreviation"] if info else str(row.get("TEAM_NAME", team_id)),
                **{k: number(row.get(k)) for k in DEFENSE[:2]},
                **{k: by_team.get(team_id, {}).get(k) for k in ZONES},
            }
        )
    rows.sort(key=lambda row: (row["OPP_FG_PCT"] is None, row["OPP_FG_PCT"] or 0))
    rank = 0
    for row in rows:
        if row["OPP_FG_PCT"] is None:
            row.update(rank=None, tier="Unknown", color="muted")
        else:
            rank += 1
            tier, color = defense_rank_tier(rank)
            row.update(rank=rank, tier=tier, color=color)
    means = {}
    counts = {}
    for key in DEFENSE:
        values = [r[key] for r in rows if r[key] is not None]
        means[key] = sum(values) / len(values) if values else None
        counts[key] = len(values)
    return {
        "rows": rows,
        "league_means": means,
        "league_counts": counts,
        "missing_zone_teams": sum(any(row[k] is None for k in ZONES) for row in rows),
    }


def slate_rows(dashboard: pd.DataFrame, logs: pd.DataFrame, games: list[dict]) -> dict[str, Any]:
    lookup = {}
    for game in games:
        home, away = game["home_team"], game["away_team"]
        lookup[home["id"]] = (home["abbreviation"], away["abbreviation"], True)
        lookup[away["id"]] = (away["abbreviation"], home["abbreviation"], False)
    rows = []
    qualified = missing = insufficient = 0
    for _, player in dashboard.iterrows():
        team_id = int(player["TEAM_ID"])
        minutes, gp, season_avg = (number(player.get(k)) for k in ("MIN", "GP", "PTS"))
        if team_id not in lookup or minutes is None or minutes < 25 or gp is None or gp < 5:
            continue
        qualified += 1
        history = logs[logs["PLAYER_ID"] == player["PLAYER_ID"]] if "PLAYER_ID" in logs else pd.DataFrame()
        points = numeric(history, "PTS")
        if history.empty or season_avg is None or points.empty:
            missing += 1
            continue
        if len(history) < 5:
            insufficient += 1
            continue
        l5 = float(points.head(5).mean())
        l10 = float(points.head(10).mean()) if len(points) >= 10 else l5
        projection = 0.60 * l5 + 0.25 * l10 + 0.15 * season_avg
        diff = projection - season_avg
        if abs(diff) < 3:
            continue
        team, opponent, home = lookup[team_id]
        rows.append(
            {
                "player": str(player["PLAYER_NAME"]),
                "player_id": int(player["PLAYER_ID"]),
                "team": team,
                "opponent": opponent,
                "is_home": home,
                "season_avg": season_avg,
                "last_5": l5,
                "last_10": l10,
                "projection": projection,
                "difference": diff,
                "direction": "Above season" if diff > 0 else "Below season",
                "minutes": minutes,
                "season_games": int(gp),
                "valid_games": len(points),
                "recent_valid_games": min(5, len(points)),
            }
        )
    rows.sort(key=lambda row: abs(row["difference"]), reverse=True)
    return {
        "rows": rows,
        "qualified_players": qualified,
        "missing_players": missing,
        "insufficient_players": insufficient,
        "evaluated_players": qualified - missing - insufficient,
    }


class LegacyToolsService:
    """Small successful-resource cache plus failure cooldown, used only in bounded workers."""

    def __init__(self, picks_dir: Path = DEFAULT_PICKS_DIR):
        self.picks_dir = picks_dir
        self._cache: dict[tuple, tuple[float, Any, str, str | None]] = {}
        self._lock = threading.Lock()

    def _resource(self, key: tuple, fetch: Callable, ttl: int = 900) -> tuple[Any, str, str | None]:
        # One lock deduplicates cold resources across distinct tool requests. No per-player I/O.
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1:]
            fetched = datetime.now(timezone.utc).isoformat()
            try:
                value = fetch()
                error = None
            except Exception as exc:
                logger.warning("Legacy tools resource failed: %s (%s)", key, type(exc).__name__)
                value = pd.DataFrame()
                error = f"{key[0]} unavailable ({type(exc).__name__}); retry shortly."
            self._cache[key] = (time.monotonic() + (30 if error else ttl), value, fetched, error)
            if len(self._cache) > 64:
                self._cache.pop(next(iter(self._cache)))
            return value, fetched, error

    def _frame(self, name: str, season: str, phase: str, before: str = "", team: int = 0) -> tuple:
        def fetch():
            date_to = (date.fromisoformat(before) - timedelta(days=1)).isoformat() if before else ""
            common = {"season": season, "season_type_all_star": phase, "timeout": 12}
            if name == "logs":
                frame = playergamelogs.PlayerGameLogs(
                    season_nullable=season,
                    season_type_nullable=phase,
                    date_to_nullable=date_to,
                    timeout=12,
                ).get_data_frames()[0]
                required = {"PLAYER_ID", "GAME_DATE"}
                if not frame.empty and not required <= set(frame.columns):
                    raise ValueError("Game log schema changed")
                return ordered_logs(frame, before or None)
            if name == "players":
                return checked_frame(
                    leaguedashplayerstats.LeagueDashPlayerStats(
                        **common,
                        per_mode_detailed="PerGame",
                        date_to_nullable=date_to,
                    ).get_data_frames()[0],
                    {"PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP", "PTS"},
                )
            if name == "roster":
                return checked_frame(
                    commonteamroster.CommonTeamRoster(team_id=team, season=season, timeout=12).get_data_frames()[0],
                    {"PLAYER_ID", "PLAYER"},
                )
            if name == "zones":
                return leaguedashteamshotlocations.LeagueDashTeamShotLocations(
                    **common,
                    measure_type_simple="Opponent",
                    distance_range="By Zone",
                    per_mode_detailed="PerGame",
                ).get_data_frames()[0]
            return leaguedashteamstats.LeagueDashTeamStats(
                **common,
                measure_type_detailed_defense="Advanced" if name == "advanced" else "Opponent",
                per_mode_detailed="PerGame",
                date_to_nullable=date_to,
            ).get_data_frames()[0]

        return self._resource((name, season, phase, before, team), fetch)

    @staticmethod
    def _result(resources: dict[str, tuple]) -> dict:
        errors = [r[2] for r in resources.values() if r[2]]
        return {
            "state": "partial" if errors else "ready",
            "errors": errors,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "resources": {
                name: {"fetched_at": r[1], "state": "error" if r[2] else "ready"} for name, r in resources.items()
            },
            "cache_ttl_seconds": 900,
        }

    def meta(self) -> dict:
        today = game_center.nba_today()
        return {
            "today": today.isoformat(),
            "season": game_center.current_season(today),
            "teams": teams.get_teams(),
            "players": players.get_players(),
            **self._result({}),
        }

    def consistency(self, season: str, phase: str, team_id: int, stat: str, window: int) -> dict:
        resources = {
            "roster": self._frame("roster", season, phase, team=team_id),
            "logs": self._frame("logs", season, phase),
        }
        result = self._result(resources)
        if any(r[0].empty for r in resources.values()):
            return {**result, "state": "error" if result["errors"] else "empty", "rows": []}
        return {**result, **consistency_rows(resources["roster"][0], resources["logs"][0], stat, window)}

    def defense(self, season: str, phase: str) -> dict:
        resources = {"overall": self._frame("overall", season, phase), "zones": self._frame("zones", season, phase)}
        result = {**self._result(resources), **defense_rows(resources["overall"][0], resources["zones"][0])}
        if not result["rows"]:
            result["state"] = "error" if result["errors"] else "empty"
        elif any(row[key] is None for row in result["rows"] for key in DEFENSE):
            result["state"] = "partial"
        return result

    def _schedule(self, season: str) -> tuple:
        return self._resource(("schedule", season), lambda: game_center.fetch_season_schedule(season), ttl=120)

    @staticmethod
    def _games(frame: pd.DataFrame, day: str, phase: str | None = None) -> list[dict]:
        if frame.empty:
            return []
        dates = pd.to_datetime(frame["gameDateEst"], errors="coerce").dt.strftime("%Y-%m-%d")
        lookup = {t["id"]: t for t in teams.get_teams()}
        games = []
        for _, row in frame[dates == day].iterrows():
            if phase and game_center.phase_for_game_id(str(row["gameId"])) != phase:
                continue
            home = lookup.get(int(row["homeTeam_teamId"]))
            away = lookup.get(int(row["awayTeam_teamId"]))
            if home and away:
                games.append(
                    {
                        "game_id": str(row["gameId"]),
                        "date": day,
                        "home_team": home,
                        "away_team": away,
                        "status": str(row.get("gameStatusText", "")),
                    }
                )
        return games

    def slate(self, season: str, phase: str, day: str) -> dict:
        resources = {"schedule": self._schedule(season)}
        games = self._games(resources["schedule"][0], day, phase)
        if not games:
            return {
                **self._result(resources),
                "state": "error" if resources["schedule"][2] else "empty",
                "games": [],
                "rows": [],
                "date": day,
                "season": season,
            }
        resources.update(
            players=self._frame("players", season, phase, day), logs=self._frame("logs", season, phase, day)
        )
        result = self._result(resources)
        if resources["players"][0].empty:
            return {
                **result,
                "state": "error" if result["errors"] else "empty",
                "games": games,
                "rows": [],
                "date": day,
                "season": season,
            }
        rows = slate_rows(resources["players"][0], resources["logs"][0], games)
        return {
            **result,
            **rows,
            "state": "partial" if rows["missing_players"] else result["state"],
            "games": games,
            "date": day,
            "season": season,
        }

    def predictor(
        self,
        season: str,
        phase: str,
        player_id: int,
        team_id: int,
        opponent_id: int,
        minutes: float,
        day: str,
        overrides: dict,
    ) -> dict:
        resources = {
            "logs": self._frame("logs", season, phase, day),
            "advanced": self._frame("advanced", season, phase, day),
            "schedule": self._schedule(season),
        }
        logs = resources["logs"][0]
        if logs.empty:
            return {
                **self._result(resources),
                "state": "error" if resources["logs"][2] else "empty",
                "projection": None,
            }
        history = logs[logs["PLAYER_ID"] == player_id]
        advanced = resources["advanced"][0]
        context = {
            key: None for key in ("def_rating", "league_def_rating", "pace", "league_pace", "rest_days", "is_home")
        }
        sources = dict.fromkeys(context, "unavailable")
        if not advanced.empty and "TEAM_ID" in advanced:
            opponent = advanced[advanced["TEAM_ID"] == opponent_id]
            for col, key in (("DEF_RATING", "def_rating"), ("PACE", "pace")):
                context[f"league_{key}"] = number(numeric(advanced, col).mean())
                context[key] = number(opponent.iloc[0].get(col)) if not opponent.empty else None
        for game in self._games(resources["schedule"][0], day):
            if {team_id, opponent_id} == {game["home_team"]["id"], game["away_team"]["id"]}:
                context["is_home"] = game["home_team"]["id"] == team_id
        # Rest comes from team's completed games before selected date, not player's last appearance.
        team_history = logs[logs.get("TEAM_ID", pd.Series(index=logs.index, dtype=float)) == team_id]
        if not team_history.empty:
            gap = (date.fromisoformat(day) - team_history.iloc[0]["GAME_DATE"].date()).days - 1
            context["rest_days"] = max(0, min(5, gap))
        for key, value in context.items():
            if value is not None:
                sources[key] = "NBA returned sample" if key != "is_home" else "NBA schedule"
        for key, value in overrides.items():
            if value is not None:
                context[key] = value
                sources[key] = "User estimate override"
        projection = points_projection(history, minutes, context)
        missing = [k for k, v in context.items() if v is None]
        return {
            **self._result(resources),
            **projection,
            "context": context,
            "context_sources": sources,
            "missing_context": missing,
            "state": "partial" if missing or any(r[2] for r in resources.values()) else "ready",
            "date": day,
            "season": season,
        }

    def picks(self, query: str, filename: str | None) -> dict:
        root = self.picks_dir.resolve()
        files = [p for p in list_pick_files(root) if not p.is_symlink() and p.resolve().parent == root]
        if filename is not None:
            selected = next((p for p in files if p.name == filename), None)
            if selected is None:
                raise ValueError("Pick file not found in read-only archive.")
            return {
                **self._result({}),
                "filename": selected.name,
                "content": selected.read_text(encoding="utf-8", errors="replace"),
            }
        matches = []
        for path in files:
            content = path.read_text(encoding="utf-8", errors="replace")
            if query.casefold() in (path.name + "\n" + content).casefold():
                matches.append({"filename": path.name, "preview": content[:160]})
        return {**self._result({}), "files": matches, "read_only": True}

    def catalog(self, query: str) -> dict:
        def build():
            rows = []
            for info in build_endpoint_infos():
                obj = getattr(endpoints, info.name)
                parameters = {
                    k: ("required" if v.default is inspect.Parameter.empty else str(v.default))
                    for k, v in inspect.signature(obj).parameters.items()
                }
                rows.append({**asdict(info), "parameters": parameters})
            return rows

        rows, fetched, error = self._resource(("catalog",), build, ttl=3600)
        return {
            **self._result({"catalog": (rows, fetched, error)}),
            "version": version("nba_api"),
            "endpoints": [
                r
                for r in ([] if error else rows)
                if query.casefold() in (r["search_blob"] + str(r["parameters"]).lower())
            ],
            "metadata_only": True,
        }
