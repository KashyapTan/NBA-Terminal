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
                "personId": 7,
                "offensiveRating": 122.4,
                "defensiveRating": 109.2,
                "netRating": 13.2,
                "trueShootingPercentage": 0.671,
                "usagePercentage": 0.28,
                "PIE": 0.17,
            },
            {"personId": 8, "offensiveRating": 100},
        ]
    )

    class Advanced:
        def __init__(self, **kwargs):
            assert kwargs == {"game_id": "0022400001", "timeout": 12}

        def get_data_frames(self):
            return [advanced, pd.DataFrame()]

    monkeypatch.setattr(player_analysis.game_center, "fetch_player_game_analysis", lambda *args: base_analysis())
    monkeypatch.setattr(player_analysis.boxscoreadvancedv3, "BoxScoreAdvancedV3", Advanced)
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
        ([pd.DataFrame([{"personId": 9, "offensiveRating": 100}])], "unavailable"),
        ([pd.DataFrame([{"personId": 7}])], "unavailable"),
    ],
)
def test_advanced_stats_report_unavailable_for_missing_endpoint_rows(monkeypatch, frames, state):
    monkeypatch.setattr(
        player_analysis.boxscoreadvancedv3,
        "BoxScoreAdvancedV3",
        lambda **kwargs: type("Advanced", (), {"get_data_frames": lambda self: frames})(),
    )
    assert player_analysis._fetch_advanced_stats("0022400001", 7)[1] == state


def test_advanced_stats_report_request_error(monkeypatch):
    monkeypatch.setattr(
        player_analysis.boxscoreadvancedv3,
        "BoxScoreAdvancedV3",
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


def test_real_upstream_raw_v3_response_through_installed_parser(monkeypatch):
    import json
    from pathlib import Path

    from nba_api.stats.library.http import NBAStatsResponse

    # Unmodified upstream provider response (WNBA game); tests real V3 nested parser shape,
    # not an assertion that this fixture is a live NBA observation.
    raw = Path("tests/fixtures/nba_boxscoreadvancedv3_upstream.json").read_text()
    payload = json.loads(raw)
    game_id = payload["boxScoreAdvanced"]["gameId"]
    endpoint = player_analysis.boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=game_id, get_request=False)
    endpoint.nba_response = NBAStatsResponse(response=raw, status_code=200, url="fixture")
    endpoint.load_response()
    monkeypatch.setattr(player_analysis.boxscoreadvancedv3, "BoxScoreAdvancedV3", lambda **kwargs: endpoint)
    values, state, _ = player_analysis._fetch_advanced_stats(game_id, 1642809)
    assert state == "available"
    assert values["off_rating"] == 66.7
    assert values["usg_pct"] == 0.29
    assert values["tov_ratio"] == 20.0
    assert "tm_tov_pct" not in values
    assert values["pie"] == -0.018
    assert values["poss"] == 27


@pytest.mark.parametrize(
    "row,state",
    [
        ({"PLAYER_ID": 7}, "error"),
        ({"personId": 7, "minutes": "0:00", "offensiveRating": 0}, "unavailable"),
        ({"personId": 7, "gameId": "0022400999", "offensiveRating": 100}, "unavailable"),
        ({"personId": 7, "minutes": "1:00", "trueShootingPercentage": None}, "unavailable"),
    ],
)
def test_v3_schema_dnp_other_game_and_null_metrics(monkeypatch, row, state):
    monkeypatch.setattr(
        player_analysis.boxscoreadvancedv3,
        "BoxScoreAdvancedV3",
        lambda **kwargs: type("Endpoint", (), {"get_data_frames": lambda self: [pd.DataFrame([row])]})(),
    )
    assert player_analysis._fetch_advanced_stats("0022400001", 7)[1] == state


def test_search_is_accent_insensitive_active_first_and_bounded(monkeypatch):
    monkeypatch.setattr(
        player_data.players,
        "get_players",
        lambda: [
            {"id": 2, "full_name": "Nikola Jokic", "is_active": False},
            {"id": 1, "full_name": "Nikola Jokić", "is_active": True},
        ],
    )
    assert player_data.search_players("jokic nik", 1) == [{"player_id": 1, "name": "Nikola Jokić", "active": True}]
    assert player_data.search_players("unknown") == []


def test_profile_uses_identity_and_joint_complete_shooting_totals(monkeypatch):
    monkeypatch.setattr(player_analysis.players, "find_player_by_id", lambda _: {"full_name": "Test Player"})
    monkeypatch.setattr(player_analysis, "_fetch_game_log", lambda *args: game_log())
    profile = player_analysis.fetch_player_profile(7, "2025-26", "Playoffs")
    assert profile["phase"] == "Playoffs"
    assert profile["history"]["games_played"] == 3
    assert profile["shooting"]["efg_pct"]["value"] == pytest.approx((22 + 0.5 * 9) / 45)
    assert profile["shooting"]["ts_pct"]["value"] == pytest.approx(66 / (2 * (45 + 0.44 * 13)))
    rates = player_analysis._aggregate_shooting(
        [
            {"fgm": 1, "fg3m": 1, "fga": 2},
            {"fgm": 9, "fg3m": None, "fga": 12},
        ]
    )
    assert rates["efg_pct"] == {"value": 0.75, "games": 1}
    assert rates["ts_pct"] == {"value": None, "games": 0}
    assert player_analysis._aggregate_shooting([{"fga": 0, "fg3a": 0}])["fg3a_rate"]["value"] is None
    monkeypatch.setattr(player_analysis.players, "find_player_by_id", lambda _: None)
    with pytest.raises(ValueError, match="Player ID"):
        player_analysis.fetch_player_profile(0, "2025-26", "Regular Season")


def test_game_ids_keep_leading_zeroes():
    assert player_analysis._records(pd.DataFrame({"GAME_ID": [22400001, None]})) == [
        {"game_id": "0022400001"},
        {"game_id": None},
    ]


def test_batch_season_dashboard_states_and_identity(monkeypatch):
    def endpoint(frame):
        return lambda **kwargs: type("Endpoint", (), {"get_data_frames": lambda self: [frame]})()

    monkeypatch.setattr(
        player_analysis.leaguedashplayerstats,
        "LeagueDashPlayerStats",
        endpoint(
            pd.DataFrame(
                [
                    {"PLAYER_ID": 7, "GP": 1, "TS_PCT": 0.5},
                    {"PLAYER_ID": 7, "GP": 3, "TS_PCT": 0.6},
                ]
            )
        ),
    )
    result = player_analysis.fetch_season_advanced("2025-26", "Regular Season")
    assert result["state"] == "available"
    assert result["players"]["7"]["TS_PCT"] == 0.6
    monkeypatch.setattr(player_analysis.leaguedashplayerstats, "LeagueDashPlayerStats", endpoint(pd.DataFrame()))
    assert player_analysis.fetch_season_advanced("2025-26", "Playoffs")["state"] == "unavailable"
    monkeypatch.setattr(
        player_analysis.leaguedashplayerstats, "LeagueDashPlayerStats", endpoint(pd.DataFrame([{"wrong": 7}]))
    )
    assert player_analysis.fetch_season_advanced("2025-26", "Playoffs")["state"] == "error"
    monkeypatch.setattr(
        player_analysis.leaguedashplayerstats,
        "LeagueDashPlayerStats",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    assert player_analysis.fetch_season_advanced("2025-26", "Playoffs")["state"] == "error"


def test_live_captured_nba_v3_response_schema_regression(monkeypatch):
    from pathlib import Path

    from nba_api.stats.library.http import NBAStatsResponse

    raw = Path("tests/fixtures/nba_boxscoreadvancedv3_finals_2025.json").read_text()
    endpoint = player_analysis.boxscoreadvancedv3.BoxScoreAdvancedV3(game_id="0042400407", get_request=False)
    endpoint.nba_response = NBAStatsResponse(response=raw, status_code=200, url="captured-fixture")
    endpoint.load_response()
    monkeypatch.setattr(player_analysis.boxscoreadvancedv3, "BoxScoreAdvancedV3", lambda **kwargs: endpoint)
    values, state, _ = player_analysis._fetch_advanced_stats("0042400407", 1628983)
    assert state == "available"
    assert values["off_rating"] > 0
    assert 0 < values["usg_pct"] < 1
    assert values["poss"] > 0
    assert "tm_tov_pct" not in values


@pytest.mark.parametrize("measure", ["Base", "Misc", "Scoring", "Usage", "Defense"])
def test_captured_season_measure_provider_schema(monkeypatch, measure):
    from pathlib import Path

    from nba_api.stats.library.http import NBAStatsResponse

    raw = Path(f"tests/fixtures/nba_player_season_{measure.lower()}_2025.json").read_text()
    endpoint = player_analysis.leaguedashplayerstats.LeagueDashPlayerStats(get_request=False)
    endpoint.nba_response = NBAStatsResponse(response=raw, status_code=200, url="captured-fixture")
    endpoint.load_response()

    def captured(**kwargs):
        assert kwargs["measure_type_detailed_defense"] == measure
        assert kwargs["per_mode_detailed"] == "PerGame"
        assert kwargs["timeout"] == 12
        return endpoint

    monkeypatch.setattr(player_analysis.leaguedashplayerstats, "LeagueDashPlayerStats", captured)
    result = player_analysis.fetch_season_advanced("2024-25", "Playoffs", measure)
    assert result["state"] == "available"
    assert result["players"]["1628983"]["GP"] == 23


def test_captured_shooting_splits_all_six_tables_and_zero_attempt_rates(monkeypatch):
    from pathlib import Path

    from nba_api.stats.library.http import NBAStatsResponse

    raw = Path("tests/fixtures/nba_player_shooting_splits_2025.json").read_text()
    endpoint = player_analysis.playerdashboardbyshootingsplits.PlayerDashboardByShootingSplits(
        player_id=1628983,
        get_request=False,
    )
    endpoint.nba_response = NBAStatsResponse(response=raw, status_code=200, url="captured-fixture")
    endpoint.load_response()
    monkeypatch.setattr(
        player_analysis.playerdashboardbyshootingsplits, "PlayerDashboardByShootingSplits", lambda **kwargs: endpoint
    )
    result = player_analysis.fetch_player_shooting_tables(1628983, "2024-25", "Playoffs")
    assert result["state"] == "available"
    assert set(result["tables"]) == set(player_data.SHOOTING_SPLIT_TABLES)
    for table in result["tables"].values():
        assert table["state"] == "available"
        assert all("GROUP_VALUE" in row for row in table["rows"])
        for row in table["rows"]:
            if row.get("FG3A") == 0:
                assert row["FG3_PCT"] is None
    overall = result["tables"]["Overall"]["rows"][0]
    assert overall["FGA"] == 504
    assert overall["FGM"] == 233


def test_shooting_splits_transport_empty_and_schema_failures(monkeypatch):
    monkeypatch.setattr(
        player_analysis.playerdashboardbyshootingsplits,
        "PlayerDashboardByShootingSplits",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    assert player_analysis.fetch_player_shooting_tables(7, "2025-26", "Playoffs")["state"] == "error"
    data = type("Data", (), {"get_data_frame": lambda self: pd.DataFrame()})()
    endpoint = type("Endpoint", (), {attribute: data for attribute in player_data.SHOOTING_SPLIT_TABLES.values()})()
    monkeypatch.setattr(
        player_analysis.playerdashboardbyshootingsplits, "PlayerDashboardByShootingSplits", lambda **kwargs: endpoint
    )
    assert player_analysis.fetch_player_shooting_tables(7, "2025-26", "Playoffs")["state"] == "unavailable"
    endpoint.overall_player_dashboard = type(
        "Data", (), {"get_data_frame": lambda self: pd.DataFrame([{"wrong": 1}])}
    )()
    result = player_analysis.fetch_player_shooting_tables(7, "2025-26", "Playoffs")
    assert result["state"] == "error"
    assert result["tables"]["Overall"]["state"] == "error"
    assert result["tables"]["Shot Area"]["state"] == "unavailable"


def test_zero_attempt_shooting_rates_remain_unknown_and_invalid_history_schema_is_error(monkeypatch):
    frame = pd.DataFrame(
        [{"GROUP_VALUE": "No attempts", "FGM": 0, "FGA": 0, "FG3A": 0, "FG_PCT": 0, "EFG_PCT": 0, "FG3_PCT": 0}]
    )
    dataset = type("Data", (), {"get_data_frame": lambda self: frame})()
    endpoint = type("Endpoint", (), {attribute: dataset for attribute in player_data.SHOOTING_SPLIT_TABLES.values()})()
    monkeypatch.setattr(
        player_analysis.playerdashboardbyshootingsplits, "PlayerDashboardByShootingSplits", lambda **kwargs: endpoint
    )
    result = player_analysis.fetch_player_shooting_tables(7, "2025-26", "Playoffs")
    assert result["tables"]["Overall"]["rows"][0]["FG_PCT"] is None
    assert result["tables"]["Overall"]["rows"][0]["FG3_PCT"] is None
    monkeypatch.setattr(player_analysis, "_fetch_game_log", lambda *args: pd.DataFrame([{"PTS": 10}]))
    assert player_analysis._fetch_history(7, "2025-26", "Playoffs", {}, "")[0]["state"] == "error"


def test_reference_game_log_mixed_case_ids_keep_profile_and_links_available(monkeypatch):
    frame = game_log().rename(columns={"GAME_ID": "Game_ID"})
    endpoint = type("Log", (), {"get_data_frames": lambda self: [frame]})()
    monkeypatch.setattr(player_analysis.playergamelog, "PlayerGameLog", lambda **kwargs: endpoint)
    profile = player_analysis.fetch_player_profile(1628983, "2024-25", "Playoffs")
    assert profile["history"]["state"] == "available"
    assert profile["history"]["games_played"] == 3
    assert profile["history"]["games"][0]["game_id"] == "0022400001"
