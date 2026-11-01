# Public player fixture provenance

Captured 2026-11-01 from NBA Stats via installed nba_api, without account credentials:

- `nba_boxscoreadvancedv3_finals_2025.json`: complete raw BoxScoreAdvancedV3 response for NBA Finals Game 7 `0042400407`; normalized regression selects Shai Gilgeous-Alexander `1628983` and checks personId/camelCase mapping, fractions, possessions, and turnoverRatio units.
- `nba_player_shooting_splits_2025.json`: complete raw PlayerDashboardByShootingSplits response for player `1628983`, `2024-25`, `Playoffs`, `PerMode=Totals`. All six retained profile breakdowns plus extra provider datasets are preserved. Zero-attempt percentage normalization is tested separately from raw provider zeroes.
- `nba_player_season_{base,misc,scoring,usage,defense}_2025.json`: actual LeagueDashPlayerStats `2024-25` Playoffs PerGame responses, with each raw rowSet reduced to player `1628983` only; all original headers and player values retained. Regression loads these through installed NBAStatsResponse and endpoint parser. Live full batches each returned 219 players. Usage MIN is total minutes despite PerGame; Base/Misc/Scoring/Defense MIN is per game. DD2/TD3 are counts.
- `nba_boxscoreadvancedv3_upstream.json`: unmodified upstream [response fixture](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/responses/boxscoreadvancedv3.json). Its game `1022500165` is a WNBA game. It validates the actual V3 nested parser structure and is explicitly not live NBA success evidence.

Transport output/time and normalized observations are retained in `code_review/evidence/v5_player_*live*.txt` and `v5_player_live_probe.txt`. Fixture tests mock transport; the retained logs document separate live observations and do not assert future availability.

Primary schema documentation: [V3](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/boxscoreadvancedv3.md), [league dashboard](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/leaguedashplayerstats.md), [shooting splits](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playerdashboardbyshootingsplits.md).
