"""Observed public schedule; synthetic league/rates and NBA transports are labeled separately."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_nba as nba
from nba_terminal.services import fantasy_planner_adapter as adapter
from nba_terminal.services.fantasy_optimizer import _context, _describe_move, _forecast, _schedule_explanation
from tests.test_fantasy_integration import preferences
from tests.test_fantasy_optimizer import fixture, player, rates

REAL_LOAD = nba.load
MONDAY = datetime(2026, 11, 2, 17, tzinfo=timezone.utc)
OBSERVED = Path(__file__).parents[1] / "docs/evidence/v7-schedule/espn-season.response"


def observed():
    return json.loads(OBSERVED.read_text())


def synthetic_nba_transport():
    """Observed dates/opponents converted to a synthetic NBA shape/IDs, NOT an NBA observation."""
    rows = {}
    ids = {value: key for key, value in nba.NBA_TO_ESPN.items()}
    for team in observed()["settings"]["proTeams"]:
        for games in team["proGamesByScoringPeriod"].values():
            for g in games:
                rows[g["id"]] = {
                    "gameId": "002" + str(g["id"]),
                    "gameDateTimeUTC": datetime.fromtimestamp(g["date"] / 1000, timezone.utc).isoformat(),
                    "homeTeam": {"teamId": str(ids[g["homeProTeamId"]])},
                    "awayTeam": {"teamId": str(ids[g["awayProTeamId"]])},
                    "gameStatus": "1",
                    "postponedStatus": "A",
                }
    return {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [{"games": list(rows.values())}]}}


@pytest.fixture
def provider(monkeypatch):
    raw = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    raw["schedule"] = observed()
    league = raw["league"]
    league.update(scoringPeriodId=14)
    league["status"]["currentMatchupPeriod"] = 3
    league["settings"]["scheduleSettings"].update(periodTypeId=2, matchupPeriods={"3": [3]})
    league["settings"]["acquisitionSettings"].update(matchupAcquisitionLimit=2, matchupLimitPerScoringPeriod=False)
    league["settings"]["rosterSettings"]["lineupSlotCounts"] = {"11": 1, "12": 12}
    for team in league["teams"]:
        team["transactionCounter"]["matchupAcquisitionTotals"] = {"3": 0}
        for entry in team["roster"]["entries"]:
            entry["lineupSlotId"] = 11
            entry["playerPoolEntry"]["player"]["proTeamId"] = 11 if team["id"] == 1 else 2
    for match in league["schedule"]:
        match["matchupPeriodId"] = 3
        for side in (match.get("home", {}), match.get("away", {})):
            side["pointsByScoringPeriod"] = {}
            for value in side.get("cumulativeScore", {}).get("scoreByStat", {}).values():
                value["score"] = 0
    for entry in raw["pool"]["players"]:
        espn.player_body(entry)["proTeamId"] = 1
    rows = []
    entries = [e for t in league["teams"] for e in t["roster"]["entries"]] + raw["pool"]["players"]
    for entry in entries:
        p = espn.player_body(entry)
        p["injured"] = False
        p["injuryStatus"] = "ACTIVE"
        row = {field: 1.0 for field in nba.FIELDS}
        row.update(
            PLAYER_ID=300000 + p["id"],
            PLAYER_NAME=p["fullName"],
            TEAM_ABBREVIATION=nba.ESPN_TEAMS[p["proTeamId"]],
            TEAM_ID=next(k for k, v in nba.NBA_TO_ESPN.items() if v == p["proTeamId"]),
            GP=8,
            MIN=30,
            PTS=20 if p["id"] == 100 else 5,
            REB=5,
            AST=8 if p["id"] == 100 else 2,
            FGM=6,
            FGA=12,
            FTM=3,
            FTA=4,
        )
        rows.append(row)
    state = {"now": MONDAY, "nba": synthetic_nba_transport(), "failed": False}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return state["now"].astimezone(tz) if tz else state["now"].replace(tzinfo=None)

    def nba_endpoint(**kwargs):
        if state["failed"]:
            raise requests.Timeout("synthetic NBA outage")
        return SimpleNamespace(get_dict=lambda: copy.deepcopy(state["nba"]))

    def blocked_cdn(*args, **kwargs):
        raise requests.HTTPError("synthetic CDN 403")

    def get(self, views, *args, **kwargs):
        key = {
            "proTeamSchedules_wl": "schedule",
            "kona_player_info": "pool",
            "kona_playercard": "cards",
            "mTransactions2": "transactions",
        }.get(views[0], "league")
        return copy.deepcopy(raw[key])

    monkeypatch.setattr(nba, "load", REAL_LOAD)
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(nba, "datetime", Clock)
    monkeypatch.setattr(espn, "datetime", Clock)
    monkeypatch.setattr(nba, "fetch_rates", lambda year: copy.deepcopy(rows))
    monkeypatch.setattr(nba, "fetch_team_games", lambda year: [{"TEAM_ID": tid, "GP": 8} for tid in nba.NBA_TO_ESPN])
    monkeypatch.setattr(nba.requests, "get", blocked_cdn)
    monkeypatch.setattr(nba.scheduleleaguev2, "ScheduleLeagueV2", nba_endpoint)
    monkeypatch.setattr(espn.EspnClient, "get", get)

    def run():
        client = espn.EspnClient(123, 2027)
        snapshot = client.snapshot(copy.deepcopy(league), 1)
        prefs = preferences(snapshot) | {
            "weekly_add_limit": 2,
            "used_adds": 0,
            "available_adds": 2,
            "selected_categories": ["pts", "reb", "ast", "stl", "blk"],
        }
        return snapshot, adapter.plan_snapshot_waivers(snapshot, prefs, state["now"])

    return raw, state, run


def test_public_observed_full_week_three_four_and_future_sunday():
    games = espn.normalize_schedule(observed(), MONDAY)
    proof = nba.coverage(games, 2027, ["2026-11-02", "2026-11-08"])
    assert proof["complete"]

    def week(tid):
        return [g["date"] for g in games[tid] if "2026-11-02" <= g["date"] <= "2026-11-08"]

    assert week(11) == ["2026-11-02", "2026-11-04", "2026-11-07"]
    assert week(2) == ["2026-11-02", "2026-11-04", "2026-11-06", "2026-11-08"]


def test_real_provider_normalizer_adapter_optimizer_both_rosters_and_weighting(provider):
    _, _, run = provider
    snapshot, result = run()
    assert result["status"] == "ready", result["reasons"]
    assert snapshot["period"]["schedule_coverage"]["source"] == "nba_schedule"
    assert snapshot["period"]["dates"][-1] == "2026-11-08"
    baseline = result["baseline"]
    assert baseline["games_by_team"] == {"user": 3, "opponent": 4}
    assert baseline["actual_primitives"]["user"]["pts"] == 0
    assert baseline["remaining_primitives"]["user"]["pts"] == 15
    assert baseline["totals"]["pts"] == 15
    assert baseline["opponent_totals"]["pts"] == 20
    assert baseline["categories"]["fg_pct"]["opponent"] == 0.5
    assert baseline["categories"]["to"]["margin"] == 1  # Three TO beat four TO.
    assert result["actions"], result["reasons"]
    move = result["actions"][0]
    assert move["schedule_explanations"]["add"]["full_week_games"] == 4
    assert move["add_starts"] == 4 and move["drop_starts"] == 3
    assert move["gains"]["pts"] == 80 - 15
    assert result["projected"]["opponent_totals"] == baseline["opponent_totals"]
    for k, row in move["arithmetic"]["primitives"].items():
        assert row["net"] == pytest.approx(row["add"] - row["drop"] + row["spillover"])
        assert row["net"] == pytest.approx(result["projected"]["totals"][k] - baseline["totals"][k])


def test_verified_nba_replaces_cropped_existing_espn_team(provider):
    raw, _, run = provider
    for team in raw["schedule"]["settings"]["proTeams"]:
        if team["id"] == 1:
            team["proGamesByScoringPeriod"] = {k: v for k, v in team["proGamesByScoringPeriod"].items() if int(k) <= 16}
    snapshot, result = run()
    pickup = snapshot["free_agents"][0]
    assert pickup["remaining_games"] == 4
    assert pickup["schedule_source"] == "nba_schedule"
    assert result["actions"][0]["add_starts"] == 4
    assert snapshot["period"]["schedule_sources_consistent"] is False


def test_unavailable_nba_explicit_verified_espn_fallback(provider):
    _, state, run = provider
    state["failed"] = True
    snapshot, result = run()
    proof = snapshot["period"]["schedule_coverage"]
    assert proof["complete"] and proof["fallback"]
    assert proof["nba_status"] == "unavailable" and proof["source"] == "espn_schedule"
    assert result["baseline"]["games_by_team"] == {"user": 3, "opponent": 4}


def test_failed_both_sources_never_become_zero_week(provider):
    raw, state, run = provider
    state["failed"] = True
    raw["schedule"] = {}
    snapshot, result = run()
    assert snapshot["teams"][0]["roster"][0]["remaining_games"] is None
    assert result["status"] == "incomplete" and not result["actions"]
    assert snapshot["period"]["schedule_coverage"]["complete"] is False


def test_midweek_banked_actuals_separate_from_remaining_on_both_sides(provider):
    _, state, run = provider
    state["now"] = datetime(2026, 11, 5, 17, tzinfo=timezone.utc)
    snapshot, _ = run()
    for team in snapshot["teams"]:
        if team["id"] in (1, 2):
            totals = team["totals"] | {"pts": 47, "fgm": 7, "fga": 19}
            team["actuals"] = {"forecast_complete": True, "forecast_source": "espn_official", "forecast_totals": totals}
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), state["now"])
    baseline = result["baseline"]
    assert baseline["games_by_team"] == {"user": 1, "opponent": 2}
    assert baseline["actual_primitives"]["user"]["pts"] == 47
    assert baseline["totals"]["pts"] == 52 and baseline["opponent_totals"]["pts"] == 57
    assert baseline["categories"]["fg_pct"]["user"] == pytest.approx(13 / 31)
    assert baseline["categories"]["fg_pct"]["opponent"] == pytest.approx(19 / 43)


@pytest.mark.parametrize("usable", [0, 2, 3, 4])
def test_usable_counts_transaction_timing_distinct_from_lineup_block(provider, usable):
    _, _, run = provider
    snapshot, _ = run()
    prefs = preferences(snapshot) | {"selected_categories": ["pts", "reb", "ast", "stl", "blk"]}
    candidate = snapshot["free_agents"][0]
    candidate["earliest_add_date"] = "2026-11-06" if usable == 2 else "2026-11-04" if usable == 3 else "2026-11-02"
    if usable == 0:
        candidate.update(active=False, lineup_slot="IR")
    # Move effective date follows transaction timing while retaining a valid baseline roster.
    result = adapter.plan_snapshot_waivers(snapshot, prefs, MONDAY)
    if usable:
        move = result["actions"][0]
        explanation = move["schedule_explanations"]["add"]
        assert move["add_starts"] == usable
        assert explanation["full_week_games"] == 4 and explanation["remaining_games"] == 4
        assert explanation["eligible_games"] == usable
        assert all(e["reason"] == "before_transaction_effective_date" for e in explanation["exclusions"])
    else:
        assert not result["actions"]


def test_true_net_negative_and_spillover_reprojects_actual_slots():
    data = fixture()
    data.update(
        dates=["2026-11-01", "2026-11-02"],
        lineup_slots=["UTIL"],
    )
    data["margin_sd"] = {k: 0.05 if k.endswith("pct") else 100 for k in espn.CATEGORIES}
    data["players"] = [
        player("drop", "user", data["dates"], current_rates=rates(pts=20)),
        player("bench", "user", ["2026-11-02"], current_rates=rates(pts=10)),
        player("add", schedule=["2026-11-01"], current_rates=rates(pts=5)),
    ]
    context = _context(data)
    before = _forecast(context, [])
    action = {"date": "2026-11-01", "drop_id": "drop", "add_id": "add", "season_cost": 0}
    after = _forecast(context, [action])
    move = _describe_move(context, before, after, action, ["pts", "reb", "ast", "stl", "blk"])
    assert move["gains"]["pts"] == 5 + 10 - 40
    assert move["lineup_changes"]["recovered"] == [{"date": "2026-11-02", "player_id": "bench", "name": "bench"}]
    assert move["arithmetic"]["primitives"]["pts"]["spillover"] == 10


def test_cache_refresh_partial_stale_recovery_and_no_false_completion(provider, monkeypatch):
    raw, state, run = provider
    clock = [100.0]
    monkeypatch.setattr(nba.time, "monotonic", lambda: clock[0])
    snapshot, _ = run()
    assert snapshot["period"]["schedule_coverage"]["nba_status"] == "fresh"
    assert run()[0]["period"]["schedule_coverage"]["nba_status"] == "cached"
    original = copy.deepcopy(state["nba"])
    # Remove a real observed remaining ATL game from the synthetic NBA response.
    games = state["nba"]["leagueSchedule"]["gameDates"][0]["games"]
    games.pop(next(i for i, g in enumerate(games) if g["homeTeam"]["teamId"] == "1610612737"))
    clock[0] += 301
    snapshot, _ = run()
    proof = snapshot["period"]["schedule_coverage"]
    assert proof["nba_status"] == "stale" and proof["fallback"]
    assert proof["source"] == "espn_schedule" and proof["complete"]
    # Failure backoff still returns stale provenance rather than relabeling cached success.
    assert run()[0]["period"]["schedule_coverage"]["nba_status"] == "stale"
    raw["schedule"] = {}
    incomplete, result = run()
    assert not incomplete["period"]["schedule_coverage"]["complete"]
    assert result["status"] == "incomplete" and not result["actions"]
    state["nba"] = original
    clock[0] += 61
    recovered, _ = run()
    assert recovered["period"]["schedule_coverage"]["source"] == "nba_schedule"
    assert recovered["period"]["schedule_coverage"]["nba_status"] == "fresh"
    assert recovered["free_agents"][0]["remaining_games"] == 4


def test_ny_boundary_postponement_repeat_opponents_dedup_and_conflicting_ids():
    data = synthetic_nba_transport()
    rows = data["leagueSchedule"]["gameDates"][0]["games"]
    first = rows[0]
    # A repeated provider row must not create a fantasy start; same opponent on another date must survive.
    rows.append(copy.deepcopy(first))
    parsed = nba.schedule_games(data, 2027, MONDAY)
    assert nba.coverage(parsed, 2027)["complete"]
    assert all(len(games) == 80 for games in parsed.values())
    boundary = copy.deepcopy(first)
    boundary.update(gameId="002BOUNDARY", gameDateTimeUTC="2026-11-02T00:30:00Z")
    old_ppd = boundary | {"gameDateTimeUTC": "2026-11-01T00:30:00Z", "gameStatusText": "Postponed"}
    rows.extend([old_ppd, boundary, copy.deepcopy(boundary)])
    parsed = nba.schedule_games(data, 2027, datetime(2026, 11, 1, 23, tzinfo=timezone.utc))
    boundary_rows = [g for games in parsed.values() for g in games if g["game_id"] == "002BOUNDARY"]
    assert len(boundary_rows) == 2 and all(g["date"] == "2026-11-01" for g in boundary_rows)
    assert all(not g["started"] for g in boundary_rows)
    rows.append(boundary | {"gameDateTimeUTC": "2026-11-03T00:30:00Z"})
    assert not nba.coverage(nba.schedule_games(data, 2027, MONDAY), 2027)["complete"]


def test_unassigned_cup_window_and_partial_inventory_are_unknown():
    schedules = espn.normalize_schedule(observed(), MONDAY)
    assert not nba.coverage(schedules, 2027, ["2026-12-06"])["complete"]
    schedules[1] = schedules[1][:-1]
    assert 1 not in nba.coverage(schedules, 2027)["verified_team_ids"]


def test_lineup_blocked_is_not_transaction_timing(provider, monkeypatch):
    _, _, run = provider
    snapshot, _ = run()
    snapshot["league"]["lineup_slots"] = ["C"]
    snapshot["teams"][0]["roster"][0]["positions"] = ["C"]
    snapshot["teams"][1]["roster"][0]["positions"] = ["C"]
    snapshot["free_agents"][0]["positions"] = ["PG"]
    captured = []
    real_plan = adapter.plan_waivers

    def capture(payload):
        captured.append(payload)
        return real_plan(payload)

    monkeypatch.setattr(adapter, "plan_waivers", capture)
    adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), MONDAY)
    context = _context(captured[0])
    before = _forecast(context, [])
    action = {"date": "2026-11-02", "drop_id": "1", "add_id": "100", "season_cost": 0}
    after = _forecast(context, [action])
    proof = _schedule_explanation(context, after, "100", action["date"])
    assert proof["full_week_games"] == proof["remaining_games"] == proof["eligible_games"] == 4
    assert proof["usable_starts"] == 0
    assert {e["reason"] for e in proof["exclusions"]} == {"lineup_capacity_or_policy"}
    assert after["user_totals"]["pts"] - before["user_totals"]["pts"] < 0


def test_planner_clock_crossing_tipoff_requires_refresh_without_doublecount(provider):
    _, _, run = provider
    snapshot, _ = run()
    later = datetime(2026, 11, 3, 3, tzinfo=timezone.utc)
    result = adapter.plan_snapshot_waivers(snapshot, preferences(snapshot), later)
    assert result["status"] == "incomplete" and not result["actions"]
    proof = result["projection_metadata"]["newly_started:user"]
    assert proof["complete"] is False
    assert result["baseline"]["schedule_explanations"]["1"]["remaining_games"] == 2
    assert result["baseline"]["actual_primitives"]["user"]["pts"] == 0
    assert result["baseline"]["remaining_primitives"]["user"]["pts"] == 10


def test_opening_eighty_game_inventory_cannot_certify_post_cup_matchup():
    schedules = espn.normalize_schedule(observed(), MONDAY)
    proof = nba.coverage(schedules, 2027, ["2027-01-04", "2027-01-10"])
    assert not proof["complete"] and not proof["verified_team_ids"]


@pytest.mark.parametrize(
    "bad", [None, [], {"leagueSchedule": []}, {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [None]}}]
)
def test_malformed_schedule_shapes_fail_closed(bad):
    assert nba.schedule_games(bad, 2027, MONDAY) == {}
    with pytest.raises(ValueError, match="incomplete"):
        nba.validate_schedule(bad, 2027)
    assert espn.normalize_schedule(bad, MONDAY) == {}
    assert espn.completed_team_games(bad, 2027, MONDAY) == {}
