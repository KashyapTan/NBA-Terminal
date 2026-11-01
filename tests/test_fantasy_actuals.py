"""Synthetic history/production contracts; never depend on live league credentials."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from types import SimpleNamespace

import pytest
import requests

from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_actuals as actuals
from nba_terminal.services import fantasy_nba as nba

STAMP = "2026-10-31T18:00:00+00:00"
DAYS = {1: "2026-10-26", 2: "2026-10-27", 3: "2026-10-28", 4: "2026-10-29"}


def values(points=10, made=4, attempts=10):
    return dict.fromkeys(actuals.PRIMITIVES, 1.0) | {"pts": points, "fgm": made, "fga": attempts}


def entry(pid=1, slot=0, owner=10, **player):
    return {
        "lineupSlotId": slot,
        "playerPoolEntry": {
            "teamId": owner,
            "player": {
                "id": pid,
                "fullName": f"Player {pid}",
                "proTeamId": 1,
                "eligibleSlots": [0, 11, 12, 13],
                **player,
            },
        },
    }


def schedules():
    return {
        1: [
            {"game_id": f"002{i}", "date": day, "scoring_period_id": i, "started": True, "final": True}
            for i, day in DAYS.items()
        ]
    }


def rows():
    return {
        (f"002{i}", str(pid)): {"totals": values(pid * 10), "status": "fresh", "final": True}
        for i in DAYS
        for pid in (1, 2, 3)
    }


@pytest.fixture(autouse=True)
def identities(monkeypatch):
    monkeypatch.setattr(
        nba.players, "get_players", lambda: [{"id": pid, "full_name": f"Player {pid}"} for pid in (1, 2, 3)]
    )


def reconstruct(lineups, **kwargs):
    params = {
        "team_id": 10,
        "days": DAYS,
        "lineups": lineups,
        "schedules": schedules(),
        "rows": rows(),
        "official": values(150),
        "fetched_at": STAMP,
    }
    return actuals.reconstruct(**(params | kwargs))


def test_historical_add_drop_trade_bench_and_ir_not_current_roster():
    # Monday starter 1 is dropped Tuesday; player 2 acquired Wednesday.
    # Player 2 sits Thursday. Player 3 trades to opponent Thursday. Today's roster is irrelevant.
    history = {
        1: {10: [entry(1), entry(3, slot=13)]},
        2: {10: [entry(3)]},
        3: {10: [entry(2), entry(3, slot=12)]},
        4: {10: [entry(2, slot=12)], 20: [entry(3, owner=20)]},
    }
    result = reconstruct(history)
    assert result["nba_derived"]["complete"]
    assert result["nba_derived"]["totals"]["pts"] == 60
    assert result["nba_derived"]["covered_player_games"] == 3
    assert result["official"]["totals"]["pts"] == 150
    assert result["forecast_source"] == "nba_derived"
    assert result["discrepancy"]["pts"] == -90
    opponent = reconstruct(history, team_id=20, days={4: DAYS[4]})
    assert opponent["forecast_totals"]["pts"] == 30


def test_percentages_weight_attempts_and_unknown_no_zeros():
    history = {i: {10: [entry(1)]} for i in (1, 2)}
    data = rows()
    data[("0021", "1")]["totals"] = values(made=1, attempts=2)
    data[("0022", "1")]["totals"] = values(made=9, attempts=10)
    result = reconstruct(history, days={i: DAYS[i] for i in (1, 2)}, rows=data)
    assert result["forecast_totals"]["fg_pct"] == pytest.approx(10 / 12)
    missing = reconstruct({}, official=None)
    assert missing["forecast_totals"] is None
    assert missing["nba_derived"]["totals"] is None
    assert missing["forecast_complete"] is False


@pytest.mark.parametrize("change", ["missing_day", "eligibility", "ownership", "missing_row", "stale", "schedule"])
def test_incomplete_reconstruction_falls_back_to_official(change):
    history = {i: {10: [entry()]} for i in DAYS}
    data, schedule = rows(), schedules()
    if change == "missing_day":
        del history[2]
    elif change == "eligibility":
        history[2][10] = [entry(eligibleSlots=[11])]
    elif change == "ownership":
        history[2][10] = [entry(owner=20)]
    elif change == "missing_row":
        del data[("0022", "1")]
    elif change == "stale":
        data[("0022", "1")]["status"] = "stale"
    else:
        schedule = {}
    result = reconstruct(history, rows=data, schedules=schedule)
    assert not result["nba_derived"]["complete"]
    assert result["forecast_source"] == "espn_official"
    assert result["forecast_totals"]["pts"] == 150
    assert result["nba_derived"]["provisional"]
    assert result["discrepancy"] is None


def test_empty_schedule_verified_zero_different_from_missing():
    history = {i: {10: [entry()]} for i in DAYS}
    empty = reconstruct(history, schedules={1: []})
    assert empty["nba_derived"]["complete"]
    assert empty["forecast_totals"]["pts"] == 0
    assert not reconstruct(history, schedules={})["nba_derived"]["complete"]


def test_daily_roster_scope_and_duplicate_ownership_rejected():
    payload = {
        "scoringPeriodId": 1,
        "schedule": [
            {"matchupPeriodId": 2, "home": {"teamId": 10, "rosterForCurrentScoringPeriod": {"entries": [entry()]}}}
        ],
    }
    assert actuals.daily_lineups(payload, 1, 2, {10}) == {10: [entry()]}
    assert actuals.daily_lineups(payload, 2, 2, {10}) == {}
    side = payload["schedule"][0]["home"]
    side["roster"] = side.pop("rosterForCurrentScoringPeriod")
    assert actuals.daily_lineups(payload, 1, 2, {10}) == {}
    side["rosterForCurrentScoringPeriod"] = {"entries": [entry(), entry()]}
    assert actuals.daily_lineups(payload, 1, 2, {10}) == {}


def test_correction_replaces_same_key_live_not_append(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(actuals, "fetch_logs", lambda *a: {"rows": [], "fetched_at": STAMP})
    counter = [10]

    def fetch(game):
        return {"rows": [{"nba_player_id": 1, "totals": values(counter[0])}], "final": False, "fetched_at": STAMP}

    monkeypatch.setattr(actuals, "fetch_live", fetch)
    schedule = {1: [{"game_id": "0021", "date": DAYS[1], "started": True}]}
    first, _ = actuals.production(2027, [DAYS[1]], schedule)
    nba._CACHE.clear()
    counter[0] = 9  # Official stat correction downward.
    corrected, _ = actuals.production(2027, [DAYS[1]], schedule)
    assert len(corrected) == 1
    assert corrected[("0021", "1")]["totals"]["pts"] == 9
    assert first[("0021", "1")]["totals"]["pts"] == 10
    result = reconstruct({1: {10: [entry()]}}, days={1: DAYS[1]}, schedules=schedule, rows=corrected)
    assert result["forecast_totals"]["pts"] == 9
    assert result["nba_derived"]["provisional"]
    assert result["started_game_policy"] == "banked_only_no_projected_remainder"


def test_partial_historical_logs_recover_required_dnp_without_unrelated_games(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    record = {field: values().get(key, 1) for field, key in nba.FIELDS.items()} | {
        "PLAYER_ID": 1,
        "GAME_ID": "0021",
        "GAME_DATE": DAYS[1],
    }
    monkeypatch.setattr(actuals, "fetch_logs", lambda *a: {"rows": [record], "fetched_at": STAMP})
    calls = []

    def live(game_id):
        calls.append(game_id)
        return {
            "rows": [{"nba_player_id": 2, "totals": dict.fromkeys(actuals.PRIMITIVES, 0.0)}],
            "final": True,
            "fetched_at": STAMP,
        }

    monkeypatch.setattr(actuals, "fetch_live", live)
    schedule = {
        1: [
            {"game_id": "0021", "date": DAYS[1], "started": True, "final": True},
            {"game_id": "002unrelated", "date": DAYS[1], "started": True, "final": True},
        ]
    }
    needed = {("0021", "1"), ("0021", "2")}
    data, _ = actuals.production(2027, [DAYS[1]], schedule, needed)
    assert calls == ["0021"]
    assert data[("0021", "2")]["totals"]["pts"] == 0
    assert data[("0021", "1")]["totals"]["pts"] == 10
    assert ("0021", "3") not in data  # No inference for a missing box-score row.
    nba._CACHE.clear()
    calls.clear()
    actuals.production(2027, [DAYS[1]], schedule, {("0021", "1")})
    assert not calls  # Complete fresh required log coverage needs no game request.


def test_recovery_keys_use_historical_active_eligibility_and_known_identity_only():
    history = {1: {10: [entry(1), entry(2, slot=12), entry(99)]}}
    assert actuals.required_production_keys({1: DAYS[1]}, history, schedules()) == {("0021", "1")}
    history[1][10].append(entry(3, owner=20))
    assert not actuals.required_production_keys({1: DAYS[1]}, history, schedules())


@pytest.mark.parametrize("owner", [999, None])
def test_explicit_historical_onteam_owner_conflict_cannot_certify_empty_schedule(owner):
    daily_entry = entry()
    pool = daily_entry["playerPoolEntry"]
    pool.pop("teamId")
    pool["onTeamId"] = owner
    result = reconstruct({1: {10: [daily_entry]}}, days={1: DAYS[1]}, schedules={1: []})
    assert not result["nba_derived"]["complete"]
    assert result["forecast_source"] == "espn_official"
    assert result["nba_derived"]["gaps"][0]["reason"] == "historical_daily_ownership_conflict"
    pool["onTeamId"] = 10
    assert reconstruct({1: {10: [daily_entry]}}, days={1: DAYS[1]}, schedules={1: []})["nba_derived"]["complete"]
    assert not reconstruct({1: {10: [daily_entry, daily_entry]}}, days={1: DAYS[1]}, schedules={1: []})["nba_derived"][
        "complete"
    ]


def test_independent_cache_resources_do_not_serialize_network(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    barrier = Barrier(2)

    def fetch():
        barrier.wait(timeout=2)
        return {"ready": True}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(nba.cached, ("concurrent", i), fetch) for i in (1, 2)]
        assert all(f.result()[0]["ready"] for f in futures)
    assert nba._FLIGHTS == {}


def test_same_cache_resource_is_single_flight(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    calls = []

    def fetch():
        calls.append(1)
        return {"ready": True}

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(r[0]["ready"] for r in pool.map(lambda _: nba.cached(("same",), fetch), range(12)))
    assert len(calls) == 1


def test_fetch_logs_and_live_shapes_and_failures(monkeypatch):
    calls = []
    headers = ["PLAYER_ID", "GAME_ID", "GAME_DATE", *nba.FIELDS]

    def endpoint(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            get_dict=lambda: {
                "resultSets": [
                    {
                        "name": "PlayerGameLogs",
                        "headers": headers,
                        "rowSet": [[1, "0021", DAYS[1], *([1] * len(nba.FIELDS))]],
                    }
                ]
            }
        )

    monkeypatch.setattr(actuals.playergamelogs, "PlayerGameLogs", endpoint)
    assert actuals.fetch_logs(2027, DAYS[1], DAYS[4])["rows"][0]["PLAYER_ID"] == 1
    assert calls[0]["date_from_nullable"] == "10/26/2026"
    assert calls[0]["timeout"] == 6
    game = {
        "gameId": "0021",
        "gameStatus": 3,
        "homeTeam": {"players": [{"personId": 1, "played": "0"}]},
        "awayTeam": {"players": []},
    }
    monkeypatch.setattr(actuals.boxscore, "BoxScore", lambda **kw: SimpleNamespace(get_dict=lambda: {"game": game}))
    assert actuals.fetch_live("0021")["rows"][0]["totals"]["pts"] == 0
    with pytest.raises(ValueError, match="identity mismatch"):
        actuals.fetch_live("wrong")


def test_history_private_failure_never_uses_current_roster(monkeypatch):
    class Client:
        season_id = 2027

        def get(self, *args, **kwargs):
            raise espn.EspnError("access_denied", "safe")

    snapshot = {
        "period": {
            "matchup_period_id": 1,
            "scoring_period_ids": [1],
            "source": "espn_scoring_periods",
            "calendar_verified": True,
        },
        "selected_team_id": 10,
        "opponent_team_id": 20,
        "fetched_at": STAMP,
        "teams": [
            {"id": 10, "totals": values(), "roster": [{"schedule": [{"date": DAYS[1], "scoring_period_id": 1}]}]}
        ],
    }
    monkeypatch.setattr(
        actuals, "production", lambda *args: pytest.fail("No verified daily history means no NBA reads")
    )
    actuals.enrich_snapshot(Client(), {"scoringPeriodId": 1}, snapshot, schedules())
    assert snapshot["teams"][0]["actuals"]["forecast_source"] == "espn_official"
    assert snapshot["actuals_coverage"]["history_failures"][0]["reason"] == "access_denied"
    assert snapshot["projection_metadata"]["actuals_team_10"]["complete"]


def test_provider_failure_backoff(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    calls = []

    def fail(*args):
        calls.append(1)
        raise requests.Timeout()

    monkeypatch.setattr(actuals, "fetch_logs", fail)
    monkeypatch.setattr(actuals, "fetch_live", fail)
    for _ in range(2):
        data, sources = actuals.production(2027, [DAYS[1]], schedules())
        assert not data
        assert all(source["status"] == "unavailable" for source in sources)
    assert len(calls) == 2  # One batch and one relevant game, each negatively cached.


def test_rates_one_two_game_primary_and_prior_fallback():
    for gp in (1, 2):
        player = {
            "name": "Player 1",
            "pro_team_id": 1,
            "current_rates": values(99) | {"minutes": 30},
            "current_games": 5,
            "prior_rates": values(20) | {"minutes": 30},
            "prior_games": 70,
            "current_rates_source": "espn_actual_season",
        }
        snapshot = {"teams": [{"roster": [player]}], "free_agents": [], "data_gaps": [], "fetched_at": STAMP}
        row = {field: values().get(key, 30) for field, key in nba.FIELDS.items()} | {
            "PLAYER_ID": 1,
            "PLAYER_NAME": "Player 1",
            "TEAM_ABBREVIATION": "ATL",
            "GP": gp,
            "FG_PCT": 0.99,
        }
        nba.enrich_players(snapshot, {"rates": [row], "rates_status": "fresh", "rates_fetched_at": STAMP})
        assert player["season_rates"]["pts"] == 10
        assert player["season_rates"]["fg_pct"] == 0.4
        assert player["rate_provenance"]["small_sample"]
        assert not player["rate_provenance"]["fallback"]
        assert player["rate_provenance"]["fetched_at"] == STAMP
        player["current_rates"], player["current_games"] = None, None
        nba.enrich_players(snapshot, {"rates": [], "rates_status": "unavailable"})
        assert player["season_rates"]["pts"] == 20
        assert player["rate_provenance"]["source"] == "espn_prior_season"
        assert player["rate_provenance"]["fallback"]


def test_schedule_explicit_empty_vs_missing():
    now = datetime.now(timezone.utc)
    assert espn.normalize_schedule({"settings": {"proTeams": [{"id": 1, "proGamesByScoringPeriod": {}}]}}, now) == {
        1: []
    }
    assert espn.normalize_schedule({"settings": {"proTeams": [{"id": 1}]}}, now) == {}


def test_market_pages_and_provider_bound(monkeypatch):
    calls = []

    def get(self, views, filters=None, **kwargs):
        offset = filters["players"]["offset"]
        calls.append(offset)
        return {
            "players": [entry(pid, owner=0) for pid in range(offset, min(offset + filters["players"]["limit"], 843))],
            "totalPlayers": 843,
        }

    monkeypatch.setattr(espn.EspnClient, "get", get)
    market = espn.EspnClient(1, 2027).market(10)
    assert calls == [0, 500]
    assert len(market["players"]) == 843
    assert market["coverage"]["complete"]

    def endless(self, views, filters=None, **kwargs):
        offset = filters["players"]["offset"]
        return {
            "players": [entry(pid, owner=0) for pid in range(offset, offset + filters["players"]["limit"])],
            "totalPlayers": 9999,
        }

    monkeypatch.setattr(espn.EspnClient, "get", endless)
    bounded = espn.EspnClient(1, 2027).market(10)
    assert len(bounded["players"]) == 2000
    assert bounded["coverage"]["stopped_reason"] == "application_bound"
    assert not bounded["coverage"]["complete"]


def test_market_repeated_page_and_partial_failure(monkeypatch):
    page = {"players": [entry(pid, owner=0) for pid in range(500)]}
    monkeypatch.setattr(espn.EspnClient, "get", lambda *a, **kw: page)
    repeated = espn.EspnClient(1, 2027).market(1)
    assert len(repeated["players"]) == 500
    assert not repeated["coverage"]["complete"]

    def get(self, views, filters=None, **kwargs):
        if filters["players"]["offset"]:
            raise espn.EspnError("timeout", "safe")
        return page

    monkeypatch.setattr(espn.EspnClient, "get", get)
    assert not espn.EspnClient(1, 2027).market(1)["coverage"]["complete"]


def test_cap_zero_absent_seven_and_usage_unknown():
    import json
    from pathlib import Path

    fixture = json.loads((Path(__file__).parent / "fixtures/espn_fantasy_synthetic.json").read_text())
    league = fixture["league"]
    acquisition = league["settings"]["acquisitionSettings"]
    acquisition.update(matchupAcquisitionLimit=0, matchupLimitPerScoringPeriod=False)
    league["teams"][0]["transactionCounter"]["matchupAcquisitionTotals"] = {
        str(league["status"]["currentMatchupPeriod"]): 0
    }
    result = espn.normalize(league, fixture["schedule"], fixture["pool"], {}, {}, 1)
    assert result["league"]["acquisition_settings"]["weekly_add_limit"] == 0
    assert result["teams"][0]["remaining_adds"] == 0
    assert result["league"]["acquisition_settings"]["cap_source"] == "espn_acquisition_settings"
    del acquisition["matchupAcquisitionLimit"]
    league["id"] = 604550749  # Authorized context-bound user fallback, not a generic league default.
    for team in league["teams"]:
        team["transactionCounter"] = {"acquisitions": 99}
    result = espn.normalize(league, fixture["schedule"], fixture["pool"], {}, {}, 1)
    assert result["league"]["acquisition_settings"]["weekly_add_limit"] == 7
    assert result["league"]["acquisition_settings"]["cap_source"] == "league_fallback_7"
    assert result["teams"][0]["weekly_used_adds"] is None
    assert result["teams"][0]["remaining_adds"] is None


def test_ir_kept_as_legal_drop_without_active_starts():
    normalized = espn.normalize_player(
        entry(slot=13), {}, schedules(), 2027, [1], datetime.now(timezone.utc), rostered=True
    )
    assert normalized["lineup_slot"] == "IR"
    assert normalized["active"] is False
    assert normalized["id"] == "1"


def test_history_partial_flag_or_unknown_calendar_disallows_nba_complete():
    history = {i: {10: [entry()]} for i in DAYS}
    assert reconstruct(history, history_complete=False)["forecast_source"] == "espn_official"


def test_verified_id_crosswalk_recovers_new_identity_without_current_ownership_proxy(monkeypatch):
    monkeypatch.setattr(nba.players, "get_players", lambda: [])
    history = {1: {10: [entry(99)]}}
    identity = {"99": 2}
    assert actuals.required_production_keys({1: DAYS[1]}, history, schedules(), identity) == {("0021", "2")}
    result = reconstruct(history, days={1: DAYS[1]}, identities=identity)
    assert result["forecast_source"] == "nba_derived"
    assert result["forecast_totals"]["pts"] == 20
    history[1][10][0]["playerPoolEntry"]["onTeamId"] = 20
    assert reconstruct(history, days={1: DAYS[1]}, identities=identity)["forecast_source"] == "espn_official"


def test_live_request_bound_is_per_game_not_player(monkeypatch):
    monkeypatch.setattr(nba, "_CACHE", {})
    monkeypatch.setattr(actuals, "fetch_logs", lambda *a: {"rows": [], "fetched_at": STAMP})
    calls = []

    def fetch(game):
        calls.append(game)
        return {"rows": [], "final": False, "fetched_at": STAMP}

    monkeypatch.setattr(actuals, "fetch_live", fetch)
    games = [{"game_id": f"002{i:03}", "date": DAYS[1], "started": True} for i in range(30)]
    actuals.production(2027, [DAYS[1]], {1: games, 2: games})
    assert len(calls) == 16
    assert len(set(calls)) == 16


def test_unknown_start_is_missing_schedule_not_empty():
    now = datetime.now(timezone.utc)
    raw = {
        "settings": {
            "proTeams": [
                {"id": 1, "proGamesByScoringPeriod": {"1": [{"date": now.timestamp() * 1000, "startTimeTBD": True}]}}
            ]
        }
    }
    assert espn.normalize_schedule(raw, now) == {}
    nba_schedule = {
        "leagueSchedule": {
            "seasonYear": "2026-27",
            "gameDates": [
                {
                    "games": [
                        {
                            "gameId": "0021",
                            "gameDateTimeUTC": "2026-10-26T23:00:00Z",
                            "homeTeam": {"teamId": 1610612737},
                            "awayTeam": {"teamId": 1610612738},
                        },
                        {
                            "gameId": "0022",
                            "gameDateTimeUTC": "TBD",
                            "homeTeam": {"teamId": 1610612737},
                            "awayTeam": {"teamId": 1610612738},
                        },
                    ]
                }
            ],
        }
    }
    parsed = nba.schedule_games(nba_schedule, 2027, now)
    assert 1 not in parsed and 2 not in parsed
    assert parsed[3] == []


def test_complete_enrichment_uses_verified_daily_side_and_preserves_metadata(monkeypatch):
    class Client:
        season_id = 2027

        def get(self, views, filters, *, scoring_period):
            assert scoring_period == 1
            return {
                "scoringPeriodId": 1,
                "schedule": [
                    {
                        "matchupPeriodId": 2,
                        "home": {"teamId": 10, "rosterForCurrentScoringPeriod": {"entries": [entry()]}},
                    }
                ],
            }

    snapshot = {
        "period": {
            "matchup_period_id": 2,
            "scoring_period_ids": [1],
            "source": "espn_scoring_periods",
            "calendar_verified": True,
        },
        "selected_team_id": 10,
        "opponent_team_id": 20,
        "fetched_at": STAMP,
        "projection_metadata": {"rates": {"complete": True}},
        "teams": [
            {"id": 10, "totals": values(99), "roster": [{"schedule": [{"date": DAYS[1], "scoring_period_id": 1}]}]}
        ],
    }
    monkeypatch.setattr(
        actuals,
        "production",
        lambda *args: (rows(), [{"source": "nba_player_game_logs", "fetched_at": STAMP, "status": "fresh"}]),
    )
    actuals.enrich_snapshot(Client(), {"scoringPeriodId": 1}, snapshot, schedules())
    result = snapshot["teams"][0]["actuals"]
    assert result["forecast_source"] == "nba_derived"
    assert result["forecast_totals"]["pts"] == 10
    assert result["official"]["totals"]["pts"] == 99
    assert snapshot["projection_metadata"]["rates"]["complete"]
    assert snapshot["projection_metadata"]["actuals_team_10"]["complete"]
    snapshot["period"]["calendar_verified"] = False
    actuals.enrich_snapshot(Client(), {"scoringPeriodId": 1}, snapshot, schedules())
    assert snapshot["teams"][0]["actuals"]["forecast_source"] == "espn_official"


def test_stale_nba_rates_prefer_espn_and_missing_rates_remain_unknown():
    player = {
        "id": "1",
        "name": "Player 1",
        "pro_team_id": 1,
        "current_rates": values(99) | {"minutes": 30},
        "current_rates_source": "espn_actual_season",
        "current_games": 2,
        "prior_rates": None,
        "prior_games": None,
    }
    snapshot = {
        "selected_team_id": 10,
        "opponent_team_id": 20,
        "teams": [{"id": 10, "roster": [player]}],
        "free_agents": [],
        "data_gaps": [],
        "fetched_at": STAMP,
    }
    nba.enrich_players(
        snapshot,
        {
            "rates": [{"PLAYER_ID": 1, "PLAYER_NAME": "Player 1", "TEAM_ABBREVIATION": "ATL", "GP": 1, "PTS": 10}],
            "rates_status": "stale",
        },
    )
    assert player["season_rates"]["pts"] == 99
    assert player["rate_provenance"]["source"] == "espn_actual_season"
    player["current_rates"], player["current_games"], player["current_rates_source"] = None, None, None
    nba.enrich_players(snapshot, {"rates": [], "rates_status": "unavailable"})
    assert player["season_rates"] is None
    assert player["rate_provenance"]["source"] is None
