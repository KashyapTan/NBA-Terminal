# V7 schedule / forecast contract — final

Additive backend contract from base `80f2e6c26cf4d1f19acc78703538b9416c7fee9a`, branch `mx/NBA_WAIVER_V7_SCHEDULE`. No React, TypeScript, session or API edits. Parent validates this source commit and explicitly routes it to FORECAST for integration.

## Existing forecast fields

Planner `baseline` and `projected` retain `totals` (user end-of-matchup primitives), `opponent_totals`, all nine `categories`, `actual_primitives` and `remaining_primitives` keyed `user` / `opponent`, and `starts: {date, owner, player_id}[]`. For **both teams**, end total = banked actual + remaining usable production. Percentages use summed makes / summed attempts; turnovers use the reverse comparison direction. `categories[key]` exposes `user`, `opponent`, `margin`, `state` (`winning`, `losing`, `tied`, `unknown`) and existing heuristic edge fields. These edges are not calibrated win probabilities.

Existing `games` / `minutes` remain user remaining usable totals. Additions: `games_by_team` and `minutes_by_team`, each `{user: number, opponent: number}`. `projected` reflects the coherent ordered plan. Current all-nine comparisons can be calculated from `baseline.actual_primitives`; use existing end totals/categories for the end-of-week view.

## Schedule explanation fields

`baseline.schedule_explanations` and `projected.schedule_explanations` are objects keyed by ESPN **player ID string**, for modeled roster/candidate players. Each action additionally contains `schedule_explanations: {add: Explanation, drop: Explanation}`. The action add uses its after-lineup; the drop uses its before-lineup, both scoped from the actual effective transaction date.

`Explanation`:

| Field | Type / meaning |
|---|---|
| `full_week_games` | `number \| null`: all scheduled matchup games including started games; null if no verified full-week observation exists |
| `remaining_games` | `number \| null`: full matchup games not yet started at planner time, before availability/transaction/lineup restrictions |
| `eligible_games` | `number`: games inside the modeled remaining horizon, after effective/availability dates and active/health restrictions, before fitting lineup positions/capacity |
| `usable_starts` | `number`: actual selected lineup starts in that scenario, from the effective date |
| `effective_date` | NY date string `YYYY-MM-DD` |
| `source` | source name or null |
| `coverage` | snapshot `period.schedule_coverage`, or null for legacy manually supplied domain inputs |
| `exclusions` | `{date: string, reason: string}[]`; one primary reason per omitted observation |

Reason codes: `already_started_or_banked`, `before_transaction_effective_date`, `inactive_or_ir`, `unavailable`, `lineup_capacity_or_policy`, `not_on_roster`, `outside_projection_horizon`. Lineup capacity/policy includes position mismatch and intentional optional benching; it does not mean transaction-ineligible. Baseline candidates are not on the roster; use an action's add explanation to describe its usable pickup starts.

Existing `add_starts`, `drop_starts`, `add_usable_dates`, per-category `calculation.*.add_eligible_games` / `drop_eligible_games`, all-nine `arithmetic.categories`, and eleven-primitive `arithmetic.primitives` remain unchanged. True net is full user team after minus before, including lost starts and other-player spillover. Do not multiply full-week NBA games into these numbers.

## Source coverage and status

Snapshot `period.schedule_coverage`:

- `complete: boolean`: full league inventory and matchup assignment coverage verified.
- `reason: string`, `team_game_counts: {ESPNTeamID: number}`, `verified_team_ids: number[]`.
- `source: "nba_schedule" | "espn_schedule"`; `status: "verified" | "partial"`.
- `nba_status`: `fresh`, `cached`, `stale`, `unavailable` (or existing `not_needed` in test/legacy bundles).
- `fallback: boolean`, `fallback_reason: string | null`.
- `nba_coverage`: NBA inventory proof (`complete`, `reason`, `team_game_counts`, `verified_team_ids`) or null.
- `source_request: string`, `fetched_at: string | null`.

Planner/snapshot `projection_metadata.schedule_coverage` has the same shape but its `complete` specifically attests the required active own/opponent professional teams. A missing unrelated team can make league-wide coverage partial while verified required teams remain forecastable; missing teams never become empty schedules. The acquisition cap and no-started/banking proof still require complete league coverage.

New `projection_metadata["newly_started:user" | "newly_started:opponent"]`, when present: `{complete: false, source: "server_clock_game_locks", reason: string, player_ids: string[]}`. It blocks confidence/actions until banked actuals are refreshed when active games start after the snapshot.

Respect top-level `status`, `reasons`, `data_gaps`, and component `complete` flags. Incomplete forecasts retain diagnostic partial known totals but cannot be labeled complete; missing contributions are unknown, not zero. Existing `_invalidate` clears confidence/category strategy labels and recommendations together.

## Provider behavior

NBA CDN first, then season-explicit NBA Stats `ScheduleLeagueV2`. NBA full-season coverage is verified **before cache admission**; a fresh verified NBA inventory replaces existing cropped ESPN team maps. ESPN's unfiltered season-specific public schedule is the explicit fallback. No successful NBA public response was observed in this environment: retained CDN responses are 403 and Stats timed out. Production NBA shape tests are synthetic, separately labeled from the actual ESPN response.

Season `2027` maps to `2026-27`; NBA team IDs normalize to ESPN team IDs, player IDs remain provider-specific. UTC instants determine NY basketball dates (including DST). Active (`A`) postponedStatus is retained; inactive/postponed originals, exhibitions and Cup final are excluded. Exact duplicates are removed; conflicting active same-ID observations invalidate affected teams. The matchup calendar includes off days, and started/locked games do not project again.

Modern season coverage requires 80–82 reciprocal unique regular-season assignments per team. Pending Cup windows remain unknown; after December 20, fewer than 82 assignments cannot certify a matchup. Unsupported historical shortened seasons fail closed. Schedule cache TTL is five minutes with a new versioned key; failed/partial refreshes cannot replace a verified cache entry or promote stale content to fresh. Stale NBA content cannot override verified ESPN content.

Evidence and root-cause scope: [source/check report](evidence/v7-schedule/README.md), [self-review](../code_review/waiver-v7-schedule.md). No private league verification is claimed.
