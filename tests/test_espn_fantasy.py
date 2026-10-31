"""Deterministic ESPN transport, normalization and authentication tests; no live credentials."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from nba_terminal.services import espn_fantasy as espn

FIXTURE = Path(__file__).parent / "fixtures" / "espn_fantasy_synthetic.json"
NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)


@pytest.fixture
def data():
    return json.loads(FIXTURE.read_text())


def normalized(data, **kwargs):
    return espn.normalize(
        data["league"], data["schedule"], data["pool"], data["cards"], data["transactions"], 1, now=NOW, **kwargs
    )


def test_nine_cat_totals_schedule_and_sample_rates(data):
    original = copy.deepcopy(data)
    result = normalized(data)
    assert data == original
    assert result["league"]["supported"] is True
    assert result["league"]["team_count"] == 14
    assert result["league"]["acquisition_settings"]["weekly_add_limit"] == 7
    assert result["league"]["lineup_slots"] == ["PG", "SG", "SF", "PF", "C", "UTIL", "UTIL"]
    assert result["opponent_team_id"] == 2
    assert result["comparison"]["team_id"] == 2
    rows = {row["key"]: row for row in result["comparison"]["categories"]}
    assert rows["to"]["state"] == "winning"
    assert rows["pts"]["state"] == "losing"
    assert rows["fg_pct"]["user"] == 0.5
    user = result["teams"][0]
    assert user["totals"]["fgm"] == 12
    assert user["season_acquisitions"] == 21
    assert user["weekly_used_adds"] is None and user["remaining_adds"] is None
    player = user["roster"][0]
    assert player["current_rates"]["pts"] == 20
    assert player["current_rates"]["fg_pct"] == 0.5
    assert player["current_rates"]["fga"] == 12
    assert player["current_rates"]["minutes"] == 32
    assert player["current_games"] == 2
    assert player["prior_games"] == 2
    assert player["today"] is True and player["remaining_games"] == 2
    assert player["locked"] is None
    assert len(result["matchup_history"]) == 7
    assert result["period"]["dates"] == ["2026-10-31", "2026-11-01"]
    assert result["fetched_at"] == NOW.isoformat()
    assert result["optimizer"]["status"] == "requires_inputs"
    assert result["optimizer"]["endpoint"] == "/api/fantasy/espn/plan"


def test_rostered_filter_waivers_and_duplicates(data):
    data["pool"]["players"] *= 2
    result = normalized(data)
    assert [p["id"] for p in result["free_agents"]] == ["100", "101"]
    assert result["free_agents"][0]["eligible"] is True
    assert result["free_agents"][1]["eligible"] is False
    assert result["free_agents"][1]["availability"] == "WAIVERS"


def test_private_ownership_comparison_and_validation(data):
    result = normalized(data, swid="{FIXTURE-OWNER-0001}", comparison=14)
    assert result["comparison"]["team_id"] == 14
    assert result["teams"][0]["ownership_verified"]
    assert not result["teams"][1]["ownership_verified"]
    with pytest.raises(espn.EspnError, match="does not own"):
        normalized(data, swid="fixture-owner-0002")
    with pytest.raises(espn.EspnError, match="not in this league"):
        normalized(data, comparison=999)
    with pytest.raises(espn.EspnError, match="Choose a team"):
        espn.validate_team(data["league"], 999, None)


def test_missing_data_never_becomes_zero_or_seven(data):
    data["schedule"] = {}
    data["league"]["settings"]["acquisitionSettings"] = {}
    data["league"]["schedule"][7]["home"].pop("cumulativeScore")
    result = normalized(data)
    assert result["league"]["acquisition_settings"]["weekly_add_limit"] is None
    assert result["teams"][0]["totals"] is None
    assert all(row["state"] == "unknown" for row in result["comparison"]["categories"])
    assert result["teams"][0]["roster"][0]["schedule"] is None
    assert result["teams"][0]["roster"][0]["remaining_games"] is None
    assert result["period"]["dates"] == []
    assert result["data_gaps"]


@pytest.mark.parametrize("value,per_day", [(None, False), (-1, False), (7, True), (7, None)])
def test_daily_unlimited_missing_cap_not_weekly(data, value, per_day):
    data["league"]["settings"]["acquisitionSettings"].update(
        matchupAcquisitionLimit=value, matchupLimitPerScoringPeriod=per_day
    )
    assert normalized(data)["league"]["acquisition_settings"]["weekly_add_limit"] is None


@pytest.mark.parametrize("scoring_type", ["ROTO", "H2H_POINTS", None])
def test_unsupported_scoring_remains_visible(data, scoring_type):
    data["league"]["settings"]["scoringSettings"]["scoringType"] = scoring_type
    result = normalized(data)
    assert not result["league"]["supported"]
    assert result["league"]["unsupported_reason"]
    assert len(result["teams"]) == 14


def test_weighted_percentages_zero_attempts_missing_and_finite():
    assert espn.stats({"13": 4, "14": 10, "19": 0.99})["fg_pct"] == 0.4
    assert espn.stats({"13": 0, "14": 0})["fg_pct"] is None
    assert espn.stats({"19": 0.3})["fg_pct"] == 0.3
    assert espn.stats({"0": float("nan"), "1": True, "2": "3"})["pts"] is None
    assert espn.stats(None) is None
    assert espn.compare_categories({"pts": 1}, {"pts": 1}, [{"key": "pts", "lower_is_better": False}], 2)["ties"] == 1


def test_sample_excludes_predictions_and_rollups(data):
    player = data["league"]["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]
    player["stats"][1]["statSourceId"] = 1
    assert espn.samples(player, 2027) == (None, None)
    player["stats"][1]["statSourceId"] = 0
    player["stats"][1]["statSplitTypeId"] = 1
    assert espn.samples(player, 2027) == (None, None)
    player["stats"][1]["statSplitTypeId"] = 0
    player["stats"][1]["stats"].pop("42")
    assert espn.samples(player, 2027) == (None, None)


class Reply:
    def __init__(self, status=200, payload=None, chunks=None):
        self.status_code = status
        self.payload = payload
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        return self.chunks if self.chunks is not None else [json.dumps(self.payload).encode()]


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "access_denied"),
        (403, "access_denied"),
        (404, "league_not_found"),
        (429, "rate_limited"),
        (500, "upstream_error"),
        (302, "upstream_error"),
    ],
)
def test_upstream_errors_static_and_safe(monkeypatch, status, code):
    monkeypatch.setattr(espn.requests, "get", lambda *a, **kw: Reply(status))
    with pytest.raises(espn.EspnError) as err:
        espn.EspnClient(123, 2027).get(["mSettings"])
    assert err.value.code == code


@pytest.mark.parametrize(
    "exc,code",
    [
        (requests.Timeout("private-cookie-must-not-escape"), "timeout"),
        (requests.ConnectionError("private-cookie-must-not-escape"), "network_error"),
    ],
)
def test_transport_exceptions_are_redacted(monkeypatch, exc, code):
    def get(*args, **kwargs):
        raise exc

    monkeypatch.setattr(espn.requests, "get", get)
    with pytest.raises(espn.EspnError) as err:
        espn.EspnClient(123, 2027).get([])
    assert err.value.code == code
    assert "private-cookie" not in str(err.value)


@pytest.mark.parametrize(
    "reply,code",
    [
        (Reply(chunks=[b"not json"]), "invalid_response"),
        (Reply(payload=[]), "schema_changed"),
        (Reply(chunks=[b"a" * 8_000_001]), "response_too_large"),
    ],
)
def test_payload_failures(monkeypatch, reply, code):
    monkeypatch.setattr(espn.requests, "get", lambda *a, **kw: reply)
    with pytest.raises(espn.EspnError) as err:
        espn.EspnClient(123, 2027).get([])
    assert err.value.code == code


def test_fixed_host_timeout_no_redirects_and_backend_cookies(monkeypatch, data):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Reply(payload=data["league"])

    monkeypatch.setattr(espn.requests, "get", get)
    client = espn.EspnClient(123, 2027, "fixture-owner-0001", "synthetic-not-a-secret")
    assert client.league()["id"] == 123
    client.get(["proTeamSchedules_wl"], season=True)
    assert calls[0][0] == espn.BASE + "/seasons/2027/segments/0/leagues/123"
    assert calls[1][0] == espn.BASE + "/seasons/2027"
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["timeout"] == (3.05, 12)
    assert calls[0][1]["cookies"]["espn_s2"] == "synthetic-not-a-secret"
    assert "synthetic-not" not in repr(client)
    client.clear()
    assert client.espn_s2 is None and client.swid is None
    data["league"]["seasonId"] = 2026
    with pytest.raises(espn.EspnError, match="identity"):
        client.league()


def test_snapshot_batches_and_optional_failures(monkeypatch, data):
    calls = []

    def get(self, views, filters=None, **kwargs):
        calls.append((views, filters, kwargs))
        if "proTeamSchedules_wl" in views:
            return data["schedule"]
        if "kona_player_info" in views:
            return data["pool"]
        if "kona_playercard" in views:
            return data["cards"]
        raise espn.EspnError("access_denied", "Safe error", 401)

    monkeypatch.setattr(espn.EspnClient, "get", get)
    result = espn.EspnClient(123, 2027).snapshot(data["league"], 1)
    assert len(calls) == 4
    assert len(calls[2][1]["players"]["filterIds"]["value"]) == 16
    assert calls[2][1]["players"]["filterStatsForTopScoringPeriodIds"]["additionalValue"] == ["002027", "002026"]
    assert result["transactions"] is None
    assert any("Transactions unavailable" in gap for gap in result["data_gaps"])


def test_unknown_or_inactive_slots_not_eligible_and_missing_period_unknown(data):
    data["pool"]["players"][0]["player"]["eligibleSlots"] = [12, 13, 99]
    result = normalized(data)
    assert result["free_agents"][0]["eligible"] is False
    data["league"]["settings"]["scheduleSettings"]["matchupPeriods"] = {}
    result = normalized(data)
    assert result["teams"][0]["roster"][0]["schedule"] is None
    assert result["teams"][0]["roster"][0]["remaining_games"] is None


def test_started_games_excluded_from_remaining_and_missing_samples_explicit(data):
    data["league"]["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]["stats"] = []
    result = espn.normalize(
        data["league"], data["schedule"], data["pool"], {}, {}, 1, now=datetime(2026, 11, 1, 1, tzinfo=timezone.utc)
    )
    player = result["teams"][0]["roster"][0]
    assert player["remaining_games"] == 1
    assert player["schedule"][0]["started"]
    assert player["current_rates"] is None
    assert any("samples are unavailable" in gap for gap in result["data_gaps"])
    assert any("attempts/makes" in gap for gap in result["data_gaps"])
