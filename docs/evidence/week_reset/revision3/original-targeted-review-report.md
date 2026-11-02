# Revision 2 — targeted verification of PR15 corrections

Assessed exact **566ec48b4b95c13c26afdcce4a96b31b5f858225**, relative to original reviewed **4881e1a9a4c7062476ff426b50f56d5e1bded736**. Task NBA_WEEK_RESET_REVIEW, attempt `attempt-18e44b35e96ac310-46480-0`, generation1, accepted brief revision2; parent correlation `a1b0f71790baf740`.

**Disposition:** both original P2 reproductions are corrected. One nearby P2 invalidation defect remains in the revised zero bootstrap. Source verification is separate from CI status and live-account success.

## Original P2 dispositions

**Fresh-load fallback: original exact-timestamp defect corrected.** Production `declaredUsage` now accepts a fresh later snapshot within the original fixed lease, uses the full `Kashyap's Team` label with apostrophe/space normalization and rejects ambiguous duplicate names. Independent direct-helper check: first snapshot `17:42:22.264988Z`, current time one second later, no localStorage entry -> binds used0, original `confirmed_at=17:02:22.264988Z`, original `expires_at=18:02:22.264988Z`; another same-context call returns the identical binding. The old exact fetched_at equality has been removed. Existing revised unit tests also cover stale/future snapshots, unverified calendar, expired declaration and storage failure. Actual private selected-team identity/session was not inspected; no current-account success claim is made.

Positive current counters, changed roster, changed aggregate and changed matchup ID in otherwise matching bootstrap scope write a durable tombstone. My independent tests replay each change and then restore the old snapshot; each correctly stays undefined. However the early-return paths below bypass this protection.

**Partial-current NBA false-zero defect corrected.** Replayed the original actual-shaped normalizer case: ESPN teams1/2 already started, partial NBA later current-matchup ATL/BOS game. New result: all seven original ESPN team1 games retained; bankable periods `[13]`; no_started_games false; schedule-source consistency false; bankable coverage unverified. Reconstruction with missing history and no official basis remains incomplete; complete official primitives select `espn_official` and remain complete. The implementation now iterates game rows from both original source dictionaries, avoiding the original dictionary-overwrite loss.

Nearest independent variants: started evidence present only in NBA also yields bankable `[13]` and no false zero; partial current NBA with neither source started still leaves coverage/zero unverified when observations conflict. Complete ESPN schedules remain intact. These three outcomes are recorded in `adversarial-results.json`.

## Remaining P2 — Early scope/name return bypasses consumed-zero tombstone

**Path:** `nba_terminal/web/src/usage-declaration.ts:32–44`, before binding reconciliation at `:49–69`.

**Trigger:** a bootstrap has already bound the selected team by ID. A subsequent snapshot for that same selected team contains authoritative positive current usage but a renamed/nonmatching team display name (or another early context guard fails). The function returns before reading the binding or checking positive usage. When the prior matching label/context later returns with the current count missing, the old bound zero is returned again.

**Observed repro:** independent scratch test `positive count on renamed bound selected team bypasses tombstone and old zero returns` calls the production helper:

1. Fresh current snapshot, selected team ID1, name `Kashyap's Team`, season acquisitions21, whole matchup counter unavailable -> declaration used0 binds.
2. Same selected team ID1, name `Renamed team`, weekly_used_adds2 and weekly_usage_complete true -> helper returns undefined, **but does not persist invalidated:true**.
3. Restore original snapshot/name and unavailable matchup count within the unchanged lease -> helper returns the original used0 declaration.

Thus a positive observation for the already-bound selected team can be forgotten. The adapter's normal positive precedence protects step2 while the positive counter is present, but cannot recover the forgotten observation after it disappears. Its declaration validation can still accept step3's same roster/aggregate/context, allowing zero to be reused despite observed positive usage. This is specifically the requested nearest `invalidated0` boundary, not an assertion that the user's current account has performed any acquisition.

Independent tests also show switching season/start date/selected team and then returning to the old context does not permanently consume the binding because those checks occur before tombstoning. This fails the revised brief's permanent context-invalidation criterion. The positive observation on the same stable selected-team ID is the concrete correctness case; harmless navigation alone is not claimed to prove an acquisition.

**Impact:** the claimed durable invalidation guarantee is incomplete, so old zero can resurrect after a known counted acquisition under a display/context mismatch. This can overstate remaining adds and confirm a plan from outdated usage evidence.

**Minimal fix:** load/reconcile an existing binding before bootstrap eligibility early returns. For the already-bound stable league/season/team/matchup identity, consume the seed on an observed authoritative positive counter or changed bound evidence even if the display-name/initial-bootstrap guard now fails. Persist scope-change invalidations according to the accepted policy. Keep strict initial binding guards, original fixed expiry, positive API precedence and fail-closed storage handling. Add the same-ID positive-plus-rename sequence and return-to-old-context regression; do not loosen matching or renew the lease.

## Independent focused evidence

All execution was in exact Git archive `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_REVIEW/revision2/archive/`; no implementation checkout or browser/session mutation occurred.

- `PYTHONDONTWRITEBYTECODE=1 /Users/kash/Documents/NBA-Terminal/.venv/bin/python -m pytest -p no:cacheprovider tests/test_week_reset.py -q`: **41 passed** (`python-targeted.txt`). Focused original week-reset boundary tests only.
- From archive web directory, `bun run test src/usage-declaration.test.ts src/review-revision2.test.ts`: **16 passed**, comprising 6 revised existing tests and 10 independent direct-helper cases (`ui-targeted.txt`). Adversarial assertions explicitly document current resurrection behavior; their pass is reproduction, not approval of that behavior. The expiry-and-clock-return exploratory case only documents wall-clock behavior; no clock-reversal defect is asserted.
- `PYTHONDONTWRITEBYTECODE=1 /Users/kash/Documents/NBA-Terminal/.venv/bin/python review_revision2.py`: **three normalizer/reconstruction variants passed corrected assertions** (`adversarial-results.json`). Independent source retained as `review_revision2.py`.

Original report and reproductions retained unchanged at `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_REVIEW/report.md`, `review_adversarial.py`, `adversarial-results.json`, and `review-adversarial.test.ts`. New test/repro sources, outputs, exact archive, and manifest live in this report's revision2 directory. Python repro runs from the archive cwd; retained copies outside scratch preserve evidence.

No broad suite, browser run, CI repair or publication was performed. Parent reports current CI failing/author correcting; I did not independently inspect or claim CI success. No later revision is assessed. Private team ID/name, current counter/map shape, application deployment and actual live plan remain unverified. No additional human decision is needed for the scoped code correction.
