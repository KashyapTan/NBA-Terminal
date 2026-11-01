# V5 fantasy diagnosis and repair

Accepted base: `15ffa760f605a3bdd4bffe8c0c25e72f5bca2a8a`. Local task branch `mx/NBA_V5_FANTASY`; no publication or live roster/session writes.

## What the live evidence establishes

Automated Firefox inspection was **unavailable**: two documented native `cua.getApp("org.mozilla.firefox")` calls returned `Computer Use server error -10005: timeoutReached`. No DOM/session/cookie fallback was used. The actual page evidence is the user's pasted text, supplied through the parent, not an automated browser observation. Both teams explicitly had **complete ESPN official banked scoring**, with optional NBA reconstruction reporting repeated `schedule_missing` for days 7–13 and NBA logs unavailable. A displayed 0/0 denominator was unknown coverage, not verified zero eligible games. That optional failure alone does not block official scoring or establish no useful free agents.

A concrete reproducible production defect caused NBA logs to fail before any HTTP request: `PlayerGameLogs` was called with `per_mode_simple`, whereas the installed and current upstream constructor accepts `per_mode_simple_nullable`. Fixing the keyword returned **1,021 public player-game rows for 2026-10-26 through 2026-11-01**, season 2026-27. A regression retains the actual installed constructor and mocks only network execution, so permissive `lambda **kwargs` fixtures cannot hide this error again.

Public read-only observations (`live-probes.json`): NBA LeagueDashPlayerStats returned 441 season player rows; ESPN public schedules returned 31 professional teams and a consistent scoring day-zero anchor 2026-10-19; NBA ScheduleLeagueV2 fallback returned the correct season and 174 date groups. The NBA CDN request returned 403 **for this request**; the parent separately reports APP received the same season successfully (1,274 rows). Availability varies per request. The private league's unauthenticated endpoint returned 401, as expected: **this says nothing about the user's authenticated browser session**.

The exact future-plan blockers and current matchup usage have not been observed in the private session. The pasted source panels do not include those facts. No historical usage count is hardcoded, and no confirmed claim about today's best available players is supported yet. **Today's useful available players remain not yet determinable for this private league until its actual required forecast/ownership/eligibility/budget inputs are verified.** Public NBA data cannot supply private league ownership or acquisition usage.

## Changes

- Repair real NBA batch game-log transport parameter. Keep six-second timeout, cache/backoff, bounded worker execution and historical ESPN daily scoring eligibility requirements.
- Report eligible expected-game coverage as unknown (`null`) when calendar/history/eligibility/schedules do not establish the expected set. Retain complete official ESPN fallback; no fabricated zeroes.
- Five explicit additive `evaluation_state` values: `required_inputs_unknown`, `known_zero_acquisitions`, `evaluated_no_material_benefit`, `confirmed_ordered_plan`, `conditional_opportunities`. Legacy status remains compatible (`ready`/`incomplete`/`unavailable`). Adapter forwards the field. Unknown-budget output confirms no moves and no longer emits the contradictory no-benefit reason. Known-zero allowance explicitly says pickup benefit was not evaluated.
- Compact primary status and recovery control, expandable deduplicated diagnostics, and grouped optional reconstruction gaps. Empty totals do not produce a blank comparison table. Unknown optional-source coverage does not become a confidence warning against complete official banked scoring.
- Conditional pairs are expanded automatically when meaningful pairs exist, and retain all-nine arithmetic, losses, guards and protection overrides. `add_usable_dates` comes from actual modeled full-roster starts. The UI shows named pairs with usable starts today when supported, explicitly qualifying benefit as remaining-matchup net and budget-dependent when applicable.
- Missing unused prior-season samples no longer produce misleading missing-rate warnings when the selected complete current/NBA basis exists. Precise forecast gaps still come from the planner's required input validation.

## Research sources (read 2026-11-01)

- [Current NBA client PlayerGameLogs implementation](https://github.com/swar/nba_api/blob/master/src/nba_api/stats/endpoints/playergamelogs.py): accepted constructor/schema, including `per_mode_simple_nullable`.
- [Current NBA client LeagueDashPlayerStats](https://github.com/swar/nba_api/blob/master/src/nba_api/stats/endpoints/leaguedashplayerstats.py) and [ScheduleLeagueV2 endpoint](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/scheduleleaguev2.md): season-scoped public production and calendar boundaries.
- [ESPN client request implementation](https://github.com/cwendt94/espn-api/blob/master/espn_api/requests/espn_requests.py), [basketball player](https://github.com/cwendt94/espn-api/blob/master/espn_api/basketball/player.py), [team](https://github.com/cwendt94/espn-api/blob/master/espn_api/basketball/team.py): provider views, actual season samples and eligibility; client is unofficial, not an ESPN guarantee.
- [ESPN's transaction counter documentation](https://support.espn.com/hc/en-us/articles/47186978217748-Transaction-Counter): H2H weekly acquisitions can be adjusted by the league manager. Counting visible transaction rows or season acquisitions cannot replace the authoritative matchup counter.

## Validation and limits

Public provider fixture `tests/fixtures/fantasy_provider_observed_v5.json` contains trimmed actual public schedules/rates/log rows, no account data. These tests exercise observed schemas, not a private-account success claim. Full Python tests and coverage, frontend lint/format/type checks, Vitest, production build and deterministic real-route desktop/mobile Playwright are recorded in adjacent logs. Playwright replaces external ESPN/NBA transport with synthetic data, including unknown budget; it does not inspect the user's Firefox or private ESPN account.

Preserved V4 active `postponedStatus=A` handling, verified ESPN calendar/history, all-nine full-team counterfactual arithmetic, official restrictions, protection overrides, and uncertainty honesty. No change to App.tsx, styles.css, game_center.py, webapp.py or player modules. CODE_REVIEW_GUIDE.md is absent at the accepted base. Review found and fixed the real-constructor blind spot and distinguishes optional source failure from mandatory forecast inputs.

Screenshots under `visual-evidence/fantasy-v5/` show deterministic production-build desktop/mobile conditional status, not live account screenshots. Complete generated long-page screenshots and raw check logs are retained locally; compact status images are committed for review.

## Final check results

- `uv run ruff check .`: passed.
- `uv run coverage run -m pytest`: **315 passed**, 13.94s. `uv run coverage report`: **97% overall configured gate**, game_center 96%, webapp 100%; threshold 93% passed. Fantasy regressions participate in full pytest; configured coverage scope remains the repository’s backend gate.
- `bun run lint`, `bun run format:check`, `bun run typecheck`: passed.
- `bun run test`: **75 passed / 14 files**.
- `bun run e2e:fantasy`: production build passed, **12 Playwright tests passed** across Vite-proxy and production-build routes, including 390px mobile, unknown budget, visible conditional pairs and recovery control, all-nine arithmetic, protections, two-move ownership and unsupported-source states. Synthetic external transport only.
- `git diff --check`: passed. Compact production-build status screenshots visually inspected locally; no actual-user browser screenshot was obtained.

Generated full-page evidence is retained locally under `code_review/v5_fantasy/generated/` to avoid replacing the committed V4 reference screenshots or adding large duplicate images. Committed V5 compact status screenshots are suitable for parent/integrator review. The real local task evidence supplies the exact final commit after this report is committed.
