# V7 combined schedule and compact forecast delivery

The waiver route now shows all nine current and end-of-matchup categories directly below ordered cards, with the final whole-plan total/change, W–L–T, five focus markers and Win/Loss/Tie text. Cards distinguish remaining scheduled games from usable lineup starts using backend action metadata. Full calculations and technical diagnostics stay collapsed by default. Known counting zeros remain zeros; missing contributions and zero-attempt percentages remain unknown. Complete baseline forecasts remain useful without recommended moves.

The exact delivered revision is the current typed delivery evidence / canonical PR head. Only humans merge. This is controlled-provider implementation proof, not a private-account or successful live NBA verification claim.

## Source provenance

- Exact accepted base: `80f2e6c26cf4d1f19acc78703538b9416c7fee9a`.
- Independent UI checkpoint: `9613f2699019355d50fdaa49a62203fd09b61752`. Original preparation evidence and screenshots remain unchanged in ../v7-forecast-prep/.
- Original SCHEDULE: `91b85cd73c706f996ac4c2e84290d0f4360a8636`, cherry-picked exactly as `11e36ab`. Canonical current source evidence `v7-schedule-91b85cd-1`, proven source completion and parent validation were read before integration. Retained parent/source evidence is in sources/; source contract is ../../fantasy_v7_schedule_contract.md; original checks, public responses and probe manifest remain unchanged in ../v7-schedule/.
- Parent preparation visual feedback is retained in sources/parent-prep-validation.md. Final screenshots use actual backend fixture rates/counts, not the illustrative prep target tiles.
- High-risk source and combined self-reviews: ../../../code_review/waiver-v7-schedule.md and ../../../code_review/waiver-v7-forecast.md. The referenced repository CODE_REVIEW_GUIDE.md is absent at the accepted base; review follows AGENTS.md criteria.

## Real HTTP / model evidence

`tests/v7_e2e_server.py` starts the actual app with controlled external provider transports. It executes the real ESPN client, NBA rate/team/schedule parsing and cache validation, normalizers, planner adapter and bounded optimizer. Browser pairing/challenge/refresh, selected-team/session, snapshot/forced refresh and plan calls use the real authenticated routes. There is no route.fulfill fake snapshot or plan. Two projects use Vite proxy4217 → backend8217 and the actual built bundle served directly by8217.

The full public ESPN schedule response captured by SCHEDULE supplies observed dates/opponents (IND3, BOS4, ATL4 for Nov2–8,2026). The converted NBA shape/IDs, league rosters, season rates and account tokens are explicitly synthetic. Rates are realistic per-game values, including 8-PTS roster players, 20-PTS pickups and 25-PTS opponent production, with 0.7/1.5/2 STL rather than illustrative 180-category chips. No fantasy transaction is submitted.

| Controlled league | Asserted behavior |
| --- | --- |
|701|Single roster IND3 vs opponent BOS4. NBA complete inventory replaces a cropped ESPN ATL map and supplies four pickup games/starts.|
|702|Two own IND players give six usable starts vs four opponent starts. Two distinct ordered pickups each use four games, dropping three starts. PTS baseline48 vs opponent100; whole-plan160, net+112. Both action scores form one coherent sequence. Baseline W–L–T1–8–0 changes to6–3–0. TO moves from a projected win to a loss; all-nine gains/harms and shooting are checked.|
|703|Thursday banked47PTS on both sides plus remaining usable IND1/BOS2. Baseline55 vs97PTS; pickup2 usable starts with four full-week observations and banked exclusions. FG baseline10/27, after21/47; FT baseline10/14, after15/20. No current/prior-week substitution or double banking.|
|704|IR roster has three remaining scheduled games and zero usable starts. Known counting zeros remain visible; 0/0 shooting stays unknown. No fabricated confidence.|
|705|Known exhausted allowance gives no moves but a complete3/4 baseline.|
|706|Both schedules unavailable: diagnostic partial totals are masked in the compact forecast, nine rows remain, sources/status are explicit and unknowns are not displayed as forecast zeros.|
|707|NBA transport failure with verified ESPN fallback remains forecastable. An actual changed reciprocal ESPN game/calendar anchor recomputes and switches the recommended pickup from100 to101; optimal total may legitimately stay equal.|
|708|Unknown acquisition usage with valid roster evidence retains a useful baseline without confirmed moves.|
|709|One lineup slot constrains two own three-game players to0/3 usable starts, with lineup-policy exclusions and full-team spillover arithmetic.|
|710|Thursday lineup-capacity scenario has two own BOS players: each four full-week/two remaining games, but0/2 usable starts, with lineup exclusions.|

All nine displayed current values and both baseline sides are checked against the HTTP response. After-plan values come from final projected team totals. Across all valid cases, eleven primitives satisfy actual+remaining=baseline for BOTH teams. Every action's primitive net satisfies Add−Drop+spillover and the whole-plan nine-category delta matches after−before; FG/FT use scenario makes/attempts. Default details remain closed, and five focus rows retain text markers.

Repeated forced observations advance actual provider timestamps, then a controlled provider cache clock crosses the five-minute schedule TTL (60/120/360 seconds) without blocking sleeps. No extra plan call occurs for unchanged facts, and edited16MPG filters, chosen targets, opened analysis, cards and comparison persist. Actual new NBA schedule facts at720seconds recompute and change final totals; source metadata confirms three remaining ATL games. A503 keeps the saved plan/comparison read-only. A cached-snapshot clock crossing tipoff supplies newly_started:user complete=false and withholds recommendations until actuals refresh. This tests lock semantics rather than inventing banked production.

`browser-final.log` is the passing8-check proxy/production run. browser-diagnostic*.log retain discarded harness/debug runs and are not passing evidence. Route counters, full response captures and refresh snapshots are retained here; captures larger than4KB are losslessly gzip-compressed as `.json.gz`. Tests regenerate readable JSON on rerun. Read using `gzip -dc FILE.json.gz`.

## Visual and accessibility verification

Inspected actual-route desktop1440, mobile390 and mobile320 screenshots for proxy/production, plus partial-provider mobile and no-deals states. All nine rows remain readable, each forecast cell fits, no document horizontal overflow occurs, and Full analysis & data stays closed by default. Help buttons expose meaning with focus/hover and touch; keyboard Escape dismisses without moving focus, tap toggles, and tooltip bounds remain within390px. Source schedule counts and usable starts remain separate. Historical V6/preparation screenshots regenerated by broad regressions were restored to preserve their original bytes.

## Gates and reproduction

- `uv sync --all-extras --dev`: pass (uv-sync.log).
- `uv run ruff check .`: pass (ruff.log).
- `uv run coverage run -m pytest`:498 passed, one existing BoxScoreTraditionalV2 deprecation warning (python-tests.log).
- `uv run coverage report`:97% combined; separate93% gates: game_center96%, webapp100% (coverage logs).
- `QT_QPA_PLATFORM=offscreen uv run python ... NBATerminal`: pass,9 pages (desktop-smoke.log).
- Bun lint /format:check /typecheck /build: pass (separate logs).
- `bun run coverage`:145 tests pass,94%+ lines against93% gate (frontend-coverage.log).
- `CI=true E2E_PORT=4217 bun run e2e`:17 regressions pass (browser-regression.log), including other Fantasy tabs and ordinary Game Center paths. These mocked/browser fixtures remain distinct from the real HTTP model suite.
- `FANTASY_E2E_PORT=8217 EVIDENCE_DIR=../../docs/evidence/v7-integrated/week-reset CI=true bunx playwright test --config playwright.week-reset.config.ts`:1 pass (week-reset.log), preserving the original usage lease, positive usage precedence and later missing-map unknown behavior. The config accepts an override so this allocation uses only authorized final ports.
- `bun test nba_terminal/browser_extension/tests/extension.test.js`:11 pass (extension.log); extension sources/packages unchanged.
- `bunx playwright test --config playwright.v7.config.ts`:8 real HTTP checks pass across both builds. CI now includes this suite after the existing new-week gate.
- Diff whitespace and owned-port cleanup pass. server-cleanup.json records no listeners on4216/8216/4217/8217. No user server, login, credential store or primary checkout was touched.

From web/, build once with `bun run build`, then run the V7 Playwright command. Fixture clocks/providers and test endpoints exist only in the test server. Production code never imports that server. Raw logs with trailing formatting are retained as `.raw.log.gz`; readable logs trim only line-end whitespace.

## Limits

Live public NBA CDN403 and NBA Stats timeout remain the observed source result; actual public ESPN full-season fallback returnedHTTP200. Original response bytes and exact timestamps/URLs remain in source evidence. The exact reason for the user's private two-start display is unverified; the cropped-map bug is reproduced, while legitimate banking/transaction/availability/lineup constraints remain enforced. No private account access, browser credential export, auth bypass, extension installation or fantasy transaction occurred.

The optimizer remains bounded and uses the disclosed lineup policy; no calibrated probability or global optimality claim is introduced. Modern80/82-game inventory verification, pending Cup windows, historical shortened seasons, provider freshness and partial market limitations remain explicit in the source contract. Missing required contributions block forecasts instead of becoming zero. PR CI/merge status and exact current HEAD are recorded by final task delivery evidence; only humans merge.
