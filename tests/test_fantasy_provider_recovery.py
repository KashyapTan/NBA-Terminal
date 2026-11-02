"""Provider-recovery contracts; public historical shapes and synthetic current inputs only."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_actuals as actuals
from nba_terminal.services import fantasy_nba as nba
from nba_terminal.services import fantasy_planner_adapter as adapter
from nba_terminal.services.fantasy_nba import fetch_identities as fetch_identity_batch
from nba_terminal.services.fantasy_nba import load as load_current_bundle
from nba_terminal.services.fantasy_nba import load_prior_rates as load_prior_sample
from tests.test_fantasy_integration import preferences

NOW = datetime(2026, 10, 31, 18, tzinfo=timezone.utc)
PUBLIC = json.loads((Path(__file__).parent / "fixtures/fantasy_recovery_public_shapes.json").read_text())


@pytest.fixture
def data():
    return json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())


def normalize(data):
    return espn.normalize(data["league"], data["schedule"], data["pool"], data["cards"], {}, 1, now=NOW)


def test_public_daily_onteam_shape_and_current_season_shooting_sample():
    daily = PUBLIC["daily"]
    entries = copy.deepcopy(daily["entries"])
    side = {"teamId": daily["team_id"], "rosterForCurrentScoringPeriod": {"entries": entries}}
    raw = {"scoringPeriodId": daily["scoring_period_id"], "schedule": [{"matchupPeriodId": 3, "home": side}]}
    assert actuals.daily_lineups(raw, 21, 3, {daily["team_id"]})[daily["team_id"]] == entries
    entries[0]["playerPoolEntry"]["onTeamId"] = 999
    assert not actuals.daily_lineups(raw, 21, 3, {daily["team_id"]})
    sample, games = espn.samples(PUBLIC["card"]["player"], 2023)
    assert games == 55
    assert sample["fgm"] == pytest.approx(609 / 55)
    assert sample["fg_pct"] == pytest.approx(609 / 1219)


def test_terminal_enumeration_without_total_and_silently_smaller_pages(monkeypatch):
    observed = [pid for page in PUBLIC["market"]["pages"] for pid in page["ids"]]
    calls = []

    def get(self, views, filters, **kwargs):
        offset, limit = (filters["players"][key] for key in ("offset", "limit"))
        calls.append(offset)
        # Simulated100-row server cap: a short response is not exhaustion.
        return {"players": [{"player": {"id": pid}} for pid in observed[offset : offset + min(limit, 100)]]}

    monkeypatch.setattr(espn.EspnClient, "get", get)
    bounded = espn.EspnClient(123, 2023).market(176)
    assert len(bounded["players"]) == 800
    assert not bounded["coverage"]["complete"]
    assert bounded["coverage"]["stopped_reason"] == "application_bound"
    assert calls[:3] == [0, 100, 200]
    calls.clear()

    def full(self, views, filters, **kwargs):
        offset, limit = (filters["players"][key] for key in ("offset", "limit"))
        calls.append(offset)
        return {"players": [{"player": {"id": pid}} for pid in observed[offset : offset + limit]]}

    monkeypatch.setattr(espn.EspnClient, "get", full)
    complete = espn.EspnClient(123, 2023).market(176)
    assert len(complete["players"]) == 843
    assert calls == [0, 500, 843]
    assert complete["coverage"]["complete"]
    assert complete["coverage"]["provider_total"] is None
    assert complete["coverage"]["stopped_reason"] == "terminal_page"


def test_missing_current_counter_gets_one_scoped_refresh_and_large_cards_are_batched(monkeypatch, data):
    current = data["league"]["status"]["currentMatchupPeriod"]
    refreshed = copy.deepcopy(data["league"])
    refreshed["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {str(current): 0}
    market = []
    for pid in range(2000, 3101):
        row = copy.deepcopy(data["pool"]["players"][0])
        row["player"]["id"] = pid
        market.append(row)
    cards, counter_calls = [], []

    def get(self, views, filters=None, **kwargs):
        if views == ["mTeam"]:
            counter_calls.append(1)
            return refreshed
        if views == ["kona_playercard"]:
            cards.append(filters["players"]["filterIds"]["value"])
            return {"players": []}
        if views == ["proTeamSchedules_wl"]:
            return data["schedule"]
        return data["league"]

    monkeypatch.setattr(espn.EspnClient, "get", get)
    monkeypatch.setattr(espn.EspnClient, "market", lambda *args: {"players": market, "coverage": {"complete": True}})
    result = espn.EspnClient(123, 2027).snapshot(data["league"], 1)
    assert counter_calls == [1]
    assert result["teams"][0]["weekly_used_adds"] == 0
    assert result["teams"][0]["weekly_usage_source"].endswith("targeted_refresh")
    assert len(cards) > 4 and all(len(batch) <= 250 for batch in cards)
    assert len(set(pid for batch in cards for pid in batch)) > 1000
    assert len(result["free_agents"]) == 1101
    assert data["league"]["teams"][0]["transactionCounter"].get("matchupAcquisitionTotals") is None


def test_irrelevant_future_schedule_row_does_not_erase_current_matchup(data):
    team = data["schedule"]["settings"]["proTeams"][0]
    team["proGamesByScoringPeriod"]["150"] = [{"date": None, "startTimeTBD": True}]
    result = normalize(data)
    assert result["teams"][0]["roster"][0]["schedule"] is not None
    current = next(iter(team["proGamesByScoringPeriod"]))
    team["proGamesByScoringPeriod"][current][0]["scoringPeriodId"] = 999
    assert normalize(data)["teams"][0]["roster"][0]["schedule"] is None


def test_explicit_market_owner_and_lock_flags_are_not_misrepresented(data):
    pool = data["pool"]["players"][0]
    pool.update(onTeamId=99, lineupLocked=True, rosterLocked=True, tradeLocked=False)
    player = normalize(data)["free_agents"][0]
    assert player["on_team_id"] == 99
    assert player["eligible"] is False
    assert player["provider_locks"] == {"lineupLocked": True, "rosterLocked": True, "tradeLocked": False}
    assert player["locked"] is None  # Raw lock names do not prove drop semantics.


def test_authorized_context_keeps_declared_matchup_cap_independent_of_optional_daily_scope(data):
    data["league"].update(id=604550749)
    acquisition = data["league"]["settings"]["acquisitionSettings"]
    acquisition.pop("matchupLimitPerScoringPeriod", None)
    current = data["league"]["status"]["currentMatchupPeriod"]
    data["league"]["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {str(current): 6}
    result = normalize(data)
    settings = result["league"]["acquisition_settings"]
    assert settings["limit_per_scoring_period"] is None
    assert settings["reported_add_limit"] == 7 and settings["reported_limit_scope"] == "unknown"
    assert settings["matchup_add_limit"] == 7 and settings["cap_source"] == "league_fallback_7"
    assert result["teams"][0]["remaining_adds"] == 1


def test_optimizer_limit_is_separate_from_market_retrieval(monkeypatch, data):
    snapshot = normalize(data)
    template = snapshot["free_agents"][0]
    snapshot["free_agents"] = [template | {"id": str(pid)} for pid in range(2000, 3101)]
    captured = []
    original = adapter.plan_waivers

    def plan(payload):
        captured.append(payload)
        # No expensive1100-candidate search is needed to verify the input boundary.
        return original(payload | {"players": [p for p in payload["players"] if p["owner"] != "free"]})

    monkeypatch.setattr(adapter, "plan_waivers", plan)
    prefs = preferences(snapshot)
    prefs.pop("candidate_ids")
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert len(captured[0]["players"]) == 1000
    assert result["candidate_coverage"]["qualified"] == 1101
    assert result["candidate_coverage"]["resource_bound_reached"]
    assert result["search"]["alternatives_complete"] is False
    assert len(snapshot["free_agents"]) == 1101


@pytest.mark.parametrize("missing", ["market", "samples"])
def test_absent_opportunity_evidence_is_not_evaluated_no_benefit(data, missing):
    snapshot = normalize(data)
    prefs = preferences(snapshot)
    if missing == "market":
        snapshot.update(free_agents=[], market_complete=False)
        prefs.pop("candidate_ids")
    else:
        snapshot["free_agents"][0].update(current_rates=None, prior_rates=None)
    result = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert result["evaluation_state"] == "required_inputs_unknown"
    assert not result["actions"] and not result["recommendations"]
    assert not any("No materially beneficial legal" in reason for reason in result["reasons"])


def test_stale_manual_counts_cannot_be_reconfirmed_by_a_background_snapshot_refresh(data):
    snapshot = normalize(data)
    prefs = preferences(snapshot) | {"counts_snapshot_at": "2026-10-30T18:00:00+00:00"}
    stale = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert not stale["actions"] and stale["evaluation_state"] == "required_inputs_unknown"
    assert "older data" in stale["reasons"][0]
    prefs["counts_snapshot_at"] = snapshot["fetched_at"]
    valid = adapter.plan_snapshot_waivers(snapshot, prefs, NOW)
    assert valid["provenance"]["counts_confirmation"]["snapshot_fetched_at"] == snapshot["fetched_at"]


def test_current_identity_inventory_and_prior_rate_recovery(monkeypatch):
    monkeypatch.setattr(nba.players, "get_players", lambda: [])
    identity = {"PERSON_ID": 321, "DISPLAY_FIRST_LAST": "Sample Rookie II", "TEAM_ID": 1610612737, "ROSTERSTATUS": 1}
    row, match = nba.match_player({"name": "Sample Rookie II", "pro_team_id": 1}, [], [identity])
    assert row is None and match["nba_player_id"] == 321 and match["current_season_roster"]
    assert nba.match_player({"name": "Sample Rookie", "pro_team_id": 1}, [], [identity])[1]["nba_player_id"] is None
    player = {
        "name": "Sample Rookie II",
        "pro_team_id": 1,
        "current_rates": None,
        "current_games": 0,
        "prior_rates": None,
    }
    snapshot = {"league": {"season_id": 2027}, "teams": [{"roster": [player]}], "free_agents": [], "data_gaps": []}
    prior = {field: 1 for field in nba.FIELDS} | {
        "PLAYER_ID": 321,
        "PLAYER_NAME": "Sample Rookie II",
        "TEAM_ABBREVIATION": "ATL",
        "GP": 60,
    }
    nba.enrich_players(
        snapshot,
        {
            "rates": [],
            "identities": [identity],
            "prior_rates": [prior],
            "prior_rates_status": "fresh",
            "season": "2026-27",
        },
    )
    assert player["season_rates"]["fg_pct"] == 1
    assert player["rate_provenance"]["source"] == "nba_prior_season"
    assert player["rate_provenance"]["season"] == "2025-26"


def test_trade_season_aggregate_preferred_and_distinct_team_samples_weighted():
    def row(team, games, points):
        return {field: 1 for field in nba.FIELDS} | {
            "PLAYER_ID": 321,
            "PLAYER_NAME": "Sample Player",
            "TEAM_ABBREVIATION": team,
            "GP": games,
            "PTS": points,
        }

    player = {"name": "Sample Player", "pro_team_id": 1}
    first, second = row("BOS", 2, 10), row("ATL", 1, 40)
    combined, identity = nba.match_player(player, [first, second])
    assert combined["GP"] == 3 and combined["PTS"] == 20
    assert identity["source"] == "nba_stats_team_splits_weighted_by_games"
    aggregate = row("TOT", 3, 25) | {"TEAM_ID": 0}
    assert nba.match_player(player, [first, second, aggregate])[0]["PTS"] == 25


def test_identity_request_uses_the_real_supported_constructor_and_explicit_season(monkeypatch):
    requests = []
    endpoint = nba.commonallplayers.CommonAllPlayers
    monkeypatch.setattr(endpoint, "get_request", lambda self: requests.append(self.parameters))
    monkeypatch.setattr(
        endpoint,
        "get_dict",
        lambda self: {
            "resultSets": [
                {
                    "name": "CommonAllPlayers",
                    "headers": ["PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID", "ROSTERSTATUS"],
                    "rowSet": [[321, "Sample Rookie II", 1610612737, 1]],
                }
            ]
        },
    )
    assert fetch_identity_batch(2027)[0]["PERSON_ID"] == 321
    assert requests == [{"IsOnlyCurrentSeason": 1, "LeagueID": "00", "Season": "2026-27"}]
    calls = []
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(nba, "fetch_rates", lambda year: calls.append(year) or [])
    load_prior_sample(2027)
    load_prior_sample(2027)
    assert calls == [2026]


@pytest.mark.parametrize("reported_total", [None, 500])
def test_oversized_market_page_cannot_skip_returned_ids_then_claim_complete(monkeypatch, reported_total):
    calls = []

    def oversized(self, views, filters, **kwargs):
        offset = filters["players"]["offset"]
        calls.append(offset)
        page = {"players": [{"player": {"id": pid}} for pid in range(1000)] if offset == 0 else []}
        if reported_total is not None:
            page["totalPlayers"] = reported_total
        return page

    monkeypatch.setattr(espn.EspnClient, "get", oversized)
    result = espn.EspnClient(123, 2027).market(1)
    assert calls == [0]  # No cursor advance past the discarded overflow.
    assert len(result["players"]) == 500
    assert not result["coverage"]["complete"] and not result["coverage"]["terminal_observed"]
    assert result["coverage"]["stopped_reason"] == "oversized_page"
    assert result["coverage"]["pages"] == [{"offset": 0, "requested": 500, "returned": 1000}]


@pytest.mark.parametrize(
    "games,made",
    [
        (None, None),
        (None, 1),
        (float("nan"), 1),
        (float("inf"), 1),
        (-1, 1),
        (1.5, 1),
        (False, 1),
        (0, None),
        (4, None),
    ],
)
def test_malformed_gp_or_primitives_preserve_last_valid_nba_batch_at_load_boundary(monkeypatch, games, made):
    headers = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GP", *nba.FIELDS]
    good = {
        "PLAYER_ID": 123,
        "PLAYER_NAME": "Example",
        "TEAM_ID": 1610612737,
        "GP": 4,
        **{field: 1 for field in nba.FIELDS},
    }
    current = [good]
    clock = [100.0]
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(nba.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        nba.leaguedashplayerstats,
        "LeagueDashPlayerStats",
        lambda **kwargs: SimpleNamespace(
            get_dict=lambda: {
                "resultSets": [
                    {
                        "name": "LeagueDashPlayerStats",
                        "headers": headers,
                        "rowSet": [[row.get(key) for key in headers] for row in current],
                    }
                ]
            }
        ),
    )
    first = load_current_bundle(2027, need_schedule=False)
    assert first["rates_status"] == "fresh" and first["rates"][0]["FGM"] == 1
    current[:] = [good | {"GP": games, "FGM": made}]
    clock[0] = 1001  # Expired900s rate cache; valid batch still within stale retention.
    recovered = load_current_bundle(2027, need_schedule=False)
    assert recovered["rates_status"] == "stale"
    assert recovered["rates"][0]["GP"] == 4 and recovered["rates"][0]["FGM"] == 1
    assert recovered["rates_fetched_at"] == first["rates_fetched_at"]


def test_explicit_zero_gp_is_valid_zero_sample_but_never_an_invented_production_basis(monkeypatch):
    headers = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", *nba.FIELDS]
    row = {
        "PLAYER_ID": 123,
        "PLAYER_NAME": "Example",
        "TEAM_ID": 1610612737,
        "TEAM_ABBREVIATION": "ATL",
        "GP": 0,
        **{field: 0 for field in nba.FIELDS},
    }
    monkeypatch.setattr(
        nba.leaguedashplayerstats,
        "LeagueDashPlayerStats",
        lambda **kwargs: SimpleNamespace(
            get_dict=lambda: {
                "resultSets": [
                    {"name": "LeagueDashPlayerStats", "headers": headers, "rowSet": [[row.get(key) for key in headers]]}
                ]
            }
        ),
    )
    assert nba.fetch_rates(2027)[0]["GP"] == 0
    player = {"name": "Example", "pro_team_id": 1, "current_rates": None, "current_games": 0, "prior_rates": None}
    snapshot = {"teams": [{"roster": [player]}], "free_agents": [], "data_gaps": []}
    nba.enrich_players(snapshot, {"rates": [row], "rates_status": "fresh"})
    assert player["season_rates"] is None  # GP0 does not establish zero ability.
    row.update(GP=4.0)
    for field in nba.FIELDS:
        row[field] = 1
    assert nba.fetch_rates(2027)[0]["GP"] == 4.0  # Integral numeric floats remain supported.
