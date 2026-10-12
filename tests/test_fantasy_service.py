"""Tests for batched Fantasy season data normalization."""

import math

import pandas as pd
import pytest

from nba_terminal.services import fantasy


def row(**overrides):
    base = {
        "PLAYER_ID": 7,
        "PLAYER_NAME": "Sample Player",
        "TEAM_ID": 2,
        "TEAM_ABBREVIATION": "BOS",
        "GP": 10,
        "MIN": 300.0,
        "PTS": 250,
        "REB": 70,
        "AST": 50,
        "STL": 10,
        "BLK": 5,
        "TOV": 20,
        "FG3M": 30,
        "FG3A": 80,
        "FGM": 90,
        "FGA": 180,
        "FTM": 40,
        "FTA": 50,
    }
    return {**base, **overrides}


def test_season_start_year_validates_shape_and_adjacent_year():
    assert fantasy.season_start_year("2025-26") == 2025
    for value in ("2025/26", "2025-27", "25-26", None):
        with pytest.raises(ValueError, match="YYYY-YY"):
            fantasy.season_start_year(value)


def test_normalize_player_rows_sorts_skips_invalid_and_preserves_missing():
    frame = pd.DataFrame(
        [
            row(PLAYER_ID=2, PLAYER_NAME="Zed", PTS=float("nan"), FGA=None),
            row(PLAYER_ID=1, PLAYER_NAME="Amy", TEAM_ID=float("nan")),
            row(PLAYER_ID=None, PLAYER_NAME="No ID"),
            row(PLAYER_ID=8, PLAYER_NAME="  "),
            row(PLAYER_ID=9, PLAYER_NAME=float("nan")),
        ]
    )

    players = fantasy.normalize_player_rows(frame)

    assert [player["player_name"] for player in players] == ["Amy", "Zed"]
    assert players[0]["team_id"] is None
    assert players[1]["points"] is None
    assert players[1]["field_goal_attempts"] is None
    assert players[1]["threes_made"] == 30


def test_normalize_player_rows_handles_empty_or_drifted_schema():
    assert fantasy.normalize_player_rows(pd.DataFrame()) == []
    with pytest.raises(RuntimeError, match="unsupported schema"):
        fantasy.normalize_player_rows(pd.DataFrame({"PTS": [20]}))


def test_player_with_tot_row_prefers_the_full_season_total():
    frame = pd.DataFrame(
        [
            row(TEAM_ABBREVIATION="BOS", GP=4, PTS=100),
            row(TEAM_ABBREVIATION="TOT", TEAM_ID=None, GP=10, PTS=250),
        ]
    )

    players = fantasy.normalize_player_rows(frame)

    assert len(players) == 1
    assert players[0]["games"] == 10
    assert players[0]["points"] == 250
    assert players[0]["team_abbreviation"] == "TOT"


def test_player_without_tot_row_combines_team_splits():
    frame = pd.DataFrame(
        [
            row(TEAM_ABBREVIATION="BOS", TEAM_ID=2, GP=4, PTS=100, MIN=120, FG3M=12),
            row(TEAM_ABBREVIATION="NYK", TEAM_ID=3, GP=6, PTS=150, MIN=180, FG3M=18, FTA=None),
        ]
    )

    players = fantasy.normalize_player_rows(frame)

    assert players[0]["games"] == 10
    assert players[0]["points"] == 250
    assert players[0]["minutes_total"] == 300
    assert players[0]["threes_made"] == 30
    assert players[0]["free_throw_attempts"] is None
    assert players[0]["team_abbreviation"] == "2TM"
    assert players[0]["team_id"] is None


def test_normalize_rejects_non_finite_numeric_cells():
    assert fantasy._number(math.inf) is None
    assert fantasy._number("not a number") is None
    assert fantasy._number("12.5") == 12.5


def test_fetch_fantasy_season_uses_one_totals_request_and_enriches_team(monkeypatch):
    calls = []

    class Endpoint:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def get_data_frames(self):
            return [pd.DataFrame([row()])]

    monkeypatch.setattr(fantasy.leaguedashplayerstats, "LeagueDashPlayerStats", Endpoint)
    monkeypatch.setattr(
        fantasy.teams,
        "get_teams",
        lambda: [{"abbreviation": "BOS", "full_name": "Boston Celtics"}],
    )

    result = fantasy.fetch_fantasy_season("2025-26")

    assert calls == [
        {
            "season": "2025-26",
            "season_type_all_star": "Regular Season",
            "per_mode_detailed": "Totals",
            "timeout": 12,
        }
    ]
    assert result["supported"] is True
    assert result["phase"] == "Regular Season"
    assert result["players"][0]["team_name"] == "Boston Celtics"


def test_fetch_fantasy_season_marks_unsupported_year_without_calling_api(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError(f"unexpected endpoint request: {kwargs}")

    monkeypatch.setattr(fantasy.leaguedashplayerstats, "LeagueDashPlayerStats", fail_if_called)

    assert fantasy.fetch_fantasy_season("1945-46") == {
        "season": "1945-46",
        "supported": False,
        "phase": "Regular Season",
        "players": [],
    }
