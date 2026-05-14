"""NBA API fetchers used by Qt worker threads."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamshotlocations, leaguedashteamstats
from nba_api.stats.static import teams

STANDARD_ZONES = (
    "Restricted Area",
    "In The Paint (Non-RA)",
    "Mid-Range",
    "Corner 3",
    "Above the Break 3",
)


def fetch_team_defense_stats(season: str) -> list[dict[str, Any]]:
    """Fetch opponent FG percentages and zone defense for every NBA team."""
    nba_teams = teams.get_teams()
    id_to_info = {
        team["id"]: {"abbrev": team["abbreviation"], "name": team["full_name"]}
        for team in nba_teams
    }

    opp_stats = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        measure_type_detailed_defense="Opponent",
        per_mode_detailed="PerGame",
        timeout=60,
    )
    opp_df = opp_stats.get_data_frames()[0]
    time.sleep(0.4)

    shot_locs = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
        season=season,
        per_mode_detailed="PerGame",
        distance_range="By Zone",
        measure_type_simple="Opponent",
        timeout=60,
    )
    zone_df = shot_locs.get_data_frames()[0]

    rows: list[dict[str, Any]] = []
    for _, opp_row in opp_df.iterrows():
        team_id = opp_row["TEAM_ID"]
        if team_id not in id_to_info:
            continue

        zone_stats: dict[str, float] = {}
        zone_row = zone_df[zone_df.iloc[:, 0] == team_id]
        if not zone_row.empty:
            zone_stats = _extract_zone_stats(zone_df, zone_row.iloc[0])

        team_info = id_to_info[team_id]
        rows.append(
            {
                "Team": team_info["abbrev"],
                "Full Name": team_info["name"],
                "OPP_FG_PCT": opp_row["OPP_FG_PCT"],
                "OPP_FG3_PCT": opp_row["OPP_FG3_PCT"],
                "Restricted Area": zone_stats.get("Restricted Area", 0.0),
                "In The Paint (Non-RA)": zone_stats.get("In The Paint (Non-RA)", 0.0),
                "Mid-Range": zone_stats.get("Mid-Range", 0.0),
                "Corner 3": zone_stats.get("Corner 3", 0.0),
                "Above the Break 3": zone_stats.get("Above the Break 3", 0.0),
            }
        )
    return rows


def _extract_zone_stats(zone_df: pd.DataFrame, zone_row: pd.Series) -> dict[str, float]:
    zone_stats: dict[str, float] = {}
    corner_pcts = []
    for column in zone_df.columns:
        if len(column) != 2:
            continue
        zone_name, stat_type = str(column[0]), str(column[1])
        if stat_type != "OPP_FG_PCT" or zone_name in {"", "Backcourt"}:
            continue
        pct = zone_row[column]
        if pd.isna(pct):
            continue
        if "Corner 3" in zone_name and zone_name != "Corner 3":
            corner_pcts.append(float(pct))
        elif zone_name in STANDARD_ZONES:
            zone_stats[zone_name] = float(pct)

    if corner_pcts:
        zone_stats["Corner 3"] = float(np.mean(corner_pcts))
    return zone_stats

