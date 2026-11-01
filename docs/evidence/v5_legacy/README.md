# Original standalone-tools validation evidence

All logs and screenshots originate in the isolated LEGACY worktree, accepted base15ffa760f605a3bdd4bffe8c0c25e72f5bca2a8a, 2026-11-01.

- `pytest.txt`: `uv run coverage run -m pytest`, **323 passed**.
- `coverage.txt`: `uv run coverage report`, **97%**, existing backend gate≥93%; webapp100%, game_center96%.
- `focused-python.txt`, `focused-coverage.txt`: `uv run coverage run --data-file=.coverage-legacy --source=nba_terminal.services.legacy_tools,nba_terminal.legacy_tools_api -m pytest tests/test_legacy_tools.py -q`, **17 passed**; report **98% combined / 100% statements**, router100%.
- `ruff.txt`: `uv run ruff check .`, passed.
- `vitest.txt`: `bun run test`, **81 passed across15 files**.
- `frontend-coverage.txt`: `bun run coverage`, same81 tests, **93.63% lines**, gate≥93% passed.
- `frontend-lint.txt`, `frontend-format.txt`, `frontend-typecheck.txt`, `frontend-build.txt`: `bun run lint`, `bun run format:check`, `bun run typecheck`, `bun run build`, all passed. These are accepted-base bundle checks; APP's eventual shell mount remains separate integration work.
- `playwright.txt`: `bunx playwright test --config playwright.analytics.config.ts`, **2 passed**, one complete six-tool flow each desktop1440×1050/mobile390×664 with touch/mobile emulation. Vite143 shutdown is the configured test-server SIGTERM, not a failed test. Isolated port5187; no user server/Firefox access.
- `desktop-*.png`, `mobile-*.png`: original **mock-provider fixture** Chromium screenshots for all six tools. Visible fixture banner. These do not claim live NBA/browser/private account verification. Representative desktop/mobile screenshots visually inspected for compact layout and local table overflow.
- `public-endpoints.txt`: actual public unauthenticated PlayerGameLogs and LeagueDashTeamShotLocations probes, raw row-count/schema observations and elapsed times.
- `live-service-smoke.txt`: actual six-service public/local smoke summary, not browser fixtures. Actual defense30 teams, AtlantaCV9, Nov1 schedule4/qualified29/evaluated29/no threshold rows; Curry GSW/LAL venue missing => incomplete projection. Notes48 and installed catalog query1. No private ESPN/account information was requested.

Formula parity tests compare original retained predictor directly against new calculations, and pin CV null/window/sample/zero conventions, defense schema/unknown/zero-attempt behavior, slate source filters/weights/sorts/partial counts, safe read-only notes and no-execution catalog. API injection test asserts service work leaves event-loop thread, validates inputs and covers all route contracts. UI tests cover six tool states, submitted context and explicit away/zero-rest overrides, stale response suppression, missing sample versus evaluated-no-trend distinction, text-only notes/back-to-search and metadata-only catalog.

The initial frontend coverage observation92.92% was corrected with meaningful explicit-context, no-evaluable-sample and note-navigation tests; final current result93.63%. No thresholds were weakened.

`original-logs.tar.gz` preserves the exact final stdout/stderr text files before trailing-whitespace normalization for clean Git diffs. No command results were changed.
