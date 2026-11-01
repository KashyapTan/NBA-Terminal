import json
from datetime import date, datetime, timezone
from io import BytesIO

import pandas as pd
import pytest

from nba_terminal.services import game_center as service

TEAMS = [
    {"id": 1, "abbreviation": "CLE", "full_name": "Cleveland Cavaliers", "nickname": "Cavaliers"},
    {"id": 2, "abbreviation": "BOS", "full_name": "Boston Celtics", "nickname": "Celtics"},
]


def schedule_row(game_id, game_date, status=3, away_id=1, home_id=2):
    status_text = "Final" if status == 3 else ("Scheduled" if status == 1 else "In progress")
    return {
        "gameDateEst": game_date,
        "gameDateTimeUTC": f"{game_date}T23:30:00Z",
        "gameId": game_id,
        "gameStatus": status,
        "gameStatusText": status_text,
        "homeTeam_teamId": home_id,
        "homeTeam_teamName": "Celtics" if home_id == 2 else "Unknown Club",
        "homeTeam_teamCity": "Boston" if home_id == 2 else "Unknown City",
        "homeTeam_teamTricode": "BOS" if home_id == 2 else "UNK",
        "homeTeam_score": 110 if status == 3 else None,
        "awayTeam_teamId": away_id,
        "awayTeam_teamName": "Cavaliers" if away_id == 1 else "Unknown Club",
        "awayTeam_teamCity": "Cleveland" if away_id == 1 else "Unknown City",
        "awayTeam_teamTricode": "CLE" if away_id == 1 else "UNK",
        "awayTeam_score": 99 if status == 3 else None,
    }


def install_schedule(monkeypatch, rows):
    frame = pd.DataFrame(rows, columns=schedule_row("0022500001", "2025-11-02").keys())

    class Schedule:
        def __init__(self, league_id="00", season="2025-26", timeout=12):
            self.season = season
            self.timeout = timeout
            self.season_games = type("SeasonGames", (), {"get_data_frame": lambda self: frame})()

    monkeypatch.setattr(service.scheduleleaguev2, "ScheduleLeagueV2", Schedule)
    return frame


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


def test_upcoming_uses_eastern_three_day_schedule_and_keeps_source_team_fallback(monkeypatch):
    unassigned_cup_game = schedule_row("0022501201", "2025-12-04", status=1, away_id=0, home_id=0)
    for side in ("home", "away"):
        for field in ("teamName", "teamCity", "teamTricode"):
            unassigned_cup_game[f"{side}Team_{field}"] = None
    install_schedule(monkeypatch, [
        schedule_row("0012500001", "2025-11-02", status=1),
        schedule_row("0022500002", "2025-11-02", status=2),
        schedule_row("0022500003", "2025-11-03", status=1, home_id=99),
        schedule_row("0022500004", "2025-11-04", status=1),
        unassigned_cup_game,
    ])
    result = service.fetch_upcoming_games(date(2025, 11, 2))
    assert result["days"] == ["2025-11-02", "2025-11-03", "2025-11-04"]
    assert len(result["games"]) == 4
    game, live_game, next_day_game, third_day_game = result["games"]
    assert live_game["status_id"] == 2
    assert third_day_game["date"] == "2025-11-04"
    assert (game["game_id"], game["phase"], game["status"], game["home_score"]) == (
        "0012500001",
        "Pre Season",
        "Scheduled",
        None,
    )
    assert game["home_team"]["name"] == "Boston Celtics"
    assert game["start_time"] == "2025-11-02T23:30:00Z"
    assert next_day_game["date"] == "2025-11-03"
    assert next_day_game["home_team"]["abbreviation"] == "UNK"


def test_nba_today_uses_eastern_date_across_utc_midnight(monkeypatch):
    class FrozenDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 1, 0, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(service, "datetime", FrozenDateTime)
    assert service.nba_today() == date(2026, 9, 30)
    monkeypatch.setattr(service, "datetime", datetime)
    monkeypatch.setattr(service, "nba_today", lambda: date(2026, 9, 30))
    assert service.current_season() == "2025-26"


def test_recent_games_covers_every_schedule_phase_and_orders_by_date(monkeypatch):
    unassigned_cup_game = schedule_row("0022401201", "2024-12-04", status=1, away_id=0, home_id=0)
    for side in ("home", "away"):
        for field in ("teamName", "teamCity", "teamTricode"):
            unassigned_cup_game[f"{side}Team_{field}"] = None
    install_schedule(monkeypatch, [
        schedule_row("0012400001", "2024-10-01"),
        schedule_row("0022400002", "2024-11-01"),
        unassigned_cup_game,
        schedule_row("0032400003", "2025-02-16", away_id=99, home_id=100),
        schedule_row("0042400004", "2025-04-01"),
        schedule_row("0052400005", "2025-04-15"),
        schedule_row("0062400006", "2025-12-17"),
    ])
    result = service.fetch_recent_games("2024-25")
    assert result["supported"] is True
    assert [game["game_id"] for game in result["games"]] == [
        "0062400006", "0052400005", "0042400004", "0032400003", "0022400002", "0012400001",
    ]
    assert [game["phase"] for game in result["games"]] == [
        "NBA Cup Final", "Play In", "Playoffs", "All Star", "Regular Season", "Pre Season",
    ]
    assert result["games"][-1]["home_score"] == 110
    assert result["games"][-1]["away_team"]["abbreviation"] == "CLE"
    assert service.fetch_recent_games("1995-96")["supported"] is False


def test_schedule_contract_drift_is_an_error_not_an_empty_slate(monkeypatch):
    class Schedule:
        def __init__(self, **kwargs):
            self.season_games = type(
                "SeasonGames", (), {"get_data_frame": lambda self: pd.DataFrame(columns=["gameId"])}
            )()

    monkeypatch.setattr(service.scheduleleaguev2, "ScheduleLeagueV2", Schedule)
    with pytest.raises(RuntimeError, match="missing expected fields"):
        service.fetch_upcoming_games(date(2025, 11, 2))


def test_upcoming_falls_back_to_official_current_season_cdn(monkeypatch):
    def unavailable_stats(**kwargs):
        raise TimeoutError("Stats endpoint timed out")

    game = {
        "gameId": "0022500001",
        "gameDateEst": "2025-11-02",
        "gameDateTimeUTC": "2025-11-03T00:30:00Z",
        "gameStatus": 1,
        "gameStatusText": "Scheduled",
        "awayTeam": {
            "teamId": 1,
            "teamCity": "Cleveland",
            "teamName": "Cavaliers",
            "teamTricode": "CLE",
            "score": None,
        },
        "homeTeam": {
            "teamId": 2,
            "teamCity": "Boston",
            "teamName": "Celtics",
            "teamTricode": "BOS",
            "score": None,
        },
    }
    payload = {"leagueSchedule": {"seasonYear": "2025-26", "gameDates": [{"gameDate": "2025-11-02", "games": [game]}]}}
    monkeypatch.setattr(service, "nba_today", lambda: date(2025, 11, 2))
    monkeypatch.setattr(service.scheduleleaguev2, "ScheduleLeagueV2", unavailable_stats)
    monkeypatch.setattr(service, "urlopen", lambda request, timeout: BytesIO(json.dumps(payload).encode()))
    result = service.fetch_upcoming_games(date(2025, 11, 2))
    assert [game["game_id"] for game in result["games"]] == ["0022500001"]
    assert result["games"][0]["away_team"]["abbreviation"] == "CLE"


def test_upcoming_reports_error_when_both_official_schedule_sources_fail(monkeypatch):
    monkeypatch.setattr(
        service.scheduleleaguev2,
        "ScheduleLeagueV2",
        lambda **kwargs: (_ for _ in ()).throw(TimeoutError("Stats timeout")),
    )
    monkeypatch.setattr(service, "urlopen", lambda request, timeout: (_ for _ in ()).throw(OSError("CDN down")))
    monkeypatch.setattr(service, "nba_today", lambda: date(2025, 11, 2))
    with pytest.raises(OSError, match="CDN down"):
        service.fetch_upcoming_games(date(2025, 11, 2))


def test_current_schedule_schema_drift_uses_the_official_cdn_fallback(monkeypatch):
    class MalformedSchedule:
        def __init__(self, **kwargs):
            self.season_games = type("SeasonGames", (), {"get_data_frame": lambda self: pd.DataFrame()})()

    monkeypatch.setattr(service, "nba_today", lambda: date(2025, 11, 2))
    monkeypatch.setattr(service.scheduleleaguev2, "ScheduleLeagueV2", MalformedSchedule)
    fallback = pd.DataFrame([schedule_row("0022500001", "2025-11-02", status=1)])
    monkeypatch.setattr(service, "_cdn_schedule_dataframe", lambda season: fallback)
    assert [game["game_id"] for game in service.fetch_upcoming_games(date(2025, 11, 2))["games"]] == [
        "0022500001"
    ]


def test_schedule_row_validation_rejects_bad_dates_ids_status_and_team_details():
    with pytest.raises(RuntimeError, match="valid Eastern game date"):
        service._required_schedule_date(None)
    assert service._utc_start_time(None) is None
    assert service._utc_start_time("not a timestamp") is None
    with pytest.raises(RuntimeError, match="invalid home team ID"):
        service._schedule_team(pd.Series({"homeTeam_teamId": None}), "home", {})
    with pytest.raises(RuntimeError, match="incomplete details"):
        service._schedule_team(
            pd.Series(
                {
                    "homeTeam_teamId": 99,
                    "homeTeam_teamName": "",
                    "homeTeam_teamCity": "",
                    "homeTeam_teamTricode": "UNK",
                }
            ),
            "home",
            {},
        )
    with pytest.raises(RuntimeError, match="without a valid 10-digit ID"):
        service._schedule_game(pd.Series(schedule_row("bad", "2025-11-02")), {})
    invalid_status = schedule_row("0022500001", "2025-11-02")
    invalid_status["gameStatus"] = "unknown"
    with pytest.raises(RuntimeError, match="invalid status"):
        service._schedule_game(pd.Series(invalid_status), {})


def test_boxscore_support_and_no_matchup_fallback(monkeypatch):
    monkeypatch.setattr(
        service.boxscoretraditionalv2,
        "BoxScoreTraditionalV2",
        lambda **kwargs: type("Box", (), {"get_data_frames": lambda self: []})(),
    )
    with pytest.raises(ValueError, match="YYYY-YY"):
        service._season_start(None)
    with pytest.raises(ValueError, match="supported from"):
        service.fetch_game_boxscore("0029500001", "1995-96")
    install_schedule(monkeypatch, [schedule_row("0022400002", "2025-01-02")])
    result = service.fetch_game_boxscore("0022400001", "2024-25")
    assert result["away_team"] is None
    assert result["home_team"] is None


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
                    pd.DataFrame([{"TEAM_ID": 2, "PTS": 112}, {"TEAM_ID": 1, "PTS": 99}]),
                ]
            },
        )(),
    )
    install_schedule(monkeypatch, [schedule_row("0022400001", "2025-01-02")])
    result = service.fetch_game_boxscore("0022400001")
    assert result["players"][0]["player_id"] == 4
    assert result["players"][0]["plus_minus"] is None
    assert result["players"][0]["team"]["abbreviation"] == "CLE"
    assert result["teams"][0]["team"]["abbreviation"] == "CLE"
    assert [team["team"]["abbreviation"] for team in result["teams"]] == ["CLE", "BOS"]
    assert result["away_team"]["abbreviation"] == "CLE"
    assert result["home_team"]["abbreviation"] == "BOS"
    with pytest.raises(ValueError, match="10-digit"):
        service.fetch_game_boxscore("not-a-game")


def test_player_analysis_missing_player_and_shot_chart_states(monkeypatch):
    player = {"player_id": 7, "player_name": "Player", "team_id": 1, "pts": 12}
    monkeypatch.setattr(service, "fetch_game_boxscore", lambda game_id, season=None: {"players": [player], "teams": []})
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
                    "EVENT_TYPE": "Made Shot",
                    "SHOT_TYPE": "2PT Field Goal",
                    "MINUTES_REMAINING": 8,
                    "SECONDS_REMAINING": 12,
                    "SHOT_ZONE_BASIC": "Restricted Area",
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
        {
            "x": 10.0,
            "y": 20.0,
            "made": True,
            "description": "Layup",
            "period": 1,
            "distance": 2,
            "event_type": "Made Shot",
            "shot_type": "2PT Field Goal",
            "minutes_remaining": 8,
            "seconds_remaining": 12,
            "zone": "Restricted Area",
        }
    ]
    ShotChart.frame = pd.DataFrame(columns=["LOC_X", "LOC_Y", "SHOT_MADE_FLAG"])
    assert service.fetch_player_game_analysis("0022400001", 7, "2024-25")["shot_chart_state"] == "unavailable"
    ShotChart.get_data_frames = lambda self: (_ for _ in ()).throw(RuntimeError("offline"))
    failed = service.fetch_player_game_analysis("0022400001", 7, "2024-25")
    assert failed["shot_chart_state"] == "error"
    assert failed["stats"] == player
    ShotChart.get_data_frames = lambda self: [pd.DataFrame([{"LOC_X": 1, "LOC_Y": 2}])]
    assert service.fetch_player_game_analysis("0022400001", 7, "2024-25")["shot_chart_state"] == "unavailable"


def test_schedule_window_preserves_live_final_and_special_statuses(monkeypatch):
    rows = [
        schedule_row("0022500001", "2025-11-02", status=2),
        schedule_row("0022500002", "2025-11-02", status=3),
        schedule_row("0022500003", "2025-11-04", status=1, home_id=99),
        schedule_row("0022500004", "2025-11-05", status=1),
        schedule_row("0022500005", "2025-11-01", status=3),
    ]
    rows[0].update(gameStatusText="Q3 4:21", homeTeam_score=82, awayTeam_score=79)
    rows[1]["gameStatusText"] = "Final/OT"
    rows[2]["gameStatusText"] = "Postponed"
    install_schedule(monkeypatch, rows)
    games = service.fetch_upcoming_games(date(2025, 11, 2))["games"]
    assert [game["status"] for game in games] == ["Q3 4:21", "Final/OT", "Postponed"]
    assert (games[0]["home_score"], games[0]["away_score"]) == (82, 79)
    assert games[0]["home_team"]["logo_url"] == "https://cdn.nba.com/logos/nba/2/primary/L/logo.svg"
    assert games[2]["home_team"]["logo_url"] is None
    for status, expected in [(1, "Scheduled"), (2, "In progress"), (3, "Final"), (4, "Status unavailable")]:
        row = schedule_row("0022500001", "2025-11-02", status=status)
        row["gameStatusText"] = None
        assert service._schedule_game(pd.Series(row), service._team_lookup())["status"] == expected


def test_real_traditional_provider_to_reaches_player_and_team_tov(monkeypatch):
    from pathlib import Path

    from nba_api.stats.library.http import NBAStatsResponse

    raw = Path("tests/fixtures/nba_traditional_v2_current_2026.json").read_text()
    endpoint = service.boxscoretraditionalv2.BoxScoreTraditionalV2(game_id="0022600152", get_request=False)
    endpoint.nba_response = NBAStatsResponse(response=raw, status_code=200, url="captured-public-traditional-v2")
    endpoint.load_response()
    monkeypatch.setattr(service.boxscoretraditionalv2, "BoxScoreTraditionalV2", lambda **kwargs: endpoint)
    monkeypatch.setattr(service, "_schedule_dataframe", lambda *args, **kwargs: pd.DataFrame({"gameId": []}))
    box = service.fetch_game_boxscore("0022600152", "2026-27")
    jaden = next(row for row in box["players"] if row["player_id"] == 1630183)
    assert jaden["tov"] == jaden["to"] == 2
    assert len(box["teams"]) == 2
    assert all(row["tov"] == row["to"] for row in box["teams"])


@pytest.mark.parametrize("row, expected", [({"TO": None}, None), ({"TO": 0}, 0),
                                         ({"TOV": 3}, 3), ({"TURNOVERS": 4}, 4), ({}, None)])
def test_traditional_turnover_aliases_preserve_unknown_and_zero(row, expected):
    assert service._traditional_record(pd.Series(row))["tov"] == expected
