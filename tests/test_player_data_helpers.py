import pandas as pd
import pytest

from nba_terminal.services import player_data
from nba_terminal.services.player_data import add_derived_columns, profile_hit_rate_rows, summarize_profile_game_stats


def test_player_profile_derived_columns_and_summaries():
    frame = pd.DataFrame(
        [
            {
                "PTS": 20,
                "REB": 8,
                "AST": 7,
                "STL": 2,
                "BLK": 1,
                "FGM": 7,
                "FGA": 10,
                "FG3M": 2,
                "FG3A": 5,
                "FTA": 5,
                "PLUS_MINUS": 4,
            },
            {
                "PTS": 10,
                "REB": 4,
                "AST": 3,
                "STL": 1,
                "BLK": 0,
                "FGM": 4,
                "FGA": 8,
                "FG3M": 1,
                "FG3A": 4,
                "FTA": 2,
                "PLUS_MINUS": -2,
            },
        ]
    )

    enriched = add_derived_columns(frame)
    assert enriched.loc[0, "PRA"] == 35
    assert enriched.loc[0, "STOCKS"] == 3
    assert enriched.loc[0, "EFG_PCT"] == pytest.approx(0.8)
    assert enriched.loc[0, "FG3A_RATE"] == pytest.approx(0.5)
    assert enriched.loc[0, "FTA_RATE"] == pytest.approx(0.5)
    assert enriched.loc[0, "TS_PCT"] == pytest.approx(20 / 24.4)

    summaries = {row["column"]: row for row in summarize_profile_game_stats(enriched)}
    assert summaries["PTS"]["avg"] == 15
    assert summaries["PRA"]["avg"] == 26
    assert summaries["PTS"]["last_5"] == 15
    assert summaries["EFG_PCT"]["type"] == "pct"


def test_player_profile_hit_rate_rows_include_combo_markets():
    enriched = add_derived_columns(
        pd.DataFrame(
            [
                {"PTS": 20, "REB": 8, "AST": 7, "FG3M": 3, "FGA": 10, "FTA": 5},
                {"PTS": 10, "REB": 4, "AST": 3, "FG3M": 1, "FGA": 8, "FTA": 2},
            ]
        )
    )

    rates = {row["market"]: row for row in profile_hit_rate_rows(enriched)}
    assert rates["PTS 10+"]["season"] == 100
    assert rates["PTS 20+"]["season"] == 50
    assert rates["PRA 20+"]["season"] == 50
    assert rates["3PM 2+"]["season"] == 50


def test_player_profile_cache_round_trip_and_clear(monkeypatch, tmp_path):
    monkeypatch.setenv("NBA_TERMINAL_CACHE_DIR", str(tmp_path))
    profile = {
        "player": "Test Player",
        "player_id": 1,
        "team": "TST",
        "season": "2025-26",
        "season_type": "Regular Season",
        "cache_hit": False,
        "game_log": pd.DataFrame(
            [
                {
                    "GAME_DATE": pd.Timestamp("2026-01-02"),
                    "PTS": 20,
                    "REB": 8,
                }
            ]
        ),
        "measures": {"Base": {"PTS": 20.0}},
        "game_summary": [{"column": "PTS", "avg": 20.0}],
        "hit_rate_rows": [{"market": "PTS 20+", "season": 100.0}],
        "shooting_splits": {"Overall": [{"FGM": 8}]},
        "warnings": [],
    }

    player_data._write_player_profile_cache(1, "2025-26", "Regular Season", profile)
    cached = player_data._load_player_profile_cache(1, "2025-26", "Regular Season")

    assert cached is not None
    assert cached["player"] == "Test Player"
    assert cached["cache_hit"] is False
    assert cached["game_log"].loc[0, "PTS"] == 20
    assert pd.api.types.is_datetime64_any_dtype(cached["game_log"]["GAME_DATE"])
    assert player_data.clear_player_profile_cache() == 1
    assert player_data._load_player_profile_cache(1, "2025-26", "Regular Season") is None
