import pandas as pd
import pytest

from nba_terminal.services import player_analysis, player_data


def game_log():
    return player_data.add_derived_columns(
        pd.DataFrame(
            [
                {
                    "GAME_ID": "0022400001",
                    "GAME_DATE": "2025-11-02",
                    "MATCHUP": "BOS vs. CLE",
                    "WL": "W",
                    "MIN": "36:12",
                    "PTS": 30,
                    "REB": 8,
                    "AST": 5,
                    "STL": 1,
                    "BLK": 1,
                    "TOV": 2,
                    "FGM": 10,
                    "FGA": 18,
                    "FG3M": 4,
                    "FG3A": 9,
                    "FTM": 6,
                    "FTA": 7,
                    "PLUS_MINUS": 8,
                },
                {
                    "GAME_ID": "0022400002",
                    "GAME_DATE": "2025-10-30",
                    "MATCHUP": "BOS @ CLE",
                    "WL": "L",
                    "MIN": "31:30",
                    "PTS": 14,
                    "REB": 6,
                    "AST": 7,
                    "STL": 2,
                    "BLK": 0,
                    "TOV": 1,
                    "FGM": 5,
                    "FGA": 13,
                    "FG3M": 2,
                    "FG3A": 6,
                    "FTM": 2,
                    "FTA": 2,
                    "PLUS_MINUS": -4,
                },
                {
                    "GAME_ID": "0022400003",
                    "GAME_DATE": "2025-10-28",
                    "MATCHUP": "BOS vs. NYK",
                    "WL": "W",
                    "MIN": "30:00",
                    "PTS": 22,
                    "REB": 4,
                    "AST": 6,
                    "STL": 0,
                    "BLK": 1,
                    "TOV": 1,
                    "FGM": 7,
                    "FGA": 14,
                    "FG3M": 3,
                    "FG3A": 7,
                    "FTM": 3,
                    "FTA": 4,
                    "PLUS_MINUS": 10,
                },
            ]
        )
    )


def base_analysis():
    return {
        "game_id": "0022400001",
        "player": {
            "player_id": 7,
            "player_name": "Test Player",
            "team_id": 2,
            "team": {"id": 2, "abbreviation": "BOS", "name": "Boston Celtics", "nickname": "Celtics"},
        },
        "stats": {},
        "shots": [],
        "shot_chart_state": "unavailable",
        "game_context": {
            "game_id": "0022400001",
            "team": {"id": 2, "abbreviation": "BOS"},
            "opponent": {"id": 1, "abbreviation": "CLE", "name": "Cleveland Cavaliers"},
            "season": "2025-26",
            "phase": "Regular Season",
        },
    }


def test_player_analysis_returns_game_advanced_and_separate_opponent_history(monkeypatch):
    advanced = pd.DataFrame(
        [
            {
                "PLAYER_ID": 7,
                "OFF_RATING": 122.4,
                "DEF_RATING": 109.2,
                "NET_RATING": 13.2,
                "TS_PCT": 0.671,
                "USG_PCT": 0.28,
                "PIE": 0.17,
            },
            {"PLAYER_ID": 8, "OFF_RATING": 100},
        ]
    )

    class Advanced:
        def __init__(self, **kwargs):
            assert kwargs == {"game_id": "0022400001", "timeout": 12}

        def get_data_frames(self):
            return [advanced, pd.DataFrame()]

    monkeypatch.setattr(player_analysis.game_center, "fetch_player_game_analysis", lambda *args: base_analysis())
    monkeypatch.setattr(player_analysis.boxscoreadvancedv2, "BoxScoreAdvancedV2", Advanced)
    monkeypatch.setattr(player_analysis, "_fetch_game_log", lambda *args: game_log())

    result = player_analysis.fetch_player_game_analysis("0022400001", 7, "2025-26", "Regular Season")
    assert result["advanced_stats_state"] == "available"
    assert result["advanced_stats"]["off_rating"] == 122.4
    assert result["advanced_stats"]["ts_pct"] == 0.671
    assert result["history_state"] == "available"
    assert result["history"]["games_played"] == 3
    assert result["history"]["opponent_games_played"] == 2
    assert result["history"]["games"][0]["game_date"] == "2025-11-02"
    assert result["history"]["games"][0]["min"] == pytest.approx(36.2)
    assert result["game_context"]["opponent_abbreviation"] == "CLE"
    assert result["game_context"]["matchup"] == "BOS vs. CLE"
    assert result["game_context"]["result"] == "W"
    assert result["history"]["summary"]["PTS"]["mean"] == pytest.approx(22)
    assert result["history"]["summary"]["PTS"]["std"] == pytest.approx(8)
    assert result["history"]["summary"]["PTS"]["consistency_cv"] == pytest.approx(8 / 22)
    assert result["history"]["summary"]["PTS"]["last_5"] == pytest.approx(22)
    assert result["history"]["summary"]["PTS"]["last_5_games"] == 3


@pytest.mark.parametrize(
    ("frames", "state"),
    [
        ([], "unavailable"),
        ([pd.DataFrame()], "unavailable"),
        ([pd.DataFrame([{"PLAYER_ID": 9, "OFF_RATING": 100}])], "unavailable"),
        ([pd.DataFrame([{"PLAYER_ID": 7}])], "unavailable"),
    ],
)
def test_advanced_stats_report_unavailable_for_missing_endpoint_rows(monkeypatch, frames, state):
    monkeypatch.setattr(
        player_analysis.boxscoreadvancedv2,
        "BoxScoreAdvancedV2",
        lambda **kwargs: type("Advanced", (), {"get_data_frames": lambda self: frames})(),
    )
    assert player_analysis._fetch_advanced_stats("0022400001", 7)[1] == state


def test_advanced_stats_report_request_error(monkeypatch):
    monkeypatch.setattr(
        player_analysis.boxscoreadvancedv2,
        "BoxScoreAdvancedV2",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    values, state, note = player_analysis._fetch_advanced_stats("0022400001", 7)
    assert values == {}
    assert state == "error"
    assert "could not return" in note


def test_fetch_game_log_preserves_missing_values_and_calculates_real_rates(monkeypatch):
    raw = pd.DataFrame(
        [
            {
                "GAME_DATE": "2025-11-02",
                "MIN": "36:30",
                "PTS": 20,
                "REB": 5,
                "AST": 4,
                "STL": 1,
                "BLK": 0,
                "FGM": 7,
                "FGA": 14,
                "FG3M": 3,
                "FG3A": 7,
                "FTA": 4,
            },
            {
                "GAME_DATE": "2025-11-01",
                "MIN": None,
                "PTS": None,
                "REB": 3,
                "AST": 1,
                "STL": 0,
                "BLK": 0,
                "FGM": None,
                "FGA": 0,
                "FG3M": 0,
                "FG3A": 0,
                "FTA": 0,
            },
        ]
    )

    class Log:
        def __init__(self, **kwargs):
            assert kwargs == {
                "player_id": 7,
                "season": "2025-26",
                "season_type_all_star": "Regular Season",
                "timeout": 12,
            }

        def get_data_frames(self):
            return [raw]

    monkeypatch.setattr(player_analysis.playergamelog, "PlayerGameLog", Log)
    frame = player_analysis._fetch_game_log(7, "2025-26", "Regular Season")
    assert frame.loc[0, "MIN"] == pytest.approx(36.5)
    assert pd.isna(frame.loc[1, "MIN"])
    assert frame.loc[0, "PRA"] == 29
    assert pd.isna(frame.loc[1, "PRA"])
    assert frame.loc[0, "EFG_PCT"] == pytest.approx(17 / 28)
    assert pd.isna(frame.loc[1, "EFG_PCT"])
    assert pd.isna(frame.loc[1, "TS_PCT"])


def test_history_states_and_matchup_fallbacks(monkeypatch):
    context = {"team": {"abbreviation": "BOS"}, "season": "2025-26", "phase": "Regular Season"}
    monkeypatch.setattr(player_analysis, "_fetch_game_log", lambda *args: pd.DataFrame())
    history, same_context = player_analysis._fetch_history(7, "2025-26", "Regular Season", context, "0022400001")
    assert history["state"] == "unavailable"
    assert same_context["team"]["abbreviation"] == "BOS"

    monkeypatch.setattr(
        player_analysis,
        "_fetch_game_log",
        lambda *args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    history, _ = player_analysis._fetch_history(7, "2025-26", "Regular Season", context, "0022400001")
    assert history["state"] == "error"
    assert history["games"] == []

    frame = game_log()
    monkeypatch.setattr(player_analysis, "_fetch_game_log", lambda *args: frame)
    history, updated_context = player_analysis._fetch_history(7, "2025-26", "Regular Season", context, "0022400001")
    assert history["opponent"] == "CLE"
    assert history["opponent_games_played"] == 2
    assert updated_context["opponent_abbreviation"] == "CLE"


def test_summary_handles_zero_means_and_record_handles_optional_columns():
    empty_values = pd.DataFrame({"PTS": [0, 0], "REB": [None, None]})
    summary = player_analysis._summaries(empty_values)
    assert summary["PTS"]["mean"] == 0
    assert summary["PTS"]["consistency_cv"] == 0
    assert summary["PTS"]["last_5"] == 0
    assert summary["PTS"]["last_5_games"] == 2
    assert "REB" not in summary
    assert player_analysis._records(empty_values) == [
        {"pts": 0, "reb": None},
        {"pts": 0, "reb": None},
    ]


def test_recent_profile_means_use_newest_non_null_values():
    summary = player_analysis._summaries(pd.DataFrame({"PTS": [10, None, 20, 30, 40, 50, 60]}))
    assert summary["PTS"]["mean"] == pytest.approx(35)
    assert summary["PTS"]["last_5"] == pytest.approx(30)
    assert summary["PTS"]["last_5_games"] == 5
