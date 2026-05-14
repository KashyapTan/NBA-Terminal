"""Offline nba_api endpoint metadata catalog."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any

from nba_api.stats import endpoints

CATEGORY_ORDER = [
    "All",
    "Box Score",
    "Play By Play & Rotation",
    "Player Dashboards",
    "Team Dashboards",
    "Player Tracking (Pt)",
    "Team Tracking (Pt)",
    "League Tracking (Pt)",
    "Shot Charts & Locations",
    "Lineups & On/Off",
    "Matchups & Comparisons",
    "Game Logs & Finders",
    "Schedule & Standings",
    "Leaders & Highlights",
    "Hustle & Defense",
    "Estimated Metrics",
    "Cumulative Stats",
    "Synergy & Play Types",
    "Bio & Profiles",
    "Franchise & History",
    "Draft & Combine",
    "Fantasy",
    "Video",
    "Misc",
]


@dataclass(frozen=True)
class EndpointInfo:
    name: str
    category: str
    datasets: dict[str, list[str]]
    dataset_count: int
    column_count: int
    search_blob: str


def categorize_endpoint(name: str) -> str:
    """Place an nba_api endpoint into a terminal catalog group."""
    if name.startswith("BoxScore"):
        return "Box Score"
    if name in {"PlayByPlay", "PlayByPlayV2", "PlayByPlayV3", "WinProbabilityPBP", "GameRotation"}:
        return "Play By Play & Rotation"
    if name.startswith("PlayerDashboard"):
        return "Player Dashboards"
    if name.startswith("TeamDashboard"):
        return "Team Dashboards"
    if name.startswith("PlayerDashPt"):
        return "Player Tracking (Pt)"
    if name.startswith("TeamDashPt"):
        return "Team Tracking (Pt)"
    if name.startswith("LeagueDashPt"):
        return "League Tracking (Pt)"
    if "ShotChart" in name or "ShotLocations" in name:
        return "Shot Charts & Locations"
    if name in {
        "LeagueDashLineups",
        "TeamDashLineups",
        "LeagueLineupViz",
        "TeamPlayerOnOffSummary",
        "TeamPlayerOnOffDetails",
        "LeaguePlayerOnDetails",
    }:
        return "Lineups & On/Off"
    if name in {"PlayerVsPlayer", "TeamVsPlayer", "TeamAndPlayersVsPlayers", "PlayerCompare", "MatchupsRollup"}:
        return "Matchups & Comparisons"
    if "GameLog" in name or name.endswith("GameLog") or "GameFinder" in name or "GameStreakFinder" in name:
        return "Game Logs & Finders"
    if name in {
        "ScoreboardV2",
        "ScheduleLeagueV2",
        "LeagueStandings",
        "LeagueStandingsV3",
        "PlayoffPicture",
        "ISTStandings",
        "CommonPlayoffSeries",
        "PlayerNextNGames",
    }:
        return "Schedule & Standings"
    if name in {
        "LeagueLeaders",
        "HomePageLeaders",
        "HomePageV2",
        "AllTimeLeadersGrids",
        "LeadersTiles",
        "AssistLeaders",
        "AssistTracker",
    }:
        return "Leaders & Highlights"
    if "Hustle" in name or "Defense" in name or "Defend" in name:
        return "Hustle & Defense"
    if name in {"PlayerEstimatedMetrics", "TeamEstimatedMetrics"}:
        return "Estimated Metrics"
    if name in {"CumeStatsPlayer", "CumeStatsTeam", "CumeStatsPlayerGames", "CumeStatsTeamGames"}:
        return "Cumulative Stats"
    if name == "SynergyPlayTypes":
        return "Synergy & Play Types"
    if name in {
        "CommonPlayerInfo",
        "PlayerProfileV2",
        "PlayerCareerStats",
        "PlayerAwards",
        "PlayerIndex",
        "CommonAllPlayers",
        "CommonTeamRoster",
        "CommonTeamYears",
        "TeamInfoCommon",
        "TeamDetails",
        "TeamYearByYearStats",
        "TeamHistoricalLeaders",
        "TeamPlayerDashboard",
    }:
        return "Bio & Profiles"
    if name.startswith("Franchise"):
        return "Franchise & History"
    if name.startswith("Draft"):
        return "Draft & Combine"
    if "Fantasy" in name or "FanDuel" in name:
        return "Fantasy"
    if name.startswith("Video"):
        return "Video"
    return "Misc"


def stringify_value(value: Any) -> str:
    """Stringify endpoint metadata values for display/search."""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def normalize_expected_data(expected_data: dict[str, Any]) -> dict[str, list[str]]:
    """Normalize endpoint expected_data into dataset-to-column rows."""
    datasets = {}
    for dataset_name, dataset_value in expected_data.items():
        if isinstance(dataset_value, list):
            columns = [item if isinstance(item, str) else stringify_value(item) for item in dataset_value]
        elif isinstance(dataset_value, dict):
            columns = [f"{key}: {stringify_value(value)}" for key, value in dataset_value.items()]
        else:
            columns = [stringify_value(dataset_value)]
        datasets[dataset_name] = columns
    return datasets


def build_endpoint_infos() -> list[EndpointInfo]:
    """Build searchable endpoint metadata without making NBA network calls."""
    infos = []
    for name in sorted(dir(endpoints)):
        obj = getattr(endpoints, name)
        if not inspect.isclass(obj):
            continue
        expected_data = getattr(obj, "expected_data", None)
        if not isinstance(expected_data, dict):
            continue
        datasets = normalize_expected_data(expected_data)
        category = categorize_endpoint(name)
        search_parts = [name, category, *datasets.keys()]
        for columns in datasets.values():
            search_parts.extend(columns)
        infos.append(
            EndpointInfo(
                name=name,
                category=category,
                datasets=datasets,
                dataset_count=len(datasets),
                column_count=sum(len(columns) for columns in datasets.values()),
                search_blob=" ".join(search_parts).lower(),
            )
        )
    return infos
