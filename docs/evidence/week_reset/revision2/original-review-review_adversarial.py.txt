import json
from datetime import timedelta
from nba_terminal.services import espn_fantasy as espn
from nba_terminal.services import fantasy_actuals as actuals
from nba_terminal.services import fantasy_planner_adapter as adapter
from tests.test_week_reset import normalized, prefs
from tests.week_reset_fixture import NOW, new_week_payload
from tests.fantasy_v2_fixture import nba_schedule_payload

results = {}
snapshot = normalized()
results['normalized_fixture_team_name'] = snapshot['teams'][0]['name']
# Fresh deployment has no bootstrap from localStorage; mimic actual request absent declaration.
p = prefs(snapshot)
p.pop('usage_declaration')
res = adapter.plan_snapshot_waivers(snapshot, p, NOW)
results['missing_map_no_bootstrap'] = {'state': res['evaluation_state'], 'budget': res['acquisition_budget'], 'moves': len(res['plan'])}
# Real 30-team schedule, only teams 1/2 already started. Partial fresh NBA has one later game for those teams.
data = new_week_payload()
for team in data['schedule']['settings']['proTeams']:
    if team['id'] in (1, 2):
        team['proGamesByScoringPeriod']['13'][0]['date'] = (NOW - timedelta(hours=1)).timestamp() * 1000
nba = nba_schedule_payload()
game = nba['leagueSchedule']['gameDates'][0]['games'][0]
game['gameDateTimeUTC'] = '2026-11-03T00:00:00Z'
nba['leagueSchedule']['gameDates'] = [{'games': [game]}]
# ESPN map teams for ATL/BOS: 1/2.
base = espn.normalize(data['league'], data['schedule'], data['pool'], data['cards'], {}, 1, now=NOW)
merged = espn.normalize(data['league'], data['schedule'], data['pool'], data['cards'], {}, 1, now=NOW, nba={'schedule': nba, 'schedule_status': 'fresh'})
results['partial_nba_started_erasure'] = {'before': {k: base['period'][k] for k in ['no_started_games_verified', 'bankable_scoring_period_ids']}, 'after': {k: merged['period'][k] for k in ['no_started_games_verified', 'bankable_scoring_period_ids']}}
rec = actuals.reconstruct(1, {}, {}, {}, {}, None, merged['fetched_at'], no_started_games=merged['period']['no_started_games_verified'])
results['false_zero_actuals'] = {k: rec[k] for k in ['forecast_complete', 'forecast_source']}
assert base['period']['no_started_games_verified'] is False
assert merged['period']['no_started_games_verified'] is True
assert merged['period']['bankable_scoring_period_ids'] == []
# Adversarial weekly expansion (week indices 3/4, with October 21 day1 anchor).
data = new_week_payload()
data['league']['settings']['scheduleSettings']['periodTypeId'] = 2
data['league']['settings']['scheduleSettings']['matchupPeriods']['3'] = [3,4]
periods, source = espn.matchup_scoring_periods(data['league'], espn.normalize_schedule(data['schedule'], NOW, anchors_only=True))
results['weekly_expansion'] = {'periods': periods, 'source': source}
# Strict sparse zero and invalid maps through normalizer, positive API beats stale declaration through adapter.
for mapping in [{}, {'3': 2}, None, {'3': False}, {'3': 0.5}]:
    data = new_week_payload()
    data['league']['teams'][0]['transactionCounter']['matchupAcquisitionTotals'] = mapping
    snap = espn.normalize(data['league'], data['schedule'], data['pool'], data['cards'], {}, 1, now=NOW)
    results[f'map_{mapping}'] = snap['teams'][0]['weekly_used_adds']
print(json.dumps(results, indent=2))
