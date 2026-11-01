# Empty ordered waiver plan diagnosis

Starting revision: `6edc9be237d2627a72e4ead50d7cc5dbb50b9087` (human-merged PR13).

## Actual user evidence

On 2026-11-01 the user supplied the current localhost text: 26 beneficial conditional alternatives; 12/12 legal drops evaluated; 804 evaluations; 398 candidates; acquisition limits or usage unverified. The market contained 800 observed players, with unknown provider total and partial coverage, fetched at `2026-11-01T17:20:41.074455+00:00`. The user confirmed a matchup cap of 7 and that 6 used was accurate **yesterday**. No current used/remaining count was supplied.

This establishes conditional opportunities, not evaluated-no-benefit and not known-zero-budget. The conditional state is emitted only after required roster, banked totals, rate, schedule and category-comparison checks pass. Acquisition verification withholds the ordered sequence. Partial market coverage separately limits the scope of the result; it does not cause the unknown-budget state. These observations do not verify a particular pickup's present ownership, transaction legality or availability.

## Live inspection and limits

- `127.0.0.1:5173/src/LeagueFantasy.tsx` served an inline source map whose `sourcesContent` exactly matched that file at PR13. The generic empty-sequence sentence is present there.
- Read-only process working-directory checks located the existing frontend and backend in the user's primary checkout. That checkout remained clean at PR13. This does not prove the Python process reloaded every module at that revision.
- Native `cua.getApp("org.mozilla.firefox")` timed out after approximately 6 seconds (`timeoutReached`); browser inventory reported Firefox running but `browsers=[]`. No Firefox inputs, login changes or session extraction were performed.
- Cookie-free localhost `/api/fantasy/espn/status` returned `connected:false`, which describes only that unauthenticated request, not the user's browser session.
- A bounded, redirect-disabled, unauthenticated read of the [ESPN league settings/team endpoint](https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027/segments/0/leagues/604550749?view=mSettings&view=mTeam) returned HTTP 401. No upstream body, credentials, cookies or private session payload was retained.

Consequently, the exact private source field rejected in the user's evaluation cannot be verified here. It may be current usage, the limit-period flag, missing/inconsistent remaining counts, or another acquisition-rule check. Do not present any one of these as an observed private field. The confirmed cap alone does not establish current remaining budget. Six used yesterday would imply one remaining only if no further acquisitions occurred and all relevant rules agree.

Original user text and clarification are retained by the parent at `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_PLAN_DIAG/user-current-status.md`. This document retains only safe counts, state and reason metadata.

## Data flow and guards

`espn_fantasy.py` requests `mSettings`/`mTeam`, then normalizes `settings.acquisitionSettings.matchupAcquisitionLimit`, `matchupLimitPerScoringPeriod`, and each team's `transactionCounter.matchupAcquisitionTotals[str(status.currentMatchupPeriod)]`. Missing/invalid current-period usage remains unknown; season acquisitions and single-day transaction rows are not substitutes. The existing cap fallback labels cap 7; it does not provide usage or verify a daily rule.

`fantasy_planner_adapter.py` accepts verified matchup counts or explicitly user-confirmed counts. A user cap fallback can combine with complete current ESPN usage only when the period rule is explicitly matchup-wide. A daily limit still needs a daily ledger. Invalid, incomplete or conflicting counts become unknown budget. Candidate ownership, free-agent eligibility, player schedules/rates and both full rosters remain guarded.

`fantasy_optimizer.py` scores the whole roster before and after each move, retaining banked actuals and adding only remaining usable starts. Net totals include pickup production minus lost drop production plus lineup spillover; shooting percentages use made/attempt totals. Search considers selected-five improvements, cushion/viability guards and season-value cost. Unknown budget allows competing one-move conditional comparisons while confirming no ordered moves. Known zero budget is distinct. Only complete inputs and positive budget can produce a confirmed sequence; bounded search never proves global optimality.

The UI previously displayed the same generic sentence whenever `recommended_plan.moves` was absent/empty. That obscured all distinct evaluation states even though precise status existed elsewhere.

## Change and proof

The empty ordered-plan section now names the state, displays the actual conditional alternative count, shows distinct provider/input reasons inline with additional reasons expandable, and offers the next action in the same section. Its recovery button opens the existing advanced controls. Backend diagnostics now identify missing cap, current usage, rule period, remaining count, invalid manual counts and conflicting totals separately. No acquisition, legality, data or scoring guard was relaxed; no current usage was hardcoded. N navigation and PR13 features are unchanged.

`desktop.png` (1440×1000 viewport) and `mobile.png` (390×844 viewport) are full-page screenshots of an isolated **synthetic** browser regression at port 4194. They prove rendering and recovery controls, not private ESPN state. The fixture deliberately models one conditional alternative and missing usage; it is not a reproduction of the user's 26 private alternatives.

Validation includes the complete Python suite and coverage, Ruff, frontend lint/format/typecheck/Vitest/build, and focused Playwright diagnosis/strategy/browser-setup checks. Exact final counts and commit are in the task delivery evidence and PR. The primary server, checkout and Firefox session were retained untouched; no fantasy transaction occurred.
