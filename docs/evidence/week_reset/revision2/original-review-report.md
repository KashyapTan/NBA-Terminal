# Focused correctness review — PR15

**Changes requested: two P2 defects.** Assessed exactly `4881e1a9a4c7062476ff426b50f56d5e1bded736` against base `53e7ac1f4030d555a957124098e893496690b92e`. Task NBA_WEEK_RESET_REVIEW, attempt `attempt-18e44b35e96ac310-46480-0`, accepted brief revision 1. This report does not assess later uncommitted edits or later commits.

Implementation checkout was read-only. Executed checks use the exact Git archive retained at `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_REVIEW/archive/`; only isolated review scratch/tests were added there. No browser/session access, credential access, fantasy transactions, publication or merge occurred. The implementation worktree was observed changing during review; the isolated archive remains the authoritative assessed source.

## P2 — Authorized current zero cannot bootstrap on a fresh deployment snapshot

**Paths:** `nba_terminal/web/src/usage-declaration.ts:42` (also name guard at line33), `current-usage-declaration.json:7`, and synthetic coverage in `usage-declaration.test.ts:17–19` / `tests/week_reset_fixture.py`.

**Trigger:** first load of this version with no existing declaration localStorage entry, selected current league604550749 / season2027 / Nov2 matchup, and whole current matchup map missing. A normal fresh API snapshot has a new `fetched_at`, even within the declaration's fixed one-hour lease.

**Observed reproduction:** `review-adversarial.test.ts` calls the actual production `declaredUsage` function. The exact synthetic `17:02:22.264988Z` snapshot seeds zero. Changing only `fetched_at` to `17:03:00Z` returns undefined and leaves localStorage empty. This happens even with the configured `Kashyap` name. The separate real normalizer/adapter reproduction uses the provided new-week fixture with the whole map absent and no unreachable declaration: cap7, used null, remaining null, `conditional_opportunities`, zero ordered moves. Thus a fresh deployed load cannot use the authorized statement for its intended missing-map recovery. The timestamp represents old displayed scoring evidence, not a snapshot the deployed frontend can recreate.

There is an additional unverified identity mismatch: config requires exact `Kashyap`, while the user calls the team `Kashyap's Team`. The production normalizer's `team_choices` preserves raw `name`, otherwise joins location/nickname; it does not strip `'s Team`. The fixture sets raw name/location to `Kashyap`, and the UI unit helper overwrites team.name to config.team_name. My direct production-helper case with `Kashyap's Team` also returns undefined. Private payload access was unavailable, so I do **not** claim that is the actual raw normalized name; timestamp failure alone proves the defect regardless of name.

**Impact:** the user's expressly authorized 7/0 does not produce a usable plan for the missing-map scenario the fallback is supposed to repair, requiring another confirmation despite the acceptance criterion. Present valid sparse maps can independently produce inferred zero and avoid this defect; that does not demonstrate whole-missing-map recovery. After fixed `18:02:22Z` expiry this bootstrap is intentionally unusable, which also cannot be represented as a successful deployed recovery.

**Minimal fix:** bind the existing user statement once to a verified fresh selected-team/current-matchup snapshot during its original fixed lease, using validated actual selected-team identity. Preserve immutable confirmation/expiry, roster/aggregate evidence, positive API precedence and scope invalidations; do not renew zero on reload or future weeks. Add a first-load test with a genuinely fresh timestamp and actual normalized identity, without rewriting inputs to match the bootstrap. A durable invalidation marker should prevent old zero resurrecting after a known acquisition/evidence change. No new user count is needed under the accepted scope.

## P2 — Partial NBA schedule erases started ESPN games and falsely certifies complete banked zero

**Paths:** `nba_terminal/services/espn_fantasy.py:757–767`, `:957–972`; downstream `fantasy_actuals.py:369–374` and `:246–253`.

**Trigger:** complete anchored 30-team ESPN matchup schedule contains started games; a successful but partial NBA schedule contains one future current-matchup game for the same affected teams. Its `schedule_status` is fresh/cached. Merely having one current-matchup row passes the new fallback filter, replacing that team's entire ESPN schedule. Both schedule dictionaries still have 30 keys, so the new verification predicates accept them.

**Observed reproduction:** `review_adversarial.py` exercises production normalizer without mocks. In the new-week fixture, only ESPN teams1/2 have period13 games started one hour before NOW. Supply actual-shaped NBA payload containing only a later ATL/BOS game at `2026-11-03T00:00:00Z`. Without NBA replacement, `no_started_games_verified=false`, bankable periods `[13]`. With partial fresh NBA, `no_started_games_verified=true`, bankable periods `[]`. `(espn_schedules | schedules)` is dictionary overwrite, not union of game rows, so it fails to retain the contradictory started evidence. Production `reconstruct(... official=None, no_started_games=True)` then reports `forecast_complete=true`, `forecast_source=nba_derived`, inventing a complete zero without the historical lineup/production evidence.

**Impact:** partial optional data can mark actuals complete when bankable games exist, skip required historical lineup reads, and give a confirmed plan the wrong banked basis. Complete nonzero official primitives are still selected rather than overwritten by synthetic zero in `reconstruct`, so this does not claim the user's current complete official basis is already corrupted. Even then, false verification and skipped reconstruction remain incorrect. The defect is the newly introduced completeness/zero certification; team-level NBA schedule replacement predates this change.

**Minimal fix:** require actual matchup schedule completeness before displacing complete ESPN coverage, or retain covered ESPN periods while reconciling NBA replacements. For bankable-period and no-started proofs, preserve any credible started event across both original sources rather than dictionary-overwriting it. If sources conflict or coverage is incomplete, leave the zero/coverage proof unknown and preserve official scoring fallback. Add this partial-current-matchup case, not only the existing test for NBA payload with no current-matchup rows.

## Focused verification and non-findings

Independent executions in the isolated archive:

- `PYTHONDONTWRITEBYTECODE=1 /Users/kash/Documents/NBA-Terminal/.venv/bin/python -m pytest -p no:cacheprovider tests/test_week_reset.py tests/test_espn_bridge.py -q`: **53 passed**. Retained `python-independent.txt`.
- From archive `nba_terminal/web`, `bun run test src/usage-declaration.test.ts src/review-adversarial.test.ts src/LeagueFantasy.test.tsx src/ActualSources.test.tsx`: at that initial invocation the new adversarial file had not been created (wrong relative output path); the **3 existing files / 28 tests passed**. Retained `ui-independent.txt`. Then corrected scratch path and ran `bun run test src/review-adversarial.test.ts`: **4 adversarial tests passed**, explicitly asserting the defective observed behavior; retained `ui-adversarial.txt`.
- `PYTHONDONTWRITEBYTECODE=1 /Users/kash/Documents/NBA-Terminal/.venv/bin/python review_adversarial.py`: successful real normalizer/adapter/actuals adversarial checks, output `adversarial-results.json`. Includes weekly periodType2 expansion of weeks3/4 into daily13–26 and strict valid sparse map0 / explicit positive2 / null / bool / fractional rejection.

These focused tests verify fractional4/7 rates, positive JS rounding, 6/7/13 game-day scaling, fixed/unlimited matchup versus season0/-1, strict sparse-map inference, invalid whole maps unknown, rollover requesting whole-context reload once, positive API precedence, declaration roster/aggregate/context/expiry validation, independently evidenced daily bounds, official scoring survival, and all-nine production plan arithmetic (11 primitives: add minus drop plus spillover). Optimizer diff only adds an independently supplied daily search bound; no scoring/core guard is relaxed. Partial 29-team game-day inventory leaves provider cap unknown and uses the explicit7 fallback. No flag-derived daily prerequisite remains.

The 28 existing UI tests include collapsed source details/actuals handling, confirmation preservation, refresh error suppression/recovery, and status polling not discarding a slow snapshot. API bridge tests cover generic extension failure preserving valid context and requiring fresh read, and definitive auth revocation. No additional lifecycle defect was demonstrated. Zero-attempt percentages remain unavailable via existing percentage/category formatting, rather than fabricated0%. Comparison table requires actual numeric category data and keeps official fallback. Mixed historical lineup completeness guards remain; finding2 identifies a path that incorrectly avoids those guards.

I inspected the retained implementation logs `docs/evidence/week_reset/checks/python.txt` (446 passed), `ui.txt` (117 passed), `browser.txt` (1 new production scenario), and `existing-browser.txt` (12 existing browser checks). These are implementer-supplied historical evidence at the assessed tree, **not** my independent suite/browser executions. The browser scenario freezes both server normalization and client clock to the old confirmation snapshot and uses fixture nameKashyap, so it does not refute finding1. No browser checks were rerun; no broad redundant suite was run.

## Source authority, artifacts and limits

Original primary-source authority read:

- `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_RESEARCH/report.md`
- `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_RESEARCH/decisive-correction.md`
- Original retained ESPN settings/team JS and offset/provenance bundles in that directory, with relevant extracts/hash manifest also retained under assessed `docs/evidence/week_reset/`.

ESPN's true flag prorates the matchup allowance by actual league-wide game days; it is not a daily acquisition ceiling. The old PR14 daily interpretation is superseded. Present structurally valid sparse maps may infer zero with separate provenance; whole missing/malformed maps remain unknown. Current explicit positive counters must beat stale user0, and season cap remains independent. The assessed implementation broadly follows those corrected semantics subject to the findings above.

Retained review files live beside this report: `review_adversarial.py`, `adversarial-results.json`, `review-adversarial.test.ts`, three independent test logs, `manifest.json`, and exact archive plus scratch tests. Run the Python repro from archive cwd, or set PYTHONPATH to that archive; its source is copied outside scratch for durability. UI repro was run against archive production source and cloned dependency files, with no writes to borrowed dependency/checkouts.

Private current payload/frontend/session was inaccessible and was not inspected here. Consequently actual team name, whole-map absence versus sparse-map recovery, current selected-team ID, current live plan, and production deployment success remain unverified. No fresh live sports fact is asserted; schedule cases are synthetic adversarial source checks. No unresolved human product decision is required for these fixes. CODE_REVIEW_GUIDE.md is referenced by project AGENTS.md but absent from the assessed archive; review used the stated correctness/resilience/honesty expectations directly.
