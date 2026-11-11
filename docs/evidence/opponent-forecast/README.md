# Opponent forecast policy and evidence

The reported understatement was reproduced from a normal authenticated read-only app snapshot, separately from synthetic verification. The old adapter replay exactly matched the visible end totals. Future opponent candidates already included ESPN bench players; the actual fault was opponent lineups inheriting the user's selected five categories and intentionally rejecting otherwise legal playing starts. The discovery forecast also used a different opponent from the subsequent focused baseline.

Full original private snapshot, official settings, both production-adapter replays, comparison table for both same teams, roster/date breakdown, reproduction scripts and SHA-256 manifest are retained in the assigned worker's private `data/` directory, outside Git. No credentials were exported. The task-bound parent report supplies their absolute paths. Private live observations are not established by these synthetic tests.

## Policy

- Keep observed roster slots for banked actuals, started-game slot reservations and IR legality. Future unstarted candidates include every owned available playing player, irrespective of current BENCH or unset slot. Real ESPN eligibleSlots remain exact.
- Opponent selection maximizes the cardinality of legal playing starts, capped by actual active league slots (at most ten supported). Among feasible maximum-size sets, rank independent marginal all-nine category utility using the existing weighted shooting/TO-aware assessment and deterministic augmenting matching. Minutes then player ID break ties. Each category has equal weight, using the existing disclosed positive deviation scales; percentage changes use summed makes/attempts, and lower TO improves utility.
- This prioritizes plausible full playing capacity rather than speculative opponent punts or strategic empty-slot benching. Harmful shooting/TO affect contention ranking, but do not intentionally empty an otherwise legal opponent slot. It is a deterministic heuristic, not a globally optimal aggregate weekly outcome or calibrated win probability.
- Establish the opponent ledger once in an all-nine discovery pass, before applying any explicit or automatic user focus. Freeze selected player/date/slot rows and decisions. User focus discovery, the final baseline, waiver whole-roster counterfactuals, guards, category summaries and daily views consume this same ledger and primitives. No additional future production is added for started games.
- Refresh recomputes from current provider rosters, rates, availability and schedules; no persistent opponent-ledger cache is added. Equivalent data is stable. User targets and modeled pickups do not alter the opponent ledger. The user's lineup policy remains focus aware.

Daily opponent `focus` now honestly lists all nine categories; user rows continue to list the selected five. The existing short forecast help explains opponent policy. No new panel or settings are required.

## Verification

`tests/test_fantasy_opponent_forecast.py` covers negative-focus benching, all-bench/unset/starter equivalence, maximum-capacity position matching with an independent small oracle, user focus independence, real beneficial waiver counterfactual conservation, IR/out/missing eligibility, locked starter and bench banking, equivalent refresh and roster/rate/schedule changes. Controlled provider tests run the actual provider→normalizer→adapter→optimizer with both NBA schedule and verified ESPN fallback.

`playwright.opponent.config.ts` runs `opponent-integration.spec.ts` against Vite 4219 and the production build on 8219. `tests/opponent_e2e_server.py` only replaces external data transports; there is no fake planner route. It uses synthetic league/rosters/rates and the previously observed public schedule. It verifies bench/starter invariance, focus invariance, unchanged refresh, changed-rate refresh, actual positional capacity, all nine categories, primitive/date conservation, short help, and mobile overflow. Screenshots stay in ignored test results. It is explicitly not private league proof.

The existing V7, V8, week-reset, V9, V10 and default browser suites remain required. V8/V9 assertions now distinguish opponent all-nine focus from the user's selected five; no behavioral assertions for user safety/outcome floors were removed. CI adds the new HTTP suite after the existing suites.

Historical official totals are authoritative. The live normalized snapshot supplies no last-week active-start count or acquisition history sufficient to decompose last week's production by today's roster. The private comparison states that limit rather than manufacturing historical eligibility.

Local validation: 546 Python tests; configured combined coverage 97%, game-center 96%, webapp 100%; 151 frontend tests, line coverage 94.31%; Ruff, Biome lint/format, TypeScript and build passed. Sequential browser suites passed: default17, V7=8, V8=2, week-reset=1, V9=4, V10=6, new opponent=2. Remote CI readiness is recorded separately in the task delivery evidence.
