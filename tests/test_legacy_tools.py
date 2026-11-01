"""Provider-shaped parity fixtures; these tests make no live NBA requests."""

from __future__ import annotations

import asyncio
import math
import threading
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from nba_terminal.legacy_tools_api import create_legacy_tools_router
from nba_terminal.services import legacy_tools as tools
from nba_terminal.services import projections

ATL, BOS = 1610612737, 1610612738


def logs(points=None, player_id=1, team_id=ATL):
    points = points if points is not None else list(range(30, 10, -1))
    return pd.DataFrame(
        {
            "PLAYER_ID": player_id,
            "TEAM_ID": team_id,
            "PTS": points,
            "MIN": 30.0,
            "GAME_ID": [f"002260{i:04}" for i in range(len(points))],
            "GAME_DATE": pd.date_range(end="2026-10-30", periods=len(points))[::-1],
        }
    )


def schedule():
    return pd.DataFrame(
        [
            {
                "gameId": "0022600100",
                "gameDateEst": "2026-11-01T00:00:00",
                "homeTeam_teamId": ATL,
                "awayTeam_teamId": BOS,
                "gameStatusText": "7:00 pm ET",
            }
        ]
    )


def context():
    return {
        "def_rating": 115.0,
        "league_def_rating": 110.0,
        "pace": 102.0,
        "league_pace": 100.0,
        "rest_days": 2,
        "is_home": True,
    }


def result(frame, error=None):
    return frame, "2026-11-01T12:00:00Z", error


def test_original_predictor_exact_parity(monkeypatch):
    frame = logs()
    monkeypatch.setattr(projections, "fetch_player_game_log", lambda *a: frame)
    monkeypatch.setattr(projections, "fetch_matchup_context", lambda *a: context())
    original = projections.project_points("A", "ATL", "BOS", "2026-27", 36)
    actual = tools.points_projection(frame, 36, context())
    for key in (
        "projection",
        "season_avg",
        "last_5",
        "last_10",
        "avg_minutes",
        "minute_factor",
        "defense_adjustment",
        "pace_adjustment",
        "rest_adjustment",
        "home_adjustment",
    ):
        assert actual[key] == pytest.approx(original[key])
    assert actual["baseline"] == pytest.approx(0.45 * 20.5 + 0.35 * 28 + 0.20 * 25.5)
    assert actual["minutes_adjustment"] == pytest.approx(actual["baseline"] * 0.2)


def test_predictor_small_samples_missing_context_and_floor():
    actual = tools.points_projection(logs([10, None, 20]), 30, context())
    assert actual["last_5"] == actual["last_10"] == 15
    assert actual["valid_games"] == 2
    assert actual["last_5_fallback"] and actual["last_10_fallback"]
    missing = tools.points_projection(logs([1]), 30, {})
    assert missing["projection"] is None and missing["rest_adjustment"] is None
    assert (
        tools.points_projection(logs([0]), 30, {**context(), "rest_days": 0, "is_home": False, "def_rating": 1})[
            "projection"
        ]
        == 0
    )
    with pytest.raises(ValueError, match="No valid"):
        tools.points_projection(logs([None]), 30, context())
    no_minutes = tools.points_projection(logs([5]).drop(columns="MIN"), 30, context())
    assert no_minutes["minutes_estimated"] and no_minutes["minute_factor"] == 1
    assert tools.points_projection(logs([5]).assign(MIN=0), 30, context())["minutes_estimated"]


def test_number_and_chronology():
    assert tools.number("NaN") is None
    assert tools.number("bad") is None
    assert tools.number(None) is None
    assert tools.number(0) == 0
    frame = logs([10, 20, 30])
    frame = pd.concat([frame.iloc[::-1], frame.head(1)])
    actual = tools.ordered_logs(frame, "2026-10-30")
    assert list(actual.PTS) == [20, 30]  # selected date and duplicate excluded
    assert tools.ordered_logs(pd.DataFrame()).empty
    with pytest.raises(ValueError, match="chronology"):
        tools.ordered_logs(pd.DataFrame({"PTS": [1]}))


def test_cv_window_before_null_removal_sample_sd_and_exclusions():
    frames = [
        logs([10, None, 20, 30, 40, 999], 1),
        logs([10] * 5, 2),
        logs([0] * 5, 3),
        logs([1, 2], 4),
        logs([None] * 5, 5),
        logs([10, None, None, None, None], 6),
    ]
    roster = pd.DataFrame({"PLAYER_ID": range(1, 7), "PLAYER": list("ABCDEF")})
    actual = tools.consistency_rows(roster, pd.concat(frames), "PTS", 5)
    assert len(actual["rows"]) == 1
    row = actual["rows"][0]
    assert row["valid_games"] == 4 and row["window"] == 5
    assert row["mean"] == 25
    assert row["sd"] == pytest.approx(math.sqrt(500 / 3))
    assert row["cv"] == pytest.approx(math.sqrt(500 / 3) / 25)
    assert actual["excluded"] == {"insufficient_games": 1, "missing_stat": 1, "zero_mean_or_sd": 3}
    missing = tools.consistency_rows(roster.head(1), frames[0].drop(columns="PTS"), "PTS", 5)
    assert missing["excluded"]["missing_stat"] == 1


def test_cv_ascending_top15():
    roster = pd.DataFrame({"PLAYER_ID": range(1, 21), "PLAYER": [f"P{i}" for i in range(20)]})
    frames = [logs([10, 10, 10, 10, 10 + i], i) for i in range(1, 21)]
    rows = tools.consistency_rows(roster, pd.concat(frames), "PTS", 5)
    assert len(rows["rows"]) == 15 and rows["ranked_players"] == 20
    assert [r["cv"] for r in rows["rows"]] == sorted(r["cv"] for r in rows["rows"])


@pytest.mark.parametrize("stat", ["FG_PCT", "OPP_FG_PCT"])
def test_defense_zone_schema_missing_unknown_corner_mean_and_league_context(stat):
    overall = pd.DataFrame(
        {"TEAM_ID": [ATL, BOS, 1], "OPP_FG_PCT": [0.45, 0.50, None], "OPP_FG3_PCT": [0.30, 0.40, None]}
    )
    zones = pd.DataFrame(
        [[ATL, 0.50, 0.20, 0.60]],
        columns=pd.MultiIndex.from_tuples(
            [("", "TEAM_ID"), ("Restricted Area", stat), ("Left Corner 3", stat), ("Right Corner 3", stat)]
        ),
    )
    actual = tools.defense_rows(overall, zones)
    assert actual["rows"][0]["Corner 3"] == 0.4
    assert actual["rows"][0]["Mid-Range"] is None
    assert actual["rows"][1]["Restricted Area"] is None
    assert actual["rows"][2]["tier"] == "Unknown" and actual["rows"][2]["rank"] is None
    assert actual["league_means"]["OPP_FG_PCT"] == 0.475
    assert actual["league_counts"]["OPP_FG_PCT"] == 2
    assert actual["league_means"]["Mid-Range"] is None
    zones.iloc[0, -1] = None
    assert tools.defense_rows(overall, zones)["rows"][0]["Corner 3"] is None
    assert tools.defense_rows(overall, zones.droplevel(0, axis=1))["rows"][0]["Restricted Area"] is None
    assert tools.defense_rows(pd.DataFrame(), pd.DataFrame())["rows"] == []


def test_slate_filters_formula_sort_and_partial_counts():
    games = tools.LegacyToolsService._games(schedule(), "2026-11-01")
    dashboard = pd.DataFrame(
        {
            "PLAYER_ID": range(1, 8),
            "PLAYER_NAME": list("ABCDEFG"),
            "TEAM_ID": [ATL, BOS, ATL, ATL, ATL, ATL, 1],
            "MIN": [30, 25, 24.9, 30, 30, 30, 30],
            "GP": [10, 5, 10, 4, 10, 10, 10],
            "PTS": [10.0, 30.0, 20.0, 20.0, 20.0, 20.0, 20.0],
        }
    )
    frame = pd.concat([logs([20] * 10, 1), logs([10] * 5, 2), logs([5] * 2, 6)])
    actual = tools.slate_rows(dashboard, frame, games)
    assert actual["qualified_players"] == 4
    assert actual["evaluated_players"] == 2
    assert actual["missing_players"] == actual["insufficient_players"] == 1
    assert actual["rows"][0]["player"] == "B"
    assert actual["rows"][0]["projection"] == pytest.approx(13)
    assert actual["rows"][0]["difference"] == -17
    assert actual["rows"][1]["projection"] == pytest.approx(18.5)
    # Original checks returned game count, then takes valid points; disclose reduced L5 count.
    sparse = tools.slate_rows(dashboard.head(1), logs([20, None, None, None, None]), games)
    assert sparse["rows"][0]["recent_valid_games"] == 1
    assert tools.slate_rows(dashboard.head(1), logs([10] * 5), games)["rows"] == []


def test_picks_search_read_only_traversal_and_symlink(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    content = "# Historical opinion\nCurry <script>alert(1)</script>"
    path = notes / "10_31_2026.MD"
    path.write_text(content)
    (notes / "11_01_2026.md").write_text("different")
    outside = tmp_path / "11_02_2026.md"
    outside.write_text("private")
    (notes / outside.name).symlink_to(outside)
    service = tools.LegacyToolsService(notes)
    assert len(service.picks("", None)["files"]) == 2
    assert service.picks("CURRY", None)["files"][0]["filename"] == path.name
    assert service.picks("", path.name)["content"] == content
    for name in ("../11_02_2026.md", "11_02_2026.md", str(outside), "missing.md"):
        with pytest.raises(ValueError, match="read-only"):
            service.picks("", name)
    assert path.read_text() == content
    assert service.picks("not found", None)["files"] == []


def test_catalog_is_installed_metadata_without_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("must not execute endpoints")

    monkeypatch.setattr(tools.playergamelogs.PlayerGameLogs, "__init__", forbidden)
    actual = tools.LegacyToolsService().catalog("PLAYER_ID")
    assert actual["metadata_only"] and actual["endpoints"] and actual["version"]
    assert any(r["datasets"] for r in actual["endpoints"])
    assert all(isinstance(r["datasets"], dict) for r in actual["endpoints"])
    assert tools.LegacyToolsService().catalog("definitely_no_endpoint")["endpoints"] == []


def test_resource_deduplication_cooldown_and_bounded_cache(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(tools.time, "monotonic", lambda: clock[0])
    service = tools.LegacyToolsService()
    calls = []

    def fetch():
        calls.append(1)
        return logs()

    first = service._resource(("test",), fetch)
    assert service._resource(("test",), fetch)[0] is first[0]
    assert len(calls) == 1
    clock[0] += 901
    service._resource(("test",), fetch)
    assert len(calls) == 2

    def failure():
        calls.append(1)
        raise RuntimeError("private internal diagnostic")

    value = service._resource(("failed",), failure)
    assert value[2] == "failed unavailable (RuntimeError); retry shortly."
    service._resource(("failed",), failure)
    assert len(calls) == 3
    clock[0] += 31
    service._resource(("failed",), failure)
    assert len(calls) == 4
    for i in range(65):
        service._resource(("bound", i), lambda: None)
    assert len(service._cache) == 64


def test_batched_endpoint_arguments_and_resource_cache(monkeypatch):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(get_data_frames=lambda: [logs().assign(PLAYER_NAME="A", PLAYER="A", GP=20)])

    monkeypatch.setattr(tools.playergamelogs, "PlayerGameLogs", fake)
    monkeypatch.setattr(tools.leaguedashplayerstats, "LeagueDashPlayerStats", fake)
    monkeypatch.setattr(tools.commonteamroster, "CommonTeamRoster", fake)
    monkeypatch.setattr(tools.leaguedashteamshotlocations, "LeagueDashTeamShotLocations", fake)
    monkeypatch.setattr(tools.leaguedashteamstats, "LeagueDashTeamStats", fake)
    service = tools.LegacyToolsService()
    for name in ("logs", "players", "roster", "zones", "advanced", "overall"):
        service._frame(name, "2026-27", "Playoffs", "2026-11-01", ATL)
        service._frame(name, "2026-27", "Playoffs", "2026-11-01", ATL)
    assert len(calls) == 6
    assert calls[0]["season_nullable"] == "2026-27"
    assert calls[0]["season_type_nullable"] == "Playoffs"
    assert calls[0]["date_to_nullable"] == "2026-10-31"
    assert "player_id_nullable" not in calls[0]  # league-wide, no N-player loop
    assert all(c["timeout"] == 12 for c in calls)
    assert calls[4]["measure_type_detailed_defense"] == "Advanced"


def test_service_success_and_partial_states(monkeypatch):
    service = tools.LegacyToolsService()
    roster = pd.DataFrame({"PLAYER_ID": [1], "PLAYER": ["A"]})
    dashboard = pd.DataFrame(
        {"PLAYER_ID": [1], "PLAYER_NAME": ["A"], "TEAM_ID": [ATL], "MIN": [30], "GP": [20], "PTS": [10]}
    )
    advanced = pd.DataFrame({"TEAM_ID": [ATL, BOS], "DEF_RATING": [110, 114], "PACE": [100, 102]})
    frames = {
        "logs": logs(),
        "roster": roster,
        "players": dashboard,
        "advanced": advanced,
        "overall": pd.DataFrame({"TEAM_ID": [ATL], "OPP_FG_PCT": [0.45]}),
        "zones": pd.DataFrame(),
    }
    monkeypatch.setattr(service, "_frame", lambda name, *a, **kw: result(frames[name]))
    monkeypatch.setattr(service, "_schedule", lambda *a: result(schedule()))
    assert service.consistency("2026-27", "Regular Season", ATL, "PTS", 5)["rows"]
    assert service.defense("2026-27", "Regular Season")["state"] == "partial"
    assert service.slate("2026-27", "Regular Season", "2026-11-01")["rows"]
    assert service.slate("2026-27", "Playoffs", "2026-11-01")["state"] == "empty"
    actual = service.predictor("2026-27", "Regular Season", 1, ATL, BOS, 32, "2026-11-01", {})
    assert actual["projection"] is not None and actual["context"]["is_home"] is True
    assert actual["context"]["rest_days"] == 1
    assert actual["context"]["league_def_rating"] == 112
    actual = service.predictor("2026-27", "Regular Season", 1, ATL, BOS, 32, "2026-11-01", {"rest_days": 3})
    assert actual["context_sources"]["rest_days"] == "User estimate override"
    frames["advanced"] = pd.DataFrame()
    actual = service.predictor("2026-27", "Regular Season", 1, ATL, BOS, 32, "2026-11-01", {})
    assert actual["projection"] is None and actual["state"] == "partial"
    frames["logs"] = pd.DataFrame()
    assert service.predictor("2026-27", "Regular Season", 1, ATL, BOS, 32, "2026-11-01", {})["state"] == "empty"
    assert service.consistency("2026-27", "Regular Season", ATL, "PTS", 5)["state"] == "empty"
    assert service.slate("2026-27", "Regular Season", "2026-11-01")["state"] == "partial"
    monkeypatch.setattr(service, "_frame", lambda *a, **kw: result(pd.DataFrame(), "logs unavailable"))
    assert service.consistency("2026-27", "Regular Season", ATL, "PTS", 5)["state"] == "error"
    assert service.defense("2026-27", "Regular Season")["state"] == "error"
    assert service.slate("2026-27", "Regular Season", "2026-11-01")["state"] == "error"
    monkeypatch.setattr(service, "_schedule", lambda *a: result(pd.DataFrame(), "schedule unavailable"))
    assert service.slate("2026-27", "Regular Season", "2026-11-01")["state"] == "error"


def test_meta_offline_and_schedule_cache(monkeypatch):
    monkeypatch.setattr(tools.game_center, "nba_today", lambda: date(2026, 11, 1))
    calls = []
    monkeypatch.setattr(tools.game_center, "fetch_season_schedule", lambda season: calls.append(season) or schedule())
    service = tools.LegacyToolsService()
    assert service.meta()["season"] == "2026-27"
    assert service.meta()["players"] and service.meta()["teams"]
    service._schedule("2026-27")
    service._schedule("2026-27")
    assert calls == ["2026-27"]


def test_router_contract_validation_and_worker_injection(tmp_path):
    service = tools.LegacyToolsService(tmp_path)
    invocations = []

    async def runner(key, ttl, function, *args):
        event_thread = threading.get_ident()

        def call():
            assert threading.get_ident() != event_thread
            return function(*args)

        invocations.append((key, ttl, args))
        try:
            return await asyncio.to_thread(call)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    app = FastAPI()
    app.include_router(create_legacy_tools_router(runner, service))
    with TestClient(app) as client:
        assert client.get("/api/tools/meta").status_code == 200
        assert client.get("/api/tools/picks?q=x").json()["files"] == []
        assert client.get("/api/tools/picks", params={"filename": "../a.md"}).status_code == 400
        assert client.get("/api/tools/catalog?q=PlayerGameLogs").json()["endpoints"]
        calls_before = len(invocations)
        invalid = [
            "defense?season=2026-99",
            "defense?season=1995-96",
            "defense?season=2026-27&phase=bad",
            "consistency?season=2026-27&team_id=1",
            f"consistency?season=2026-27&team_id={ATL}&window=7",
            "slate?season=2026-27&day=not-a-date",
            f"predictor?season=2026-27&player_id=1&team_id={ATL}&opponent_id={ATL}&minutes=32&day=2026-11-01",
            f"predictor?season=2026-27&player_id=1&team_id={ATL}&opponent_id={BOS}&minutes=nan&day=2026-11-01",
        ]
        for path in invalid:
            assert client.get("/api/tools/" + path).status_code in {400, 422}, path
        assert len(invocations) == calls_before
        # Integer query windows must parse, and all routes use the injected worker.
        service.consistency = lambda *args: {"rows": [], "args": args}
        response = client.get(f"/api/tools/consistency?season=2026-27&team_id={ATL}&window=15")
        assert response.status_code == 200 and response.json()["args"][-1] == 15
        service.defense = lambda *args: {"state": "partial"}
        assert client.get("/api/tools/defense?season=2026-27").json()["state"] == "partial"
        service.slate = lambda *args: {"date": args[-1]}
        assert client.get("/api/tools/slate?season=2026-27&day=2026-11-01").json()["date"] == "2026-11-01"
        service.predictor = lambda *args: {"overrides": args[-1]}
        response = client.get(
            f"/api/tools/predictor?season=2026-27&player_id=1&team_id={ATL}&opponent_id={BOS}&minutes=32&day=2026-11-01&is_home=false&rest_days=0"
        )
        assert response.json()["overrides"]["is_home"] is False
        assert response.json()["overrides"]["rest_days"] == 0


def test_schema_loss_is_an_explicit_resource_failure(monkeypatch):
    def fake(**kwargs):
        return SimpleNamespace(get_data_frames=lambda: [pd.DataFrame({"wrong_schema": [1]})])

    monkeypatch.setattr(tools.playergamelogs, "PlayerGameLogs", fake)
    monkeypatch.setattr(tools.leaguedashplayerstats, "LeagueDashPlayerStats", fake)
    monkeypatch.setattr(tools.commonteamroster, "CommonTeamRoster", fake)
    service = tools.LegacyToolsService()
    for resource in ("logs", "players", "roster"):
        frame, _, error = service._frame(resource, "2026-27", "Regular Season")
        assert frame.empty and "unavailable (ValueError)" in error


def test_zero_attempt_zones_unknown_and_total_slate_log_failure(monkeypatch):
    overall = pd.DataFrame({"TEAM_ID": [ATL], "OPP_FG_PCT": [0.45]})
    zones = pd.DataFrame(
        [[ATL, 0, 0]],
        columns=pd.MultiIndex.from_tuples(
            [("", "TEAM_ID"), ("Restricted Area", "OPP_FG_PCT"), ("Restricted Area", "OPP_FGA")]
        ),
    )
    assert tools.defense_rows(overall, zones)["rows"][0]["Restricted Area"] is None
    service = tools.LegacyToolsService()
    dashboard = pd.DataFrame(
        {"PLAYER_ID": [1], "PLAYER_NAME": ["A"], "TEAM_ID": [ATL], "MIN": [30], "GP": [5], "PTS": [20]}
    )
    monkeypatch.setattr(service, "_schedule", lambda *a: result(schedule()))
    monkeypatch.setattr(
        service,
        "_frame",
        lambda name, *a: result(dashboard) if name == "players" else result(pd.DataFrame(), "logs unavailable"),
    )
    actual = service.slate("2026-27", "Regular Season", "2026-11-01")
    assert actual["qualified_players"] == actual["missing_players"] == 1
    assert actual["evaluated_players"] == 0 and actual["state"] == "partial"
