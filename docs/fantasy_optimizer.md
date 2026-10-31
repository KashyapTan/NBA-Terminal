# Read-only waiver strategy engine V2

`plan_waivers(payload)` is pure: no network, clock, writes or transactions.
`plan_snapshot_waivers(snapshot, preferences, now=None)` adapts authenticated
server-owned facts. The HTTP route continues to own authentication and bounded
worker execution. All examples/tests are synthetic.

## Automatic preferences and output

Adapter preferences require `context` with `league_id`, `team_id` and
`matchup_period_id`. `fetched_at` may be included, but a refresh within the same
league/week preserves choices. A changed league/team/week rejects stale choices.
Omitting `candidate_ids` selects the eligible, unrostered FREEAGENT pool; omitting
`droppable_ids` considers the user roster. Explicit arrays narrow either set,
including empty arrays to opt out. `protected_ids` protects additional roster
players. `player_overrides[id].injured` is the Available/Out toggle;
`.protected` overrides inferred protection. Known undroppable and first-round
value remain protected. No per-player health/lock confirmation is required.
`max_stream_slots` defaults to two in the adapter, supports one through four.

Legacy fields remain: `status`, `reasons`, `actions`, `baseline`, `projected`,
`remaining_adds`, `provenance`, `assumptions`, `limitations`, `data_gaps`, `search`.
`actions` and `plan` contain the same chronological, budget-constrained sequence.
`remaining_adds` is the balance **after** that sequence; it is null when unknown.

`recommendations` contains up to seven **alternatives**, one best explored
add/drop/date option per pickup ID. They are not seven moves to execute together.
`recommendation_kind` is `alternatives`. Each recommendation includes:

- `rank`, `date`, `add_id`, `drop_id`, `stream_slot` (original roster ID).
- `probability_gain` (uncalibrated five-win estimate improvement; null for partial
  shooting data), `estimated_win_gain`, `net_score`, `season_cost`, `season_value`.
- `gains` (net counting totals plus shooting makes/attempts), `games_gain`,
  `minutes_gain`, `category_probability_gains`, `category_impacts` (before/after
  values and margins, estimate gain and whether the projected lead flips).
- `target_categories`, plain-language `rationale`, `conditional_on_one_add`.

`strategy[category]` includes `classification` (`favored`, `swing`, `reachable`,
`punt`, `unknown`), `explanation`, `estimate`, `target_priority`, `lower_is_better`,
`current_user/opponent`, `projected_user/opponent`, `projected_margin`,
`previous_user/opponent`, and `historical_margin`. Previous values compare both
teams in the same latest complete earlier period, even if they played different
opponents. They never replace this week's actuals or get added to the forecast.
Historical values are null when unavailable.

`uncertainty` supplies `source` (`history`, `model_estimate`, `sensitivity`),
`calibrated: false`, and `margin_sd`. `score_basis` distinguishes the full
`five_category_model` from `known_category_estimates`. `protected_players` maps
roster IDs to protection reasons. Adapter `baseline/projected` keep the prior
frontend shape: `totals`, `opponent_totals`, `games`, `minutes`, `categories`,
`probability_five_wins`, `basis: forecast`. Pure forecasts also expose starts.

## Rates, schedules and availability

Rates use `pts, reb, ast, stl, blk, threes, to, fgm, fga, ftm, fta, minutes` per
game. Healthy current samples from three games use current rates exclusively.
Below three games, prior rates are a labeled fallback when present, otherwise the
small current sample remains labeled. Missing current rate fields can fall back
to prior values individually; shooting makes/attempts fall back as a pair to avoid
mixing seasons. Unknown observed sample counts use available current averages
with explicit provenance. Invalid fractional samples are rejected. No missing
rate or schedule is silently treated as zero production.

The adapter consumes observed `schedule[{date,start_at,started}]`, excludes past
and already-started games against supplied server time, and filters to remaining
matchup dates. Expected remaining minutes are the sum of each selected playable
game times current per-game minutes. Eligible daily lineup slots constrain starts
through position matching. A started active player consumes that day's slot;
user and opponent capacities are independent. Pure callers may supply exact
`lineup_slots_by_date` and `opponent_lineup_slots_by_date`, including empty lists.
IR activation is not modeled. Explicit OUT removes future contributions; a user
Available override recalculates immediately. Missing health/transaction locks
use the authorized assumed-available/unlocked policy, recorded in provenance.
Known locks and undroppable remain authoritative.

## Budgets and missing data

Use only actual matchup cap/usage, never season acquisition totals. The adapter
accepts `weekly_usage_complete` and `weekly_usage_source`; an explicitly incomplete
counter remains unknown. A compact manual override uses `user_confirmed_counts`
plus `weekly_add_limit`, `used_adds`, `available_adds`. All must be nonnegative
integers with used + remaining <= cap. Daily acquisition limits require a daily
ledger and keep alternatives conditional; no sequential weekly feasibility claim
is made. Unknown budgets retain strategy/baseline and conditional one-add
alternatives, with **no actions/plan** and null remaining budget. A known zero
budget yields no recommendations.

Missing candidate schedule/rates excludes that candidate only and records a
specific reason in `provenance.excluded_candidates`. Missing roster inputs marks
the forecast partial and suppresses numerical certainty and actions. An explicitly
out player without rates can contribute zero because they are out, while default
protection preserves their unknown season value. Missing shooting denominators
produce null percentages, not zero: known categories can still rank alternatives,
but five-win odds and sequential actions remain withheld. No remaining dates
retains actual category comparisons and explains why no future moves are modeled.

## Objective and model choices

Weighted shooting uses summed makes / summed attempts. Turnovers are lower-is-
better. Independent normal margin estimates yield an approximate chance of five
outright category wins; ties do not count as wins. This is a ranking heuristic,
**not calibrated odds**. Three complete prior team comparisons supply empirical
margin standard deviations, floored at 0.025 for shooting and max(2, 12% of current
combined volume) for counts. Without history, the same labeled model floors use
current combined totals or scheduled roster volume, whichever is larger. A caller
can still opt into sensitivity `margin_sd`; it is no longer required.

Category estimates >=0.8 are favored, <0.1 low-upside punts, 0.1–0.4 reachable
trailing, and 0.4–0.8 swing categories. Priority is `4*p*(1-p)`. These labels
reflect projected gaps relative to model variation, with prior-week comparison
shown separately. Search ranks full **net roster forecasts**, including lost drop
starts and lineup crowding, toward five wins; it does not count free-agent games
or minutes as the objective. Partial shooting rankings use the average estimated
win contribution of baseline-known categories, without inventing five-win odds.

Default protection covers ESPN undroppable/droppable=false, draft round one,
observed top-12 draft/season evidence, top-36 season rank, and established
30-minute core production with per-game value index >=3.5. User overrides can
release inferred top-36/production protection, but hard undroppable/first-round
evidence persists. The season value proxy is pts/25 + reb/10 + ast/8 + stl/1.5 +
blk/1.5 + threes/3 - to/4 + (fgm-.47*fga)/3 + (ftm-.78*fta)/2. These reference
rates are model assumptions, not asserted league averages. Acquired value is
discounted for small samples (0.6 + 0.4*min(1, observed games/15)) and sub-18-minute
roles (another 0.8). Positive sustained per-game value lost costs 0.035 score units
per index point. This preserves season opportunity cost beyond a tiny weekly gain;
it is not an exact season simulation. Every accepted move must have net gain
above 1e-5. Minutes break equal-score ties only.

Search is deterministic and bounded: 0–14 dates, <=1000 players, <=20 slots,
<=100 shortlisted candidates, <=32 beam states, <=4 original stream slots, no
re-adds. The adapter uses 1000 forecast evaluations; pure default is 2000, maximum
5000. `search` and `limitations` report exhaustion. Greedy daily matching and
improving-only beam search can miss combinations and global optima. Future rate
changes, category correlations, waiver clearance, unsupported league positional
season caps and transaction timing policies remain limitations. Recommendations
are manual ESPN decisions; the engine never performs transactions.
