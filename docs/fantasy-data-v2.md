# Fantasy data normalization and NBA enrichment

Verified 2026-10-31. This document supersedes the data-source limitations in the original ESPN v1 guides. The transport remains read-only; no transaction, cookie export, browser storage or application lifecycle changes are involved.

## Corrected ESPN behavior

A public ESPN basketball league was queried without cookies to verify field names and types. Only sanitized aggregate observations were retained. These observations supplement the community client's source, which does not expose every returned field:

- `scheduleSettings.periodTypeId == 2` means WEEKLY. `matchupPeriods["2"] == [2]` identifies week two, not scoring day two. The professional schedule contains daily scoring IDs; `pointsByScoringPeriod` in matchup sides confirms observed daily coverage. Normalization derives the season date anchor from actual game dates/scoring IDs, applies Monday–Sunday weekly boundaries (short first week allowed), and verifies observed matchup scoring IDs fit. Disagreement produces explicitly partial observed coverage instead of silently inventing a full week. Weekly calendar dates include off days; individual schedules contain actual games only.
- `matchupAcquisitionLimit` can be a JSON float such as `7.0`. Finite nonnegative integral values are accepted. `matchupLimitPerScoringPeriod: false` establishes a matchup cap; `true` establishes a daily cap. Negative/unlimited, missing and ambiguous settings remain distinct.
- `team.transactionCounter.matchupAcquisitionTotals[str(matchup_id)]` is the actual matchup usage counter. It establishes complete usage independently of the partial daily transaction log. An absent key stays unknown, including for apparently inactive teams. An explicit zero stays zero. Season acquisitions are never substituted. Remaining matchup adds require both cap and usage.
- `player.droppable` is a real boolean, unlike the previous source-only assessment. `undroppable` reverses that flag, except a league with `rosterSettings.isUsingUndroppableList: false` explicitly disables list protection. `team.isTransactionLocked: true` is a real team transaction restriction. Game start is **not** inferred to mean a drop is locked. ESPN remains authoritative when the user manually transacts.
- `mDraftDetail.picks` supplies `playerId`, `overallPickNumber` and `roundId`. Metadata is passed to the planner; the data layer does not invent rankings or protection formulas.
- Actual season aggregates (`statSourceId=0`, `statSplitTypeId=0`, `scoringPeriodId=0`) supply rates. Cumulative totals divided by games take precedence over inconsistent `averageStats`; missing total fields can retain supplied averages. FG/FT percentages use makes/attempts. Forecast/rolling splits are excluded. Sparse cards merge actual splits without wiping usable roster samples.
- Current and prior cumulative matchup totals remain in `matchup_history`, including missing sides as null. One optional prior-period batch repairs missing previous-period totals across all teams; partial responses cannot erase an existing good side. `history_coverage` lists the prior periods with totals for each current team.

The public verification reproduced the stale-date bug: the old parser chose scoring day two for week two. The corrected public response produced October 26–November 1 with October 31/November 1 remaining, and usable current-season samples and upcoming games. This is public-source verification, separate from the browser worker's private connected-app audit.

## NBA enrichment

`fantasy_nba.py` performs public, credential-free batches, executed from the existing ESPN worker path:

1. `LeagueDashPlayerStats` for the explicit NBA season, `PerGame`, `Regular Season`, six-second timeout. ESPN ending year `2027` maps to NBA `2026-27`. Includes current minutes, category rates, GP, FGM/FGA/FTM/FTA. Only missing ESPN fields are filled.
2. When professional schedule coverage is incomplete, official NBA `scheduleLeagueV2.json`; if unavailable or for a different season, `ScheduleLeagueV2` with an explicit season and six-second timeout. The CDN response is limited to 8 MB and rejects redirects. The CDN returned HTTP 403 during research; this is an expected failure path, not evidence that NBA data succeeded live.

NBA schedule parsing keeps actual regular-season `002` games, excludes cup-final/exhibition/playoff IDs and postponed games, converts UTC timestamps through America/New_York including DST, and derives daily IDs from the first regular-season game. NBA team IDs map through official-client static team abbreviations into ESPN IDs (PHL/PHO aliases handled). Empty current samples, schema drift and transport failures are unavailable, never zero games/rates.

Player matching requires a unique normalized full name and current pro-team abbreviation for NBA rates. Accents and punctuation normalize; suffix letters remain distinct. Ambiguous matches never enrich rates. A unique packaged NBA static full name can establish identity without borrowing another team's rates; unknown rookies remain unresolved. There is no fuzzy matching and no per-player HTTP loop.

In-memory cache: at most 12 resource/season entries, single-flight under a lock, rates 15 minutes, schedule 60 minutes, failed requests back off 60 seconds. A refresh failure may retain public NBA data for at most six hours, explicitly marked stale. ESPN session caches and authentication behavior are unchanged. NBA fallback never replaces a usable ESPN team schedule or non-null ESPN rate. No private league responses enter this shared public cache.

## Additive interface

Existing normalized fields and schema version remain. Added fields:

| Location | Fields / semantics |
|---|---|
| `period` | `source`, `start_date`, `end_date`; corrected daily IDs, active `dates`/`remaining_dates` |
| acquisition settings | `matchup_add_limit`, `daily_add_limit`, `cap_source`, `unlimited`; legacy `weekly_add_limit` remains the verified matchup cap |
| team | `weekly_usage_source`, `weekly_usage_complete`; existing usage/remaining values now filled only from verified counters/settings |
| player | `health_status: available|out`, `health_source`; `droppable`, `undroppable`, `undroppable_source`, `lock_source`; `draft_pick`, `draft_round`, `draft_rank`, `draft_source`; `current_rates_source`, optional `current_games_source`/`nba_filled_rate_fields`; `schedule_source`; `identity: {nba_player_id,status,source}` |
| game | `game_id`, `source` in addition to existing schedule fields |
| snapshot | `history_coverage`, `enrichment: {rates_status,schedule_status,season}` |

Health policy follows user authorization: explicit OUT/INJURY_RESERVE/SUSPENSION/RESERVE_RETIRED is out. ACTIVE is available from ESPN; all other or absent statuses are assumed available with provenance. The raw injury status/boolean is retained. This layer adds no confirmation barrier; the planner/UI owns immediate per-player overrides.

## Remaining limits

There is no established per-player drop-lock expiry. Unknown locks remain null, allowing the authorized planner availability assumption. Missing matchup counter keys remain unknown; daily transaction rows do not prove weekly completeness. NBA Stats/CDN access may fail or be blocked. Static identities may lag new players. Weekly-calendar disagreement (for example an exceptional extended schedule) is marked partial; no nominal seven-day window overrides observed scoring data. Current season per-game minutes describe historical usage, not guaranteed future minutes. All transactions remain manual in ESPN.

## Primary sources

Inspected 2026-10-31:

- [ESPN client request implementation](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/requests/espn_requests.py), [basketball league](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/basketball/league.py), [player](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/basketball/player.py), [team](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/basketball/team.py), [constants](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/basketball/constant.py), [base league](https://raw.githubusercontent.com/cwendt94/espn-api/master/espn_api/base_league.py). These are community-client primary source, not official ESPN API documentation.
- Official read-only probes: `https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027?view=proTeamSchedules_wl` and public league `4487` with `mTeam`, `mSettings`, `mRoster`, `mDraftDetail`, `mMatchup`, `mMatchupScore`, `mScoreboard`. No private credentials supplied; no raw league data committed.
- [Official NBA schedule CDN](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json), [NBA client schedule endpoint](https://raw.githubusercontent.com/swar/nba_api/master/src/nba_api/stats/endpoints/scheduleleaguev2.py), [NBA client batch stat endpoint](https://raw.githubusercontent.com/swar/nba_api/master/src/nba_api/stats/endpoints/leaguedashplayerstats.py).
