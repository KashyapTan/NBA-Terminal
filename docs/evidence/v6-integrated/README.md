# Waiver V6 combined delivery evidence

The compact waiver route is integrated with current-season qualification, ordered planning and stable session/refresh lifecycle. The exact delivered revision is the task delivery evidence / PR head. This is fixture-backed implementation proof, not verification of a private ESPN account.

## Original sources

- Exact starting base: 4e9f94f51fa2ab402e2a913023bfc28a49358553.
- Independent UI: 1e78444fb69095be444b4e58a25f77bffa7906d0.
- ENGINE original: 8b38a377c83bc72611551a8899d4c7bfd13a918a; cherry-pick af24991. Original handoff and parent validation: sources/engine-handoff.md and sources/engine-parent-validation.md. Final contract: ../../fantasy_v6_engine_contract.md. Original review/probes/check logs: ../../../code_review/v6_engine/.
- CONNECTION original: 3cff75cfa1c4a4b016cfa63a859c3ac9485acfed; cherry-pick bc95479. Original handoff: ../v6-connection/handoff.md; parent validation: sources/connection-parent-validation.md. Final contract: ../../v6-connection-contract.md. Original lifecycle review: ../../../code_review/v6-connection-lifecycle.md.
- Design references, original props contract and preparation captures: ../../../code_review/waiver-v6-design.md. Combined correctness review: ../../../code_review/waiver-v6-combined.md.

## Actual HTTP / model proof

`tests/v6_e2e_server.py` replaces ESPN/NBA provider transports with explicit synthetic data on a controlled synthetic 2026-10-31 basketball date, with observation timestamps advancing by real elapsed wall-clock time. It runs the actual application, authenticated pairing/session routes, normalizer, planner adapter and bounded optimizer. No browser route.fulfill planner/snapshot answers are used in this suite. Vite proxy4214 targets production backend8214; the second project loads the real built bundle directly from8214.

Tested routes include bridge pair/challenge/refresh/status, session status, snapshot and forced refresh, compare_team_id, authenticated plan, public fallback connect, team PUT and connection DELETE. Actual plan requests carry target categories, pickup_filters (participation as a fraction), player availability/protection and core override. Request counts are retained in *-route-counts.json. Other Fantasy tabs and navigation are exercised separately by the ordinary browser regression suite.

Controlled scenarios (JSON response captures are stored losslessly as .json.gz):

| League | Provider facts / expected result |
| --- | --- |
|601|Two qualified 15 MPG /2GP /4teamGP pickups, plus 11MPG /1GP excluded for minutes, games and participation. Two distinct positive sequential moves; step2 starts at step1 score. All nine arithmetic rows retained. Complete official ESPN totals remain usable during optional NBA schedule/reconstruction outage.|
|602|One distinct qualified pickup gives one legal move with allowance left; no further beneficial explored continuation, no claim about all free agents.|
|603|Known exhausted acquisition budget; zero moves.|
|604|Only low-sample player available; zero qualified pickups.|
|605|Completed team denominator unavailable; explicit exclusion, official scoring remains complete, no fabricated denominator/pass.|
|606|Required schedule/context missing; incomplete plan and compact failure status.|
|608|Qualified pool with no material improvement; zero beneficial explored moves.|
|609–612|14.99 MPG, GP1, 2/5 participation and prior-only observation each fail the corresponding current-season qualification gate. Exact 15/2/50% boundary qualifies in601.|
|613|Whole matchup usage map absent; allowance remains unknown and no confirmed ordered moves.|
|614|30 qualified candidates, seven-add budget, two beneficial explored moves. Actual 4910 evaluations /depth7 with layer/beam pruning; compact search-limit status, no global optimality claim.|
|615|Two positive moves against active drops. Each explicitly shows REB Add6 /Drop10 /Net−4 (red Loss), with gains in the selected five. Drop usable starts are nonzero.|

Assertions verify backend Add−Drop+spillover=Net, before/after differences, weighted makes/attempts, distinct pickup IDs, sequential scores, all-nine table rows, sample display, exclusion reason display, compact card dimensions, details closed by default, no horizontal overflow, retained cards and filters. The adjustable 10MPG/1GP/25% request genuinely admits the third low-sample candidate; controls are not cosmetic.

## Refresh and error proof

browser-current-full.log is the final full16-check run on both proxy and production. It includes three actual minute-long refresh intervals on EACH build, with advancing provider observation timestamps (no browser clock override). *-cycles.json records three snapshot increments, no extra plan calls and no strategy unmount; *-lifecycle-sources.json.gz retains the changing sample/denominator observations. Same cards remain visible/read-only through503/429/504; recovery and manual refresh work. Slow snapshot and out-of-order plan responses cannot replace newer results. Definitive401 removes cards and exposes reconnect navigation.

Cross-source review caught that ENGINE's new sample_as_of was outside CONNECTION's earlier observational timestamp allowlist. The integrator now compares the snapshot/sample/denominator qualification dates in New York, suppressing intraday observation churn while retaining date-boundary/invalid-evidence changes. Unit regressions cover same-NY-day observations across UTC midnight, next-NY-day changes and genuine GP edits. The final fixture's advancing timestamps ensure a frozen clock cannot conceal that issue.

Earlier browser-final.log, browser-visual-final.log and browser-final-visual-review.log retain passing intermediate checks. browser-diagnostic.log is a discarded test-harness diagnostic, not passing evidence. The final full run supersedes preparation/intermediate runs. The final cache-renewal supplement (browser-cache-final.log) reruns all16 fast project cases after also handling provider *_fetched_at observations and the current NY qualification day. Its two new cache-renewal checks force three actual provider batch renewals per build, record distinct batch/sample timestamps and verify zero additional plan calls (*-cache-renewal.json). The current suite has22 project checks (20 fast +2 sustained). The full16 run,16-case cache supplement and4-case compatibility supplement (browser-compat-final.log: scoped cap and private manual ownership) cover their union. current-identity-proof.json applies the final snapshotIdentity function to the actual sustained HTTP captures: four distinct sample timestamps map to one semantic identity in each build. No browser planner/snapshot mock substitutes for the actual routes.
Inspected production/proxy screenshots: *-active-tradeoffs-desktop.png, *-active-tradeoffs-mobile.png, *-mobile-touch.png, *-mobile-filter-help.png, *-required-data-failure.png and *-saved-503.png /429/504. Final default page has short bold headings, five baseline category tiles (Before moves), compact ordered Add/Drop/Net cards with genuine sample, and bottom Full analysis & data closed. Non-target harms are visible, with Gain/Loss text as well as color. Keyboard hover/focus/Escape (including retained Escape dismissal after pointer leave) and real touch tap toggle are checked; filter tooltip bounds stay inside390px. Other Fantasy headers remain unchanged. browser-help-final.log and browser-keyboard-final.log retain the final touch and keyboard dismissal reruns.

## Gates

- UV Ruff: pass (ruff.log).
- `uv run coverage run -m pytest`:477 pass, one existing BoxScoreTraditionalV2 deprecation warning (python-tests.log).
- `uv run coverage report`:97% measured total,96% game_center,100% webapp (python-coverage.log).
- Bun Vitest coverage:138 pass,94.16% lines against93% gate (frontend-coverage.log).
- Bun lint /format:check /typecheck /build: pass (corresponding logs).
- `E2E_PORT=4213 bun run e2e`:17 pass, including Game Center, profiles, Fantasy stats, Matchups, navigation and compact waiver UI (browser-regression-final.log). These component/regression mocks are separate from the real HTTP evidence above.
- `bun test nba_terminal/browser_extension/tests/extension.test.js`:11 pass (extension.log). Connection's original v1.0.1 source/packages retained.
- New-week production CI regression:1 pass (week-reset-ci.log), preserving the immutable zero evidence lease, positive usage precedence and unknown state after later map loss. Its fixture now supplies explicit observed team GP; unchanged observation refresh retains the existing plan.
- The supported `bun run e2e:fantasy` command now targets the comprehensive V6 suite. The older standalone V5 production config is retained as historical troubleshooting, not the supported current-UI gate.
- Diff whitespace check: pass. Final owned4213/4214/8214 listeners closed (server-cleanup.json). Playwright's SIGTERM/143 Vite teardown messages are normal owned-server cleanup, not check failures.

To reproduce: from web/, `bun run build`; `bunx playwright test --config playwright.v6.config.ts` runs both fast and real wall-clock checks. Ports are isolated; no5173/primary server is started. For just fast cases, add `--grep-invert 'saved cards'`. Provider captures larger than4KB are gzip-compressed without altering original JSON bytes; tests regenerate readable JSON when rerun. Padded log lines are trimmed for a clean review diff; corresponding .raw.log.gz files preserve original bytes, including inherited source-worker logs whose padded whitespace was normalized in this final branch. Original source commits/allocations remain untouched.

## Limits

The private signed-in ESPN league was not inspected. Source-worker bounded Firefox availability probe timed out; no credentials/browser stores were read, no auth bypass or Fantasy transaction occurred. Source NBA public probes timed out/CDN403; public ESPN official completed-schedule probe succeeded and is retained in original ENGINE evidence. Fixtures are not private/live-account proof. Search remains bounded and lineups greedy; partial upstream markets/freshness can change recommendations. Updated bridge extension requires ordinary user update/reload if an older package is installed. Only humans merge; parent owns final validation and user delivery.
