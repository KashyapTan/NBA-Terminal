# V8 original audit and integrated evidence

Task NBA_WAIVER_V8_LINEUPS; branch `mx/NBA_WAIVER_V8_LINEUPS`; exact starting revision `3d1e5c716e58d1daa7e05979fe33a2d7d5864c2a`. Work occurred only in the assigned isolated allocation. Final exact-HEAD typed delivery/PR/CI evidence is recorded through the task model, separately from this commit's artifacts.

## Plain answer to the original question

The math is banked actuals plus each player's season averages multiplied by their **remaining usable lineup starts**, summed separately for both teams. Midweek it does not multiply every roster player by the full week's games. FG/FT are weighted total makes / attempts; fewer turnovers wins. Plan net includes the dropped player's production and displaced starts.

The previous automatic-focus path did not consistently choose lineups for its displayed five categories. That mismatch is fixed. The daily Start/Bench section renders exactly the forecast's decisions, respects the configured ESPN positions and the user-confirmed maximum of ten active players, and starts only available players with remaining games. Position restrictions and disclosed intentional focus benching can leave fewer than ten. Current roster is default; after-plan preview is explicitly hypothetical. This is bounded greedy matching / best explored plan search, not a global optimality guarantee. Actual private league slots/eligibility were not accessed during development.

## Original artifacts

- [Initial base audit](audit.md): code findings and public ESPN rule references, reported early to the recorded parent.
- [Final contract](../../fantasy_v8_lineup_contract.md) and [self-review](../../../code_review/waiver-v8-lineups.md).
- `vite-proxy-*` / `production-build-*` JSON: actual HTTP plan/snapshot responses from controlled provider transports through production routes, ESPN normalizer, planner adapter and optimizer. JSON artifacts are gzip-compressed without changing their original bytes.
- `*-plan.json.gz`: thirteen owned / twelve opponent players, ten actual position slots, distinct nonzero banked actuals. `*-11-plan` / `*-12-plan` cover smaller overcrowded rosters; `*-focus-change` proves legitimate focus changes; `*-ordered-plan` proves current ownership vs dated hypothetical transactions and all-nine full-team net.
- `*-desktop.png`, `*-mobile.png`, `*-320.png`, `*-forecast-*`, `*-hypothetical-mobile.png`: original browser captures; desktop and 390px/320px reviewed for overflow, slot/name clarity, nine-category forecast and preview labels. Help tested via pointer, keyboard and mobile tap.
- `regression-v7/`: original existing integration snapshots/plans/screenshots, redirected here to preserve historical artifacts. `v7-owned-remap.patch.gz` and `v7-owned.config.txt` retain the exact port/output-only remap to owned 4218/8218; temporary test copies were removed.
- `browser-regression-images/`: newly generated existing browser/new-week captures; prior tracked evidence was restored byte-for-byte.
- `server-cleanup.json`: both owned listeners absent after all local tests. No primary checkout, 5173 server, credential store or user login was changed. No fantasy transactions, lineup writes or merge.

## Checks

| Check | Result / log |
|---|---|
| `uv run ruff check .` | Passed, `ruff.log` |
| `uv run coverage run -m pytest` | 513 passed; one existing provider deprecation warning, `python.log` |
| `uv run coverage report` | Combined 97%, `python-coverage.log` |
| Game center / webapp coverage (93% gates) | 96% / 100%, `coverage-game-center.log`, `coverage-webapp.log` |
| `bun install --frozen-lockfile` | Passed, lock unchanged |
| `bun run lint`, `format:check`, `typecheck` | Passed, corresponding logs |
| `bun run coverage` | 148 tests; 94.32% lines, `frontend-coverage.log` |
| `bun run build` | Passed, `build.log` |
| `E2E_PORT=4218 bun run e2e` | 17 passed, `browser-regression.log` |
| Existing V7 HTTP integrations, owned port remap | 8 passed, `v7-regression.log` |
| `FANTASY_E2E_PORT=8218 bun x playwright test --config playwright.week-reset.config.ts` | 1 passed, `week-reset.log` |
| `bun x playwright test --config playwright.v8.config.ts` | 2 passed (proxy + production), `http-final.log` |
| Qt offscreen instantiation | Stack count 9, `desktop-smoke.log` |

V8 deterministic tests cover 11–13 players, illegal raw top-ten position combinations, both-side overcrowding/banking, focus replay, exactly-ten / fewer / zero schedules, availability overrides, locked starts, missing/excess capacity/positions, dated ordered ownership, weighted shooting and TO harm, explicit policy benching, frozen opponent explanations and all-nine reconciliation. A small brute-force oracle verifies one independent marginal-score matching case; no aggregate global optimum is claimed.

Early `focused-initial` / `http-initial*` logs retain corrected test-development failures (obsolete 126-set expectation, test fixture position assumptions, incomplete target-checkbox reset and wrong test refresh label). `http-final.log` and final gate logs are the authoritative passing observations. Public NBA live access and private-account data remain unverified; existing verified ESPN schedule fallback and incomplete-data labels remain intact.
