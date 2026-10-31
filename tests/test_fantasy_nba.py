"""Synthetic official NBA shapes; all network calls are mocked."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import requests

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba

NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)


def schedule():
    def game(id, start, home=1610612737, away=1610612738, **extra):
        return {
            "gameId": id,
            "gameDateTimeUTC": start,
            "gameStatus": 1,
            "postponedStatus": "N",
            "homeTeam": {"teamId": home},
            "awayTeam": {"teamId": away},
            **extra,
        }

    return {
        "leagueSchedule": {
            "seasonYear": "2026-27",
            "gameDates": [
                {
                    "games": [
                        game("0022600001", "2026-10-20T23:30:00Z"),
                        game("0022600002", "2026-10-31T23:30:00Z"),
                        game("0022600003", "2026-11-02T00:30:00Z"),  # EST Nov 1 after DST switch
                        game("0012600001", "2026-10-10T23:30:00Z"),
                        game("0062600001", "2026-12-20T23:30:00Z"),
                        game("0022600004", "2026-11-01T23:30:00Z", gameStatusText="PPD"),
                        game("0022600005", "TBD"),
                    ]
                }
            ],
        }
    }


def test_schedule_year_timezone_actual_games_and_no_games():
    games = nba.schedule_games(schedule(), 2027, NOW)
    assert nba.season_name(2027) == "2026-27"
    assert len(games[1]) == 3
    assert games[1][1]["scoring_period_id"] == 12
    assert games[1][2]["date"] == "2026-11-01"
    assert games[1][0]["started"] is True
    assert games[1][1]["started"] is False
    assert games[1][1]["opponent_pro_team_id"] == 2
    assert games[3] == []
    assert nba.schedule_games(schedule(), 2026, NOW) == {}


def test_normalization_missing_espn_schedule_uses_nba_calendar():
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    data["league"]["settings"]["scheduleSettings"].update(periodTypeId=2, matchupPeriods={"2": [2]})
    bundle = {"rates": [], "schedule": schedule(), "rates_status": "unavailable", "schedule_status": "fresh"}
    result = espn.normalize(data["league"], {}, data["pool"], data["cards"], {}, 1, now=NOW, nba=bundle)
    player = result["teams"][0]["roster"][0]
    assert result["period"]["remaining_dates"] == ["2026-10-31", "2026-11-01"]
    assert player["schedule_source"] == "nba_schedule"
    assert player["remaining_games"] == 2
    assert player["today"] is True


def test_identity_requires_unique_full_name_and_team(monkeypatch):
    monkeypatch.setattr(nba.players, "get_players", lambda: [])
    row = {"PLAYER_ID": 123, "PLAYER_NAME": "Nikola Jokić", "TEAM_ABBREVIATION": "DEN"}
    player = {"name": "Nikola Jokic", "pro_team_id": 7}
    assert nba.match_player(player, [row])[1]["nba_player_id"] == 123
    assert nba.match_player(player, [row, row | {"PLAYER_ID": 456}])[1]["status"] == "ambiguous"
    assert nba.match_player(player | {"pro_team_id": 1}, [row])[1]["status"] == "unresolved"
    assert nba.name_key("Gary Payton") != nba.name_key("Gary Payton II")
    monkeypatch.setattr(nba.players, "get_players", lambda: [{"id": 12, "full_name": "New Rookie"}])
    assert nba.match_player({"name": "New Rookie"}, [])[1]["source"] == "nba_static_unique_name"


def test_batch_current_season_rates_fill_only_missing_fields():
    player = {
        "name": "Sample Player",
        "pro_team_id": 1,
        "current_rates": {"pts": 20, "minutes": None},
        "current_games": 4,
        "prior_rates": None,
    }
    snapshot = {"teams": [{"roster": [player]}], "free_agents": [], "data_gaps": []}
    nba.enrich_players(
        snapshot,
        {
            "rates": [
                {
                    "PLAYER_ID": 123,
                    "PLAYER_NAME": "Sample Player",
                    "TEAM_ABBREVIATION": "ATL",
                    "GP": 4,
                    "PTS": 15,
                    "MIN": 30,
                    "FGM": 5,
                    "FGA": 10,
                }
            ],
            "rates_status": "fresh",
        },
    )
    assert player["current_rates"]["pts"] == 20
    assert player["current_rates"]["minutes"] == 30
    assert player["current_rates"]["fgm"] == 5
    assert player["current_rates_source"] == "espn_with_nba_stats"
    assert player["current_games"] == 4


def test_cache_failure_backoff_stale_preservation_and_expiry(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    clock = [100.0]
    monkeypatch.setattr(nba.time, "monotonic", lambda: clock[0])
    calls = []

    def fetch():
        calls.append(1)
        return [{"PTS": 10}]

    value, state = nba.cached(("test",), fetch, 10)
    assert state == "fresh"
    value[0]["PTS"] = 99
    assert nba.cached(("test",), fetch, 10)[0][0]["PTS"] == 10
    assert len(calls) == 1

    def fail():
        raise requests.Timeout("secret-must-not-escape")

    clock[0] = 120
    assert nba.cached(("test",), fail)[1] == "stale"
    assert nba.cached(("test",), fail)[1] == "stale"
    clock[0] = 22000
    assert nba.cached(("test",), fail) == (None, "unavailable")
    assert nba.cached(("test",), fail) == (None, "unavailable")  # cached failure metadata; value remains unknown


def test_stats_request_one_batch_explicit_current_season_and_timeout(monkeypatch):
    calls = []

    def endpoint(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            get_dict=lambda: {
                "resultSets": [
                    {
                        "name": "LeagueDashPlayerStats",
                        "headers": ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", "MIN", "PTS"],
                        "rowSet": [[123, "Example", 1610612737, 4, 30, 20]],
                    }
                ]
            }
        )

    monkeypatch.setattr(nba.leaguedashplayerstats, "LeagueDashPlayerStats", endpoint)
    assert nba.fetch_rates(2027)[0]["PTS"] == 20
    assert calls == [
        {"season": "2026-27", "per_mode_detailed": "PerGame", "season_type_all_star": "Regular Season", "timeout": 6}
    ]
    monkeypatch.setattr(nba, "_CACHE", {})
    result = nba.load(2027, need_schedule=False)
    assert len(calls) == 2
    assert result["schedule_status"] == "not_needed"


def test_cdn_failure_uses_explicit_season_schedule_endpoint(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(nba.requests, "get", fail)
    calls = []

    def endpoint(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(get_dict=schedule)

    monkeypatch.setattr(nba.scheduleleaguev2, "ScheduleLeagueV2", endpoint)
    assert nba.fetch_schedule(2027)["leagueSchedule"]["seasonYear"] == "2026-27"
    assert calls == [{"season": "2026-27", "timeout": 6}]
    with pytest.raises(ValueError, match="season mismatch"):
        nba.fetch_schedule(2026)


def test_upstream_failure_does_not_erase_espn_rates_or_schedule():
    player = {
        "name": "Example",
        "pro_team_id": 1,
        "current_rates": {"pts": 20},
        "current_games": 4,
        "prior_rates": None,
        "schedule": [{"date": "2026-10-31"}],
    }
    snapshot = {"teams": [{"roster": [player]}], "free_agents": [], "data_gaps": []}
    nba.enrich_players(
        snapshot, {"rates": [], "schedule": None, "rates_status": "unavailable", "schedule_status": "unavailable"}
    )
    assert player["current_rates"] == {"pts": 20}
    assert player["schedule"] == [{"date": "2026-10-31"}]
    assert len(snapshot["data_gaps"]) == 2


def test_empty_stats_and_schema_drift_are_failures(monkeypatch):
    def endpoint(**kwargs):
        return SimpleNamespace(
            get_dict=lambda: {"resultSets": [{"name": "LeagueDashPlayerStats", "headers": [], "rowSet": []}]}
        )

    monkeypatch.setattr(nba.leaguedashplayerstats, "LeagueDashPlayerStats", endpoint)
    with pytest.raises(ValueError, match="sample unavailable"):
        nba.fetch_rates(2027)
    monkeypatch.setattr(nba, "_CACHE", {})
    assert nba.load(2027, need_schedule=False)["rates_status"] == "unavailable"


def test_failed_resource_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})

    def fail():
        raise requests.Timeout()

    for year in range(2000, 2030):
        nba.cached(("rates", year), fail)
    assert len(nba._CACHE) == 12


def test_cdn_success_is_bounded_and_no_redirects(monkeypatch):
    import json

    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield json.dumps(schedule()).encode()

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(nba.requests, "get", get)
    assert nba.fetch_schedule(2027)["leagueSchedule"]["seasonYear"] == "2026-27"
    assert calls[0][1] == {"timeout": (3.05, 6), "allow_redirects": False, "stream": True}
