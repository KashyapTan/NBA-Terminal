# Fantasy expansion integration record

## Scope and source requirements

Accepted brief 1, base `292e17885ae96613254c936c2189162a8b9bfa0f`, task `NBA_FANTASY_INTEGRATION`, branch `mx/NBA_FANTASY_INTEGRATION`. Work is confined to its isolated checkout. The primary checkout, including dirty `nba_terminal/web/scripts/dev.mjs`, is untouched.

Full original intake read at `/Users/kash/.local/share/multplx/home/data/NBA_FANTASY_20261031/handoff.md`; SHA256 `b2fa75ae3c1a4026de785c918bc9e261e7ba86715b38c5dacfe8fe7302993676`. This remains the source of original requirements alongside the accepted task brief. No real ESPN transaction writes, merges, target-branch pushes or Herdr lifecycle actions are authorized.

## Released prerequisites

- Navigation: exact approved source `47685f149731977d0681f118ca6f2e182681d7dd`, integrated as `704cbbd31223de361b33ba39439ccb0d4fd498a3`.
- Dashboard: current typed evidence `fantasy-dashboard-f9f4b06-final`, exact source `f9f4b065f6b12538cb5d214138fc9dc85251be7f`, integrated as `a342db8`. Dashboard default, four URL subtabs and playing-time filters retained. Navigation semantic selector preserved.
- Optimizer: current typed evidence `optimizer-result-1`, exact source `92e9fc96aedc1dcf28b67d938cf9f38581a118c4`, integrated as `c917a56`. Algorithm limitations are in `docs/fantasy_optimizer.md` and `code_review/fantasy_optimizer.md`.

ESPN and League UI implementations remain external prerequisites. Only the parent-validated exact completed revisions will be integrated. Provisional contracts read: ESPN `api-contract.md` including weekly accounting/lock research appendix, optimizer interface v1.1 and Dashboard seam. Planned UI exports are `useLeagueFantasy`, `LeagueConnection`, `Matchups`, `WaiverWire`, `LeagueDashboardSummary`; exact final exports are still pending.

## Integration acceptance checklist

- Mount one App-owned shared league state across Dashboard/Matchups/Waiver slots; preserve Leaders and its existing comparison/shortlist filters and season URL.
- Connect the authenticated snapshot directly to `plan_waivers` in a bounded backend worker, with response consumed by `WaiverWire.onPlan`. Never run search on the async event loop or accept client-invented league snapshots as trusted data.
- Validate target team against snapshot teams; use current same-period totals and complete relevant rosters. Weight percentages by makes/attempts; reverse TO direction. Validate actual lineup eligibility, remaining dated unstarted games, and acquisition-effective dates. Avoid modeling unsupported same-day game locks as known.
- Require period/league/team-bound confirmed weekly cap/used/remaining when ESPN accounting is incomplete. User expectation of seven is an editable proposed input, never an ESPN assertion. Enforce nonnegative integers and used + remaining <= cap. Invalidate confirmations across week/team/league changes.
- Require explicit droppable/locked roster choices and add eligibility; null locks/injuries/schedules never become false, healthy or empty. Provide exact missing-input guidance and baseline/rate comparisons when readiness is unavailable. Cosmetic shortlist edits are insufficient: allowed candidates/rotation must constrain the actual search.
- Derive historical margin variation only from sufficient complete prior weeks. Otherwise require an explicit, labeled sensitivity mode with supplied assumptions; never imply calibrated probabilities. Missing evidence suppresses recommendations and probabilities.
- Preserve loopback client/Host, same-origin mutations, request-header, HttpOnly session and no-store boundaries. Test real Vite proxy and single-process production serving. Keep credentials only in explicit request bodies/backend memory, absent from URLs, browser storage, logs and evidence. Explain cookie retrieval locally, unofficial ESPN stability, and unsupported remote hosting.
- Deterministic backend-to-frontend chain and Playwright coverage must verify connection/team selection, 14-team comparison including ties/TO, today's players, Dashboard/Leaders/minutes filters, responsive sidebar, ready/incomplete/unsupported/failure optimizer states. Full UV/Bun checks and coverage gates must run after all integration changes.
- Inspect desktop/mobile rendered screenshots, document real limitations, publish one combined scoped PR, register canonical publication, then submit exact-current typed evidence and task-bound done. Human merge remains separate.

## Initial combined verification and findings

At Nav + Dashboard content: Bun install/static checks/build passed; all 38 frontend tests passed with 96.05% lines (93% gate). Python Ruff and all 62 then-present tests passed; configured backend coverage 97%. First combined browser run found one stale icon-inclusive accessible-name selector. Integration fixes it to the semantic Workspace navigation link and adds actual desktop expansion-width and mobile toggle visibility assertions. Focused browser rerun passed. Desktop expanded/collapsed and 390px mobile screenshots were visually inspected: content remains readable and mobile has no horizontal page overflow. Local retained screenshots: `code_review/fantasy-integration-evidence/` (ignored, no credentials; deterministic test fixtures only).

This is a progress record, not full production delivery evidence. No live user league has been connected. Production adapter/auth/UI chain and final combined verification remain pending prerequisite release.

After adding the released optimizer: `uv run ruff check .`, `uv run coverage run -m pytest` (100 tests), and `uv run coverage report` (97%) passed. `E2E_PORT=4197 bun run e2e` passed all five browser tests, including game/player regression and the combined fantasy/sidebar path. The browser server's exit 143 is its expected graceful shutdown. Full frontend static checks, coverage and build had already passed on the same frontend implementation; the only subsequent frontend change is the now-passing browser assertion update. ESPN and League UI exact completed commit handoffs are the only external wait at this checkpoint.
