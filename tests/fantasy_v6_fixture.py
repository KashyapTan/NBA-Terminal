"""Explicit synthetic observed team-GP batch; never a live-account observation."""

from copy import deepcopy

from nba_terminal.services import fantasy_nba as nba


def team_bundle(as_of, games=4):
    return {
        "season": "2026-27",
        "rates": [],
        "rates_status": "unavailable",
        "team_games": [{"TEAM_ID": tid, "GP": games} for tid in nba.NBA_TO_ESPN],
        "team_games_status": "fresh",
        "team_games_fetched_at": as_of,
    }


def enrich(snapshot, games=4):
    enriched = deepcopy(snapshot)
    nba.enrich_players(enriched, team_bundle(snapshot["fetched_at"], games))
    for original, resolved in zip(snapshot["free_agents"], enriched["free_agents"], strict=True):
        original["pickup_sample"] = resolved["pickup_sample"]
    return snapshot
