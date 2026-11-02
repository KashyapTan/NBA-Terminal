# V7 schedule / forecasting self-review

Scope: `fantasy_nba.py`, `espn_fantasy.py`, `fantasy_planner_adapter.py`, `fantasy_optimizer.py`, new bounded `fantasy_schedule.py`, backend fixtures/tests and source evidence. Base `80f2e6c26cf4d1f19acc78703538b9416c7fee9a`. This is a high-risk service/cache self-review, not an independent review. `CODE_REVIEW_GUIDE.md` referenced by AGENTS.md is absent from the starting checkout; the documented correctness, resilience, responsiveness and data-honesty expectations were followed.

## Findings resolved

- Existing ESPN-key precedence hid NBA games: select verified full fresh NBA inventory rather than filling only absent teams. Regression replays a cropped team through the production provider/adapter/optimizer.
- Nonempty/30-key parser output could certify partial coverage and false no-game/denominator claims: verify unique reciprocal 80–82 modern-season assignments, dates/anchors and statuses. Only individually verified ESPN team inventories survive unrelated provider omissions. Acquisition/no-start/bankable proofs require complete league coverage. A completed-only observed extract fails full-inventory attestation.
- Repeated NBA rows inflated starts, while string IDs/statuses failed joins: normalize NBA numeric team IDs and string statuses, deduplicate exact game IDs, reject conflicting active versions. Preserve regular-season repeated opponents on separate dates. Explicit PPD/inactive originals never add starts.
- One-hour schedule cache could obscure updates: new versioned key, five-minute TTL, bounded failure backoff. Validate before cache admission; stale NBA cannot override verified ESPN fallback. Cached failure preserves stale provenance.
- Last-game cropping lost explicit off days/end date: retain the full mapped matchup calendar. Matchup season ending-year mapping and NY basketball dates are tested across UTC midnight and DST.
- Ambiguous displayed starts: retain full-week observations through the adapter and expose full-week/remaining/eligible/usable counts plus per-date exclusions. Actual rosters are reprojected each action; net still includes drop loss and spillover, rather than rate times NBA games.
- Planner time could cross a game lock while the snapshot's banked actuals remained old: advance lock metadata and require an actuals refresh for newly started active games. No invented actual production and no doublecount.
- Full-inventory coverage was initially recomputed inside each player's denominator selection: moved to once per enrichment batch to avoid an O(players × season games) validation cost.

## Review evidence

Full Ruff and all 498 Python tests pass. Combined configured coverage is 97%, game-center service 96%, FastAPI webapp 100%. Evidence under `docs/evidence/v7-schedule/`. No network work was added at import time or in async handlers. Existing bounded worker architecture, credential boundaries, ownership/usage/protection guards, pickup sample thresholds, stable-card refresh behavior and weighted percentage/TO math remain intact. No server process was created.

## Remaining risks and explicit limits

- NBA public endpoints are blocked/timing out in this environment. Real NBA availability is unverified; actual public ESPN full-season fallback succeeded. NBA shape/cache tests are labeled synthetic, not private/live verification.
- The user's private displayed two starts cannot be attributed exactly without private input. The source-precedence failure is reproduced, but correct transaction/lineup/availability restrictions can also yield two; they remain enforced.
- Inventory validation is a conservative structural coverage proof, not a cryptographic guarantee of upstream correctness. Current modern 80/82-game assumptions fail closed for shortened historical seasons and incomplete Cup assignments; after Dec 20 a matchup requires 82 assigned games. Unknown or contradictory provider records can temporarily block a forecast rather than inventing starts.
- Daily lineup matching/plan search retain the existing bounded heuristic and optional benching policy, with disclosed search/lineup metadata. No global optimality or calibrated probability claim is added.
- Legacy direct domain inputs without full-week observations have null full-week counts. Incomplete forecasts may retain known partial diagnostic totals, but confidence/actions are blocked by component metadata. FORECAST must respect status/component completeness and use the exact delivered contract.
- Frontend forecast rendering and real HTTP proxy/browser evidence remain the explicitly separate FORECAST assignment. This delivery is local source only; parent validates and routes the exact commit.
