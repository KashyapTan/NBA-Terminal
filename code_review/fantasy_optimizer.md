# Fantasy optimizer algorithm review

Scope: pure module and synthetic fixtures only. No API, frontend, credentials, external requests or transactions. Self-review; no independent review claimed. CODE_REVIEW_GUIDE.md was absent at accepted base 292e17885ae96613254c936c2189162a8b9bfa0f.

## Model and constraints

Forecast adds actual matchup totals to per-game rates for remaining supplied dates. Daily slot matching uses augmenting paths, preventing the same player or slot from being counted twice even with overlapping position eligibility. A greedy marginal-value ordering chooses which players fit crowded lineups. Opponent lineups similarly optimize their own approximate chance, a responsive-lineup assumption rather than observed future decisions. Minutes are an opportunity measure and tie breaker, never the primary waiver objective.

FG/FT aggregate makes and attempts before division. Zero attempts stay unknown. Turnovers reverse the margin sign. Current samples under ten games blend with prior-season averages when provided; otherwise small-sample provenance is explicit. Prior-only fallback remains identified. There is no projected injury recovery, fabricated schedule, default league add cap or silent replacement of unknown weekly usage.

Nine category normal margin probabilities feed a Poisson-binomial dynamic program for at least five wins. Standard deviations must be caller-supplied or derived from at least three nonconstant prior weekly margin observations per category. The units are counting-stat margins and fractional percentage margins. This is an uncalibrated independence model: real categories are correlated, sample rates drift, historical weekly uncertainty may not match the remaining horizon, and continuous normals ignore discrete tie probability. Probabilities are numerically bounded away from zero/one to avoid implying certainty. Category attainability labels use disclosed thresholds (<.1 unlikely, >.9 favored, otherwise swing); they are sensitivity labels, not guarantees.

Search uses chronological transaction ledgers and original roster-slot ancestry, at most four rotating slots, exact add charges, nondecreasing acquisition dates and no re-adds. Each forecast reconstructs ownership, so an acquired player contributes only while held. The effective budget is the minimum of verified remaining adds and verified cap minus usage. Locked drops/acquisitions, other-team and ineligible free agents, out/inactive players, unavailable dates, and off-schedule games are excluded. Negative raw/category gains expose turnover, percentage and other tradeoffs. No transaction is returned unless the modeled objective improves.

## Findings addressed

- Unknown ESPN weekly usage/remaining and null locks fail closed. Trusted or user-confirmed constraints belong in a later adapter, with provenance; null must never be coerced to false or zero.
- Missing shooting denominators, uncertainty or reported data gaps suppress probabilities/recommendations. A candidate that would leave zero projected shooting attempts is skipped.
- Existing matchup totals are retained, and every changed plan is reforecast in full; games/adds are not independently stacked into impossible lineups.
- Bounded player/day/slot/beam/candidate/evaluation limits constrain work. Search evaluation exhaustion is returned explicitly.
- All fixtures are synthetic and deterministic; payloads remain unchanged.

## Remaining risks / integration handoff

This is approximate improving-only beam search, not a global optimum. Candidate shortlisting uses single-game marginal value before complete dated simulation and can miss schedule-driven options. A beneficial combination requiring an initially harmful move can be missed. At most 14 remaining dates, 1000 players, 20 slots, 32 beam states, 100 shortlisted candidates and 5000 plan evaluations are accepted; defaults are 8/40/2000 for beam/candidates/evaluations. Evaluation count and exhaustion are visible, while beam/shortlist limits always apply. Request larger budgets only after profiling; do not execute substantial search on an async event loop.

No same-day game-time locks, waiver claim clearance, dropped-player cooldown or moves into/out of IR are modeled. Caller must provide only transaction-effective unstarted dates, explicit complete rosters/schedules, exact eligible slot names, verified availability/injuries, boolean transaction locks and trusted add constraints. Unknown injury outlook must be a data gap. A global transaction lock is conservative; day-specific game unavailability does not assert transaction availability. Future lineup intent may differ from the greedy assumptions. No adapter or production integration is included; no live league claims are made.

Verification: `uv run ruff check .` passed; `uv run coverage run -m pytest` passed all 100 tests; `uv run coverage report` passed backend coverage 97% (webapp 100%, game_center 96%); targeted `uv run pytest tests/test_fantasy_optimizer.py --cov=nba_terminal.services.fantasy_optimizer --cov-report=term-missing --cov-fail-under=93 -q` passed 38 tests with 96.76% optimizer branch-inclusive coverage. Remaining optimizer uncovered paths concern validation and search branches, not an asserted 100% gate. No frontend changes, Bun checks or live API calls were needed.
