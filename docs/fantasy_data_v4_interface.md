# NBA-first V4 data contract

Additive service interface; existing `team.totals` remains the official ESPN score.
The engine/UI integrator owns consumption in `fantasy_planner_adapter.py` and display.

## Banked production

`EspnClient.snapshot()` enriches selected team and matchup opponent with `team.actuals`:

- `official`: ESPN `totals`, `source`, `fetched_at`.
- `nba_derived`: independently joined primitive `totals` and weighted percentages, `complete`,
  `provisional`, expected/covered player-game counts, exact missing facts and fetch timestamp.
  Missing history with no observed production yields `totals: null`, never a fabricated zero.
- `forecast_source`, `forecast_totals`, `forecast_complete`: deterministic selected banked basis.
  Fresh complete NBA coverage wins; otherwise complete official ESPN totals; otherwise unknown.
  `provisional` also marks fully covered games still in progress. No projected live-game remainder.
- `sources`: NBA resource status and original cached provider fetch timestamps. Source update
  timestamp is null where the feed's update time is unverified. `discrepancy` compares only a
  complete NBA reconstruction with complete official totals.

Pass `actuals.forecast_totals` to engine `current_totals` / `opponent_totals`. Honor
`forecast_complete` and snapshot `projection_metadata`. Do not silently substitute a partial
NBA sum for official totals. `actuals_coverage` records history failures and request bounds.

NBA rows use `(NBA game ID, NBA player ID)` replacement keys. ESPN game IDs are never sent to
NBA endpoints. A single date-bounded league-wide PlayerGameLogs batch supplies actual totals;
at most 16 relevant NBA games use shared boxscore reads. Live rows replace equal keys.
Started games are banked only; the existing future schedule filter must continue excluding them.
This omits any unplayed live-game remainder, rather than adding a full projected game twice.

Every historical day requires ESPN's explicit `rosterForCurrentScoringPeriod.entries`, an echoed
requested scoring period and matchup ID, side-owned daily player entries, and verified active
slot eligibility. Bench, IR/IR+, unknown eligibility and conflicting ownership cannot receive
credit. A former roster member can receive correctly banked production; current-only roster
members cannot. No current-roster history proxy exists. ESPN-aligned day/calendar mapping is
required before NBA reconstruction is considered complete. At most 14 history days are read.
Private history may remain unavailable; complete reconstruction is not promised.

## Season rates and schedules

`player.current_rates` is NBA current-season primary, including GP 1/2; preserve
`espn_current_rates` and `nba_rates` as separate samples. Shooting pairs never mix providers.
`player.season_rates` is the selected sample; `rate_provenance` includes source, exact season
when available, games, small-sample flag, fallback reason, status and fetched timestamp.
Selection is NBA current, ESPN current, then ESPN prior when no current sample exists.
Stale NBA does not displace usable ESPN current rates. Missing values remain null.

The planner must consume `season_rates` and `rate_provenance` rather than its old GP >= 3
fallback rule. Incomplete primitives still require normal planner validation; no absent field
is a zero. Per-player rates are coherent samples, not cross-provider field blends.

Fresh NBA schedule is primary, ESPN is fallback. Explicit empty schedules mean known no games;
absent/unparseable team schedules remain unknown. Unknown game timing invalidates affected
team schedule coverage rather than silently discarding that possible game. ESPN daily calendar
anchors align NBA schedule dates; NBA-inferred scoring-day numbering alone is not verified
historical fantasy eligibility. `schedule_source` remains present for verified empty schedules.

IR/IR+ roster members remain available as legal drop identities with `active: false` and ESPN
lock/droppable provenance. The planner must retain them as drops and schedule no starts or
implicit activation. IR status does not bypass locks or ESPN transaction validation.

## Acquisition and market coverage

Use `league.acquisition_settings.cap_source` when explaining the cap. Explicit 0 is retained.
A genuinely absent/null cap receives 7 with source `league_fallback_7`. Explicit unlimited or
ambiguous daily rules are not reinterpreted as weekly 7. `weekly_used_adds` comes only from the
matchup transaction counter, including explicit zero. No used count is invented. The engine
adapter must preserve fallback cap provenance rather than relabeling it as ESPN-confirmed.

`market_complete` / `market_coverage` describe upstream market coverage independently of
required roster/rate/schedule/actual completeness. Pages use limit 100, offset and deduplication;
stop at exhaustion/provider total or max 800 observed entries. Repeated pages, malformed
responses, later-page failures and bound exhaustion remain partial. This does not block a
verified matchup forecast, but qualifies search as best explored over observed candidates.
Pagination is not an atomic ownership snapshot and is not a provider completeness guarantee.

## Worker and cache boundary

All calls remain synchronous inside the existing bounded snapshot worker path; no imports do
I/O. Per-key single-flight releases the global metadata lock before network calls. Cache is
bounded to 64 resource keys, failures back off 60 seconds and labeled stale values expire after
six hours. Rates TTL 15 minutes, schedule 1 hour, log batch 60 seconds, live boxscore 30 seconds.
The existing outer session snapshot cache bounds private daily-history reads to refreshes.

## Integration checks still owned by final integrator

Wire the selected banked/rate inputs into the engine adapter; retain legal IR drops; expose
source/freshness/partial state in UI; ensure confidence labels honor all projection metadata;
verify production-shaped recommendations and rendered arithmetic. This service branch does
not change the optimizer, frontend, login, credentials or transaction behavior.

Final integration correction: `postponedStatus=A` is an active ScheduleLeagueV2 row, including completed games; inactive/PPD/Postponed originals are excluded while active reschedules retain their proper date. `projection_metadata.matchup_calendar` now carries ESPN date-anchor verification. Unverified future calendar blocks plans and confidence; unavailable private NBA history alone still permits complete ESPN scoring fallback.
