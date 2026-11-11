# Opponent forecast self-review

Scope: fix independently reproduced opponent understatement at base `0de0a0d89c16e94de02865390ba27db1d4f3766f`. `CODE_REVIEW_GUIDE.md` is absent; review follows AGENTS priorities for correctness, API resilience, responsiveness, data honesty and structure. This is a self-review, not an independent review.

## Findings and fixes

1. **Incorrect objective / omitted starts.** Opponent `_lineup` received user `scored_categories`, and negative marginal value rejected playing players with open legal slots. Removed the coupling; opponent always ranks all nine and uses maximum legally matchable playing capacity. Positions are enforced by augmenting matching, with maximum ten active slots checked in the adapter. Strong shooting/TO costs still influence which players win contention. No claim of global aggregate optimality is made.
2. **Different opponent during focus discovery.** The first discovery forecast and the focused forecast could select different opponent starts. The ledger is now frozen immediately after the independent all-nine pass, before user focus discovery. All later baseline and waiver forecasts reuse those same player/date/slot rows. Metadata and daily focus now describe the actual opponent objective.
3. **Misleading rules provenance.** “Bench and IR excluded” could imply future bench players were unavailable. Provenance now specifies active slot rules, eligible future bench players and excluded IR players. The existing compact help describes the new policy.
4. **Regression fixture ambiguity.** Reusing V8's many opponent teams produced duplicated synthetic display names, so NBA identity matching truthfully fell back to ESPN samples. The new fixture isolates its two synthetic teams and verifies changes propagate through real rate normalization. This was test-data behavior, not a private data-access failure or a reason to weaken production identity checks.

## Preserved boundaries

Provider and normalizer data handling, schedule/rate caches, official banked actuals, already-started filtering, active-slot reservations, IR/out exclusion, exact ESPN eligibility, manual availability overrides, acquisition caps and pickup qualification are unchanged. PR20 category-result floors and PR19 dated ownership/acquisition-efficiency guards remain intact. No fantasy writes, primary checkout changes, authentication changes or server5173 lifecycle actions occur.

The extra independent forecast is bounded by the existing roster/date limits and occurs once per plan request; no per-candidate opponent search is added. This avoids UI/event-loop network work and keeps every downstream scenario comparable.

## Remaining risks and tradeoffs

Maximum playing capacity is a disclosed forecasting assumption; a real opponent may strategically bench to protect shooting or TO. Daily ranking uses independent marginal edges and does not globally optimize interacting shooting percentages or the full week. Uncertain injuries and small current-season samples can change actual results. Existing missing-data handling remains visible and incomplete data does not become zero production.

The live manual comparison uses official last-completed totals for the current user and current opponent, separately retrieved from their different historical matchups. It never substitutes the user's previous opponent. The private original snapshot and replay hashes are outside Git. Last-week active-start counts and transaction effects cannot be reconstructed from today's roster; the comparison expressly leaves that decomposition unknown.

Validation commands and exact results are recorded in the task evidence and PR. All existing HTTP suites and the new Vite/production suite must pass before readiness is claimed. Human merge remains separate.
