# V2 integration self-review

Scope: released DATA 6ef882cd792c1e271d8b0ea0977a759c60a48dcc and ENGINE be97df7ff847b443100351578e354a599d7afd68, frontend redesign and real HTTP wiring. CODE_REVIEW_GUIDE.md is absent at the accepted base. No independent deep review was requested.

Findings fixed:
- Raw ESPN injured=true can represent questionable status. Planner/UI now honor normalized available-unless-explicitly-out policy; explicit out statuses and manual overrides are tested through real adapter/HTTP paths.
- Planner remaining_adds is after its proposed sequence. Top UI shows actual pre-plan adds; sequence disclosure labels the remainder correctly.
- Shooting net gains need weighted before/after percentages, not absent raw percentage gains. UI derives them from category_impacts.
- Existing verified-count regression omitted new weekly_usage_complete/source fields. Its fixture now represents verified data explicitly; unknown completeness remains conditional.
- Six concurrent production browser cases exceeded the production bounded worker pool. Deterministic E2E uses two workers; capacity/busy behavior remains covered independently.
- General offline NBA fixture could accidentally bypass enrichment. New full-chain HTTP tests restore the real loader, mocking only external transport. Test server runs the real loader/cache/parsers as well.
- Visual review reduced nine large default cards and expanded roster controls to three target cards, collapsed all-category details, seven compact alternative rows and an explicit Edit availability control. Main target labels and top recommendation categories are checked together against actual engine output.

Validation: backend regression/required coverage plus supplemental changed-module coverage, frontend static/unit/coverage/build, existing browser regressions, production + Vite-proxy chain, synthetic desktop/mobile screenshots. Actual connected before-audit screenshots remain private outside Git. The primary 5173 process/session was not modified.

Remaining risks are documented in docs/fantasy-data-v2.md, docs/fantasy_optimizer.md and docs/fantasy-v2-ui.md: unofficial upstream availability, unknown transaction counts/daily ledgers, ambiguous identities, IR/lock timing limits, heuristic uncalibrated category and season-value model, bounded/greedy search. No merge or roster transaction performed.
