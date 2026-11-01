# Player revision-2 integration evidence

Exact parent-verified source `d7e9aecbe0243ee95d9d282591479eaac7df9ef4` was cherry-picked without conflicts as `0b083ac`. Inspected canonical `nba-v5-player-rev2-final-1`: attempt `attempt-18e3f75ece243800-65698-0`, generation 1, accepted brief revision 2, current source commit and completed schedule match. Original completion artifact is retained verbatim in `player-source-completion.md`; its original source path remains in the artifact. Source review, probe logs, fixture provenance and API contract remain unchanged at `code_review/NBA_V5_PLAYER.md`, `code_review/evidence/v5_player_*`, `tests/fixtures/PLAYER_SOURCES.md`, `docs/v5_player_handoff.md`.

## Integration and remaining parity

Production App binds the real PlayerBrowser at `/players` and `/players/:id`; native Game Center Games/Players section links preserve season/phase. Existing `/game/:id/player/:id` and fantasy query routes remain. Backend shell reload/player APIs are the actual source routes, not fixture-only browser placeholders. Six measure APIs and six on-demand shooting breakdowns are wired; Usage MIN totals, Base MPG, count metrics, V3 turnoverRatio per 100 plays and unavailable values retain source units.

Source inventory exposed missing simultaneous different-player comparison. APP adds a searched second player to the existing sample explorer and keeps their requested season independent. The same opponent/stat/recent-window/threshold applies to both samples, each with explicit valid counts, SD/CV/quartiles and hit rates. Both players' charts are shown and each comparison log carries its own player ID/season/phase to actual game box scores. Same-player two-season comparisons still work. The current two-sample limit and absent helper's exact PNG/export format remain explicit; no claim of unlimited-card or absent-helper parity.

Profile hierarchy removes duplicate page headers and avoids loading a 30-name directory for an already selected direct profile until a query is entered. Positive/negative net rating uses green/red with signed numeric text; errors retain red labeled messages; the comparison section uses yellow emphasis. No page-level clipping masks overflow.

Installed PlayerGameLog reference headers use `Game_ID`/`Player_ID`; captured live source observation had successful history. APP now normalizes column casing before validation to support both mixed/uppercase provider variants. Regression and deterministic production transport deliberately use mixed-case Game_ID alone rather than permissively providing both variants. This is a schema-resilience fix, not a claim that source-worker live requests failed.

## Tests and original observations

- Whole repository Ruff passed. Full combined APP/FANTASY/PLAYER pytest after the mixed-case regression: 340 passed, 97% configured coverage (game_center 96%, webapp 100%). Raw log: `player-python-checks.log`. Final combined repository gates still run after LEGACY.
- Frontend lint/format/types/build passed. Full Vitest coverage: 91 tests, 93.60% lines at unchanged 93% threshold after the final compact-search adjustment.
- Eleven isolated headless Game Center/player flows pass, including compact schedule rows/N collapse, historical game link/reload, independent profile chart aspect at 1440/390 and full-width desktop consistency table.
- New `playwright.v5.config.ts` runs the served **production build** and actual API/cache/worker/service/normalizer boundaries on isolated port8195; only NBA transport is replaced. Two full flows at 1440/390 pass: independent search->URL selection->reload; all six measures; all six shooting tables; searched same-season second-player sample; responsive chart/table assertions; actual game box score->reload->selected player V3 metrics->reload->browser-back profile.
- First deterministic fixture run omitted the installed traditional endpoint's TeamStarterBenchStats dataset; corrected the fixture to satisfy the actual parser. A history assertion went back three entries instead of two; corrected the test to match browser history. Neither is a claimed live-provider bug.

`tests/v5_app_e2e_server.py` explicitly identifies its mixture: captured public V3/season/shooting response schemas, synthetic game logs/advanced season values/traditional box score, and a deliberately synthetic second-player dashboard row. No screenshot asserts actual historical player rates for that synthetic sample. The actual production services consume these provider shapes. Source worker's separate public live observations and captured real fixtures remain distinct from deterministic integration validation. No user Firefox/private ESPN access occurred.

Generated complete screenshots are retained locally at `code_review/v5_app/generated/player/` (`profile-*`, `shell-*`, `comparison-*`, `game-*`). Selected committed current screenshots are copied under `visual-evidence/v5-integrated/`. Screenshot labels identify deterministic transport, not live user data. Final all-feature images will be refreshed after LEGACY.

## Remaining gate

Exact completed LEGACY revision-1 source/evidence, actual router registration and AnalyticsTools binding, current complete feature-parity reconciliation and final full checks/PR/evidence remain pending. This document does not assert full task completion.
