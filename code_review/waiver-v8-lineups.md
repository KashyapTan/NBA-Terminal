# V8 high-risk self-review

Scope: both-roster math audit, automatic/explicit focus alignment, position matching exposure and compact daily UI. CODE_REVIEW_GUIDE.md was not present in this checkout; applied the correctness/resilience/responsiveness/data-honesty expectations from AGENTS.md.

Findings fixed:
- Automatic category selection had reused nine-category lineups while displaying a chosen five. Automatic discovery now freezes a disclosed focus before all actionable forecasts/search; explicit requests already selected five. Both-side utility follows that focus; opponent starts remain fixed for coherent before/after transactions.
- Forecast starts lacked assigned positions and there was no safe UI decision contract. Exposed exact source decisions, not frontend stat sorting. Current owned roster is default; after-plan explicitly hypothetical.
- Started/banked slots were excluded from future starts but invisible. Adapter adds locked display rows using original observed schedule and active slots, without multiplying banked production again.
- Distinguish optional harmful-focus benching from capacity/position failures. Empty schedules never manufacture starters; missing position rules fail closed. Observed ESPN eligibleSlots are exact (including UTIL), while legacy domain inputs retain their generic UTIL semantics. More-than-ten configured active slots reports a mismatch.

Preserved: banking attestations, weighted shots, TO direction, ownership/ordered transaction dates, sample gates, roster protections, all-nine/spillover arithmetic, schedule inventory fallback, stable lifecycle, worker limits and read-only/manual ESPN behavior.

Evidence: ../docs/evidence/v8-lineups/ contains original local logs, JSON HTTP artifacts and desktop/mobile captures. Controlled provider tests run the real routes, normalizer, adapter and optimizer through Vite proxy and production static serving. No private-account verification or global optimality claim. The small oracle verifies the independent marginal-score matching case, not global aggregate-week optimality. Remaining limitation: same-day transaction ordering/provider drop-lock semantics retain prior disclosed assumptions. Public NBA transport access remains unverified, with existing ESPN fallback retained.
