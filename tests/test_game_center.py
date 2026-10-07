from datetime import date

import pandas as pd
import pytest

from nba_terminal.services import game_center as service

TEAMS = [
    {"id": 1, "abbreviation": "CLE", "full_name": "Cleveland Cavaliers", "nickname": "Cavaliers"},
    {"id": 2, "abbreviation": "BOS", "full_name": "Boston Celtics", "nickname": "Celtics"},
]


@pytest.fixture(autouse=True)
def teams(monkeypatch):
    monkeypatch.setattr(service.teams, "get_teams", lambda: TEAMS)


def test_seasons_roll_over_in_october_and_stop_at_supported_start():
    assert service.current_season(date(2025, 9, 30)) == "2024-25"
    assert service.current_season(date(2025, 10, 1)) == "2025-26"
    assert service.available_seasons(date(2025, 10, 1)) == [
        "2025-26",
        "2024-25",
        "2023-24",
        "2022-23",
        "2021-22",
        "2020-21",
        "2019-20",
        "2018-19",
        "2017-18",
        "2016-17",
        "2015-16",
        "2014-15",
        "2013-14",
        "2012-13",
        "2011-12",
        "2010-11",
        "2009-10",
        "2008-09",
        "2007-08",
        "2006-07",
        "2005-06",
        "2004-05",
        "2003-04",
        "2002-03",
        "2001-02",
        "2000-01",
        "1999-00",
        "1998-99",
        "1997-98",
        "1996-97",
    ]
    assert service._date_string("date unavailable") == "date unavailable"
    assert service._serial({"unexpected": "value"}) == "{'unexpected': 'value'}"


@pytest.mark.parametrize("season", ["1996-96", "2025/26", "25-26", "2025-27"])
def test_invalid_season_is_rejected(season):
    with pytest.raises(ValueError, match="YYYY-YY"):
        service._season_start(season)


def test_upcoming_keeps_only_scheduled_games_and_skips_unknown_teams(monkeypatch):
    frames = [
        pd.DataFrame(
            [
                {
                    "GAME_ID": "0012600001",
                    "GAME_STATUS_ID": 1,
                    "GAME_STATUS_TEXT": "7:00 PM",
                    "HOME_TEAM_ID": 2,
                    "VISITOR_TEAM_ID": 1,
                },
                {
                    "GAME_ID": "0022600002",
                    "GAME_STATUS_ID": 2,
                    "GAME_STATUS_TEXT": "Final",
                    "HOME_TEAM_ID": 2,
                    "VISITOR_TEAM_ID": 1,
                },
                {
                    "GAME_ID": "0022600003",
                    "GAME_STATUS_ID": 1,
                    "GAME_STATUS_TEXT": "8:00 PM",
                    "HOME_TEAM_ID": 99,
                    "VISITOR_TEAM_ID": 1,
                },
            ]
        ),
        pd.DataFrame(columns=["GAME_ID", "GAME_STATUS_ID", "HOME_TEAM_ID", "VISITOR_TEAM_ID"]),
    ]

    class Scoreboard:
        def __init__(self, game_date, timeout):
            self.game_header = type("Header", (), {"get_data_frame": lambda self: frames.pop(0)})()

    monkeypatch.setattr(service.scoreboardv2, "ScoreboardV2", Scoreboard)
    result = service.fetch_upcoming_games(date(2025, 11, 2))
    assert result["days"] == ["2025-11-02", "2025-11-03"]
    assert len(result["games"]) == 1
    game = result["games"][0]
    assert (game["game_id"], game["phase"], game["status"], game["home_score"]) == (
        "0012600001",
        "Pre Season",
        "Scheduled",
        None,
    )
    assert game["home_team"]["name"] == "Boston Celtics"


def test_recent_games_normalizes_home_away_sorts_and_skips_incomplete_rows(monkeypatch):
    rows = pd.DataFrame(
        [
            {
                "GAME_ID": "0021",
                "GAME_DATE": "2025-01-03",
                "MATCHUP": "BOS vs. CLE",
                "WL": "W",
                "TEAM_ID": 2,
                "PTS": 110,
            },
            {"GAME_ID": "0021", "GAME_DATE": "2025-01-03", "MATCHUP": "CLE @ BOS", "WL": "L", "TEAM_ID": 1, "PTS": 99},
            {
                "GAME_ID": "0020",
                "GAME_DATE": "2024-12-01",
                "MATCHUP": "BOS vs. CLE",
                "WL": "W",
                "TEAM_ID": 2,
                "PTS": 101,
            },
            {"GAME_ID": "0020", "GAME_DATE": "2024-12-01", "MATCHUP": "CLE @ BOS", "WL": "L", "TEAM_ID": 1, "PTS": 90},
            {"GAME_ID": "bad", "GAME_DATE": "2025-01-01", "MATCHUP": "BOS vs. CLE", "WL": None, "TEAM_ID": 2, "PTS": 1},
            {"GAME_ID": "bad", "GAME_DATE": "2025-01-01", "MATCHUP": "CLE @ BOS", "WL": "L", "TEAM_ID": 1, "PTS": 2},
            {
                "GAME_ID": "unknown",
                "GAME_DATE": "2025-01-01",
                "MATCHUP": "XXX vs. CLE",
                "WL": "W",
                "TEAM_ID": 99,
                "PTS": 3,
            },
            {
                "GAME_ID": "unknown",
                "GAME_DATE": "2025-01-01",
                "MATCHUP": "CLE @ XXX",
                "WL": "L",
                "TEAM_ID": 1,
                "PTS": 2,
            },
            {
                "GAME_ID": "orphan",
                "GAME_DATE": "2025-01-01",
                "MATCHUP": "BOS vs. CLE",
                "WL": "W",
                "TEAM_ID": 2,
                "PTS": 3,
            },
        ]
    )

    class Finder:
        def __init__(self, **kwargs):
            self.phase = kwargs["season_type_nullable"]

        def get_data_frames(self):
            return [rows if self.phase == "Regular Season" else pd.DataFrame()]

    monkeypatch.setattr(service.leaguegamefinder, "LeagueGameFinder", Finder)
    result = service.fetch_recent_games("2024-25")
    assert result["supported"] is True
    assert [game["game_id"] for game in result["games"]] == ["0021", "0020"]
    assert result["games"][0]["home_score"] == 110
    assert result["games"][0]["away_team"]["abbreviation"] == "CLE"
    assert service.fetch_recent_games("1995-96")["supported"] is False


def test_game_boxscore_handles_missing_frames_and_serializes_nulls(monkeypatch):
    monkeypatch.setattr(
        service.boxscoretraditionalv2,
        "BoxScoreTraditionalV2",
        lambda **kwargs: type(
            "Box",
            (),
            {
                "get_data_frames": lambda self: [
                    pd.DataFrame([{"PLAYER_ID": 4, "TEAM_ID": 1, "PLUS_MINUS": pd.NA}]),
                    pd.DataFrame([{"TEAM_ID": 2, "PTS": 112}]),
                ]
            },
        )(),
    )
    result = service.fetch_game_boxscore("0022400001")
    assert result["players"][0]["player_id"] == 4
    assert result["players"][0]["plus_minus"] is None
    assert result["players"][0]["team"]["abbreviation"] == "CLE"
    assert result["teams"][0]["team"]["abbreviation"] == "BOS"
    with pytest.raises(ValueError, match="10-digit"):
        service.fetch_game_boxscore("not-a-game")


def test_player_analysis_missing_player_and_shot_chart_states(monkeypatch):
    player = {"player_id": 7, "player_name": "Player", "team_id": 1, "pts": 12}
    monkeypatch.setattr(service, "fetch_game_boxscore", lambda game_id: {"players": [player], "teams": []})
    with pytest.raises(ValueError, match="does not appear"):
        service.fetch_player_game_analysis("0022400001", 8, "2024-25")

    class ShotChart:
        frame = pd.DataFrame(
            [
                {
                    "LOC_X": "10",
                    "LOC_Y": "20",
                    "SHOT_MADE_FLAG": "1",
                    "ACTION_TYPE": "Layup",
                    "PERIOD": 1,
                    "SHOT_DISTANCE": 2,
                },
                {"LOC_X": "bad", "LOC_Y": 10, "SHOT_MADE_FLAG": 0},
            ]
        )

        def __init__(self, **kwargs):
            pass

        def get_data_frames(self):
            return [self.frame]

    monkeypatch.setattr(service.shotchartdetail, "ShotChartDetail", ShotChart)
    available = service.fetch_player_game_analysis("0022400001", 7, "2024-25")
    assert available["shot_chart_state"] == "available"
    assert available["shots"] == [
        {"x": 10.0, "y": 20.0, "made": True, "description": "Layup", "period": 1, "distance": 2}
    ]
    ShotChart.frame = pd.DataFrame(columns=["LOC_X", "LOC_Y", "SHOT_MADE_FLAG"])
    assert service.fetch_player_game_analysis("0022400001", 7, "2024-25")["shot_chart_state"] == "unavailable"
    ShotChart.get_data_frames = lambda self: (_ for _ in ()).throw(RuntimeError("offline"))
    failed = service.fetch_player_game_analysis("0022400001", 7, "2024-25")
    assert failed["shot_chart_state"] == "error"
    assert failed["stats"] == player
    ShotChart.get_data_frames = lambda self: [pd.DataFrame([{"LOC_X": 1, "LOC_Y": 2}])]
    assert service.fetch_player_game_analysis("0022400001", 7, "2024-25")["shot_chart_state"] == "unavailable"
