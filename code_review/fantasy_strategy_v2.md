# Fantasy strategy V2 implementation review

Scope: fantasy_optimizer.py, fantasy_planner_adapter.py, focused synthetic tests
and engine documentation. Base 951e262abda859de2121a9697c018ce564dbef03. This is an
implementation self-review, not an independent review. CODE_REVIEW_GUIDE.md was
referenced by AGENTS.md but is absent at this base.

Findings addressed:

- Removed old per-player confirmation and nine-standard-deviation prerequisites.
  Unknown availability is assumed available; explicit Out/Available edits recompute.
- Seven unique pickup alternatives are separate from the add-budgeted sequence.
  Actual unknown budgets retain conditional rankings and never create a plan.
- Full roster forecasts subtract dropped starts, apply daily eligibility/crowding,
  and reserve slots already consumed by started active players independently for
  both teams. Clock-sensitive behavior is tested with an injected time.
- Current rates are primary from three observed games. Missing rates fall back
  explicitly; shooting makes/attempts never mix seasons. No fabricated schedules.
- Weighted percentage denominators and reverse turnovers remain correct. Unknown
  percentages preserve known-category rankings without inventing full-match odds.
- Draft/undroppable/core evidence protects season value; sustained lost replacement
  value and acquisition sample/role stability penalize marginal weekly upgrades.
- Prior-week explanations compare both teams in one completed period, separately
  from current actuals plus remaining contributions. Constant history variance is
  floored rather than blocking the planner or implying certainty.
- Missing market inputs exclude only the affected candidate; missing roster inputs
  suppress complete-forecast claims. Unknown-value Out players remain protected.

Validation: repository Ruff and full backend coverage suite; focused V2 tests
cover alternatives/budgets, season priorities/protection/costs, history/current
swings, punts, percentages/turnovers, current date/caps, toggles and missing inputs.
A synthetic 126-player, seven-day/ten-slot scenario hit the 1000-evaluation bound
in 0.93 seconds locally and returned seven options (timing is not an SLA).

Remaining risks: model estimates are not calibrated probabilities; independent
categories, fixed per-game roles and heuristic long-term cost omit correlations
and future injuries. Greedy matching and bounded improving-only beam search may
miss a better plan. No transaction execution, IR activation, waiver clearance or
unmodeled positional season caps. Daily acquisition caps require additional ledger
support and stay conditional. Integration must allow protected_ids through the
API allowlist (and optional UI automatic/max_recommendations if sent). The browser
worker owns that route/UI work and final combined production-chain verification.
No primary checkout/server/session was changed; no private league exports or
cookies were read, retained or committed by this engine worker.
