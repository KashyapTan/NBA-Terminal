"""Primary-source boundary regressions; all account/provider payloads are synthetic."""

import copy
from datetime import timedelta

import pytest

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_actuals as actuals
from nba_terminal.services import fantasy_planner_adapter as adapter
from tests.test_fantasy_integration import preferences
from tests.week_reset_fixture import NOW, new_week_payload


def normalized():
    data = new_week_payload()
    result = espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)
    for team in result["teams"]:
        team["actuals"] = actuals.reconstruct(
            team["id"],
            {},
            {},
            {},
            {},
            team["totals"],
            result["fetched_at"],
            no_started_games=result["period"]["no_started_games_verified"],
        )
    return result


def declaration(snapshot):
    team = snapshot["teams"][0]
    return {
        "league_id": snapshot["league"]["id"],
        "season_id": snapshot["league"]["season_id"],
        "team_id": 1,
        "matchup_period_id": 3,
        "used": 0,
        "confirmed_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "snapshot_at": snapshot["fetched_at"],
        "roster_ids": sorted(p["id"] for p in team["roster"]),
        "season_acquisitions": team["season_acquisitions"],
        "source": "explicit current user declaration",
    }


def prefs(snapshot):
    return preferences(snapshot) | {
        "user_confirmed_counts": False,
        "matchup_add_limit_fallback": 7,
        "usage_declaration": declaration(snapshot),
    }


@pytest.mark.parametrize(
    "rate,days,expected", [(1, 7, 7), (4 / 7, 7, 4), (1, 6, 6), (1, 13, 13), (0.5, 7, 4), (7, 7, 49)]
)
def test_espn_prorated_matchup_allowance(rate, days, expected):
    data = new_week_payload()
    raw = data["league"]
    raw["settings"]["acquisitionSettings"]["matchupAcquisitionLimit"] = rate
    periods = list(range(13, 13 + days))
    raw["settings"]["scheduleSettings"]["matchupPeriods"]["3"] = periods
    # Extend the source schedule with complete game days, preserving the real daily-period join.
    for team in data["schedule"]["settings"]["proTeams"]:
        first = team["proGamesByScoringPeriod"]["13"][0]
        team["proGamesByScoringPeriod"] = {
            str(p): [first | {"date": first["date"] + (p - 13) * 86400000}] for p in periods
        }
    snapshot = espn.normalize(raw, data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)
    settings = snapshot["league"]["acquisition_settings"]
    assert settings["weekly_add_limit"] == expected
    assert settings["daily_add_limit"] is None
    assert settings["reported_limit_scope"] == "matchup_game_day_rate"


def test_game_day_helper_off_day_empty_array_fallback_and_partial_inventory():
    data = new_week_payload()["schedule"]
    assert espn.matchup_acquisition_days(data, list(range(13, 20))) == 7
    for team in data["settings"]["proTeams"]:
        del team["proGamesByScoringPeriod"]["15"]
    assert espn.matchup_acquisition_days(data, list(range(13, 20))) == 6
    data["settings"]["proTeams"][0]["proGamesByScoringPeriod"]["15"] = []  # JS arrays are truthy.
    assert espn.matchup_acquisition_days(data, list(range(13, 20))) == 7
    for team in data["settings"]["proTeams"]:
        team["proGamesByScoringPeriod"] = {}
    assert espn.matchup_acquisition_days(data, list(range(13, 20))) == 7
    data["settings"]["proTeams"].pop()
    assert espn.matchup_acquisition_days(data, list(range(13, 20))) is None


@pytest.mark.parametrize(
    "mapping,value,source",
    [
        ({"3": 0}, 0, "espn_matchup_acquisition_totals"),
        ({"3": 2}, 2, "espn_matchup_acquisition_totals"),
        ({"2": 6}, 0, "espn_sparse_matchup_map_zero"),
        ({}, 0, "espn_sparse_matchup_map_zero"),
        (None, None, None),
        ({"3": False}, None, "invalid_matchup_acquisition_map"),
        ({"2": -1}, None, "invalid_matchup_acquisition_map"),
    ],
)
def test_current_matchup_not_daily_or_previous_week(mapping, value, source):
    team = {"transactionCounter": {"matchupAcquisitionTotals": mapping, "acquisitions": 99}}
    assert espn.matchup_usage(team, 3) == (value, source)
    assert espn.matchup_usage(team, None) == (None, None)


def test_exact_new_week_user_7_zero_missing_ledger_produces_full_real_plan():
    snapshot = normalized()
    assert snapshot["period"]["scoring_period_id"] == 13
    assert snapshot["period"]["matchup_period_id"] == 3
    assert snapshot["teams"][0]["weekly_used_adds"] is None
    assert snapshot["period"]["no_started_games_verified"] is True
    result = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert result["evaluation_state"] == "confirmed_ordered_plan", result
    assert result["recommended_plan"]["budget_before"] == 7
    assert result["plan"] and result["remaining_adds"] >= 0
    assert len(result["baseline"]["categories"]) == 9
    assert result["acquisition_budget"]["usage_source"] == "scoped user-declared current matchup usage"
    for move in result["plan"]:
        assert len(move["arithmetic"]["primitives"]) == 11
        for row in move["arithmetic"]["primitives"].values():
            assert row["net"] == pytest.approx(row["add"] - row["drop"] + row["spillover"])


@pytest.mark.parametrize(
    "change", ["refresh", "positive", "explicit_zero", "roster", "aggregate", "expiry", "season", "team", "matchup"]
)
def test_declaration_refresh_reconciliation_and_scope(change):
    snapshot = normalized()
    preferences = prefs(snapshot)
    if change == "refresh":
        snapshot["fetched_at"] = (NOW + timedelta(seconds=10)).isoformat()
    if change in ("positive", "explicit_zero"):
        snapshot["teams"][0].update(
            weekly_used_adds=2 if change == "positive" else 0,
            weekly_usage_complete=True,
            weekly_usage_source="espn_matchup_acquisition_totals",
            remaining_adds=5 if change == "positive" else 7,
        )
    if change == "roster":
        snapshot["teams"][0]["roster"].pop()
    if change == "aggregate":
        snapshot["teams"][0]["season_acquisitions"] += 1
    if change == "season":
        snapshot["league"]["season_id"] += 1
    if change == "team":
        snapshot["selected_team_id"] = 2
    if change == "matchup":
        snapshot["period"]["matchup_period_id"] += 1
    result = adapter.plan_snapshot_waivers(
        snapshot, preferences, NOW + timedelta(hours=2) if change == "expiry" else NOW
    )
    if change in ("refresh", "positive", "explicit_zero"):
        assert result["acquisition_budget"]["used"] == (2 if change == "positive" else 0)
        assert result["acquisition_budget"]["remaining"] == (5 if change == "positive" else 7)
        if change != "refresh":
            assert "usage_declaration" not in result["provenance"]
    else:
        assert not result["plan"]


@pytest.mark.parametrize("limit,used,expected", [(0, None, 0), (2, 1, 1), (2, None, None), (-1, None, 7)])
def test_season_budget_independent_of_matchup_scaling(limit, used, expected):
    snapshot = normalized()
    snapshot["league"]["acquisition_settings"]["season_add_limit"] = limit
    snapshot["teams"][0]["season_counted_acquisitions"] = used
    result = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert result["recommended_plan"]["budget_before"] == expected


def test_no_started_games_does_not_fabricate_ownership_or_mask_unknown_schedule():
    snapshot = normalized()
    assert snapshot["teams"][0]["actuals"]["nba_derived"]["expected_player_games"] == 0
    assert snapshot["teams"][0]["actuals"]["forecast_complete"]
    totals = snapshot["teams"][0]["totals"]
    unknown = actuals.reconstruct(1, {13: "2026-11-02"}, {}, {}, {}, totals, NOW.isoformat())
    assert unknown["nba_derived"]["expected_player_games"] is None
    assert unknown["forecast_source"] == "espn_official"
    assert unknown["forecast_complete"]


def test_rollover_between_base_and_counter_reloads_whole_context_once(monkeypatch):
    data = new_week_payload()
    old = copy.deepcopy(data["league"])
    old["status"]["currentMatchupPeriod"] = 2
    calls = []
    original = espn.EspnClient.snapshot

    def get(self, views, *args, **kwargs):
        calls.append(views)
        if views == ["mTeam"]:
            return data["league"]
        return {}

    def fresh(self):
        calls.append("full_league")
        return data["league"]

    # Stop only after the actual rollover path has requested a complete replacement.
    def snapshot(self, raw, selected, comparison=None, *, _context_retry=False):
        if _context_retry:
            assert raw["status"]["currentMatchupPeriod"] == 3
            assert selected == 1
            return {"bounded_reloaded": True}
        return original(self, raw, selected, comparison)

    monkeypatch.setattr(espn.EspnClient, "get", get)
    monkeypatch.setattr(espn.EspnClient, "league", fresh)
    monkeypatch.setattr(espn.EspnClient, "snapshot", snapshot)
    assert espn.EspnClient(604550749, 2027).snapshot(old, 1) == {"bounded_reloaded": True}
    assert calls == [["mTeam"], "full_league"]


def test_independent_daily_constraint_needs_explicit_subset_evidence():
    snapshot = normalized()
    settings = snapshot["league"]["acquisition_settings"]
    settings["daily_add_limit"] = 7
    unknown = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert not unknown["plan"]
    settings["daily_matchup_subset_verified"] = True
    proven = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert proven["plan"]
    settings["daily_add_limit"] = 1
    bounded = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert bounded["plan"]
    assert len({move["date"] for move in bounded["plan"]}) == len(bounded["plan"])


@pytest.mark.parametrize(
    "counter",
    [
        None,
        [],
        {"matchupAcquisitionTotals": None},
        {"matchupAcquisitionTotals": {"4": 0}},
        {"matchupAcquisitionTotals": {"3": 0.5}},
    ],
)
def test_corrupt_counter_is_unknown_not_zero_or_normalizer_crash(counter):
    data = new_week_payload()
    data["league"]["teams"][0]["transactionCounter"] = counter
    snapshot = espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)
    assert snapshot["teams"][0]["weekly_used_adds"] is None
    assert snapshot["teams"][0]["season_counted_acquisitions"] is None


def test_partial_nba_schedule_cannot_erase_verified_espn_current_week():
    from tests.fantasy_v2_fixture import nba_schedule_payload

    data = new_week_payload()
    snapshot = espn.normalize(
        data["league"],
        data["schedule"],
        data["pool"],
        data["cards"],
        {},
        1,
        now=NOW,
        nba={"schedule": nba_schedule_payload(), "schedule_status": "fresh"},
    )
    assert snapshot["period"]["dates"] == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
        "2026-11-07",
        "2026-11-08",
    ]
    assert snapshot["teams"][0]["roster"][0]["remaining_games"] == 7


def test_stale_previous_week_daily_context_cannot_confirm_current_counter():
    data = new_week_payload()
    data["league"]["scoringPeriodId"] = 10
    data["league"]["teams"][0]["transactionCounter"] = {"matchupAcquisitionTotals": {"3": 0}}
    snapshot = espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)
    assert snapshot["period"]["context_verified"] is False
    assert snapshot["period"]["calendar_verified"] is False
    assert snapshot["teams"][0]["weekly_used_adds"] is None
    assert not adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)["plan"]


def test_optional_nba_history_failure_keeps_complete_official_basis_and_full_plan():
    snapshot = normalized()
    for team in snapshot["teams"]:
        team["actuals"] = actuals.reconstruct(
            team["id"], {13: "2026-11-02"}, {}, {}, {}, team["totals"], snapshot["fetched_at"]
        )
        assert team["actuals"]["forecast_source"] == "espn_official"
        assert team["actuals"]["nba_derived"]["expected_player_games"] is None
    result = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert result["evaluation_state"] == "confirmed_ordered_plan"
    assert result["plan"]


def test_incomplete_league_game_day_coverage_uses_explicit_cap_without_inventing_api_cap():
    data = new_week_payload()
    data["schedule"]["settings"]["proTeams"].pop()
    snapshot = espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)
    assert snapshot["league"]["acquisition_settings"]["weekly_add_limit"] is None
    assert not snapshot["period"]["no_started_games_verified"]
    result = adapter.plan_snapshot_waivers(snapshot, prefs(snapshot), NOW)
    assert result["acquisition_budget"]["matchup_cap"] == 7
    assert result["acquisition_budget"]["cap_source"] == "scoped user-declared matchup cap"
    assert result["plan"]


def test_review_partial_current_nba_schedule_cannot_erase_started_espn_games_or_certify_zero():
    from tests.fantasy_v2_fixture import nba_schedule_payload

    data = new_week_payload()
    for team in data["schedule"]["settings"]["proTeams"]:
        if team["id"] in (1, 2):
            team["proGamesByScoringPeriod"]["13"][0]["date"] = (NOW - timedelta(hours=1)).timestamp() * 1000
    nba = nba_schedule_payload()
    game = nba["leagueSchedule"]["gameDates"][0]["games"][0]
    game["gameDateTimeUTC"] = "2026-11-03T00:00:00Z"
    nba["leagueSchedule"]["gameDates"] = [{"games": [game]}]
    snapshot = espn.normalize(
        data["league"],
        data["schedule"],
        data["pool"],
        data["cards"],
        {},
        1,
        now=NOW,
        nba={"schedule": nba, "schedule_status": "fresh"},
    )
    assert snapshot["period"]["no_started_games_verified"] is False
    assert snapshot["period"]["bankable_scoring_period_ids"] == [13]
    assert snapshot["period"]["bankable_periods_verified"] is False
    assert snapshot["teams"][0]["roster"][0]["schedule"][0]["started"] is True
    assert snapshot["teams"][0]["roster"][0]["schedule_source"] == "espn_schedule"
    missing = actuals.reconstruct(
        1,
        {13: "2026-11-02"},
        {},
        {},
        {},
        None,
        snapshot["fetched_at"],
        no_started_games=snapshot["period"]["no_started_games_verified"],
    )
    assert missing["forecast_complete"] is False
    assert missing["nba_derived"]["expected_player_games"] is None
    official = actuals.reconstruct(
        1,
        {13: "2026-11-02"},
        {},
        {},
        {},
        snapshot["teams"][0]["totals"],
        snapshot["fetched_at"],
        no_started_games=snapshot["period"]["no_started_games_verified"],
    )
    assert official["forecast_source"] == "espn_official"
    assert official["forecast_complete"] is True
    assert official["nba_derived"]["expected_player_games"] is None
