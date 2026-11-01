# V5 Game Center independent implementation

Task NBA_V5_APP, accepted base `15ffa760f605a3bdd4bffe8c0c25e72f5bca2a8a`, isolated branch `mx/NBA_V5_APP`.
This is intermediate implementation evidence, not final V5 completion or PR readiness.

## Implemented

- The N brand button toggles sidebar collapse using native button keyboard behavior, accessible expanded/control attributes, and a stored preference. The separate collapse arrow is removed. Mobile retains named navigation links and compact icons when collapsed.
- The schedule contains all statuses from today through today + 2 in Eastern league dates. Live and final games remain visible. Raw status text preserves postponements, overtime and source details; scores display only for underway/completed games. Start times render with the browser's timezone abbreviation; date grouping explicitly uses Eastern league dates.
- Two-column desktop / single-column mobile matchup cards are low-height rows. Live red, scheduled yellow, final green, white scores and grey secondary labels have text equivalents.
- Known NBA teams use NBA CDN primary SVG logos. Failed or unavailable logos retain team abbreviations alongside full matchup names. No logo URL is invented for unknown/All-Star teams outside the NBA static team lookup.
- Existing game/player detail routes and fantasy query deep links are preserved. Player/analytics subtab integration awaits the exact dependency contracts and commits.

## Sources and direct observations

On 2026-11-01, the production `_cdn_schedule_dataframe('2026-27')` fetched 1,274 rows from [the official NBA schedule CDN](https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json), with status counts 1: 1,119 and 3: 155. The browser research gateway returned 403; the app's existing public browser-header request succeeded. No private ESPN session was accessed.

`tests/fixtures/nba_schedule_2026_11_01.json` retains the public rows for November 1–4, flattened by the production CDN adapter and identified with their source. November 3 has no games in this snapshot. Tests run these rows through the actual `/api/upcoming` ASGI route, worker/cache boundary and production normalizer; provider transport is replaced with captured rows. This does not assert future live freshness or live scores.

[The official Boston Celtics logo](https://cdn.nba.com/logos/nba/1610612738/primary/L/logo.svg) returned HTTP 200 and `image/svg+xml`. That public SVG (line endings/trailing padding normalized in the repository copy; original bytes retained under `code_review/v5_app/generated/celtics-logo-original.svg`) is retained in `nba_terminal/web/e2e/fixtures/celtics-logo.svg` for deterministic screenshots. Browser tests deliberately fail the opposing team's image to check fallback. Screenshot score/status data is synthetic, not a live game claim.

## Checks before dependency integration

- Ruff passed across repository.
- Python coverage run including the captured-provider route test: 308 tests passed; game_center 96%, webapp 100%, combined 97%.
- Frontend lint, format, types, all 69 Vitest tests and production build passed.
- Isolated Playwright `E2E_PORT=4185` Game Center and existing game/player flow: six checks passed at 1440px / 390px. Card height <115px, useful wide rows, no document horizontal overflow, native Enter/Space toggle and reload persistence verified. A follow-up run replaced the illustrative logo response with the captured official logo.
- Retained screenshots: [desktop](v5-game-center/desktop.png), [mobile](v5-game-center/mobile.png). These use the captured official Celtics SVG and deliberate Cavaliers fallback. Final integration will retain separate current screenshots and rerun the combined checks.

## Outstanding integration

Parent-verified exact completed commits and evidence from NBA_V5_FANTASY, NBA_V5_PLAYER (plus Qt inventory), NBA_V5_LEGACY are required. No final publication, typed full-completion evidence, or done report is authorized by this intermediate document. Final feature parity and high-risk review notes will reconcile all dependency work.
