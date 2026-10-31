# Fantasy data V2 service review

Scope: ESPN normalization and public NBA enrichment only. No UI, planner, API routes, primary-checkout edits, running-server changes or ESPN writes. CODE_REVIEW_GUIDE.md is referenced by AGENTS.md but absent at the accepted base.

Findings fixed:

- Real WEEKLY matchup indices were incorrectly used as daily scoring IDs, producing stale dates/zero remaining games. Calendar now uses verified scoring-date anchors and checks observed matchup IDs for agreement.
- Integral float caps were discarded, while actual complete matchup counters and droppable/draft/team-lock metadata were ignored. Values now retain exact source and missingness.
- Average stats could contradict actual season totals; sparse card payloads could erase roster samples. Totals/GP take precedence and samples merge additively.
- Missing ESPN data lacked a batch fallback. Public NBA season-specific stats/schedule fill gaps with unique name/team identity checks, request timeouts, cache bounds/backoff and stale labeling. Good ESPN data survives NBA failures.
- Unknown health used to support blanket confirmation gates. Explicit health representation now follows the user's available-unless-out policy while retaining original status and source.

Validation: deterministic ESPN and NBA fixtures cover real weekly shape, float/day/week counts, unknown vs zero, explicit out/assumed availability, actual team locks and undroppable flags, draft fields, partial prior history repair, sparse cards, NBA fallback, ending-year/timezone/DST, suffix ambiguity, request batching, stale/backoff, wrong season and source failure. Full suite and Ruff results are retained in the task completion artifact. A sanitized real public ESPN probe verified corrected dates/counters/samples; the user-connected private app is verified by the browser worker.

Remaining risks: NBA upstream access can fail (CDN returned 403 here); exact per-player transaction locks are unresolved; missing counter keys are unknown; exceptional weekly-calendar disagreements remain partial; no predictive injury feed is invented. The engine must honor health_status and hard undroppable/team-lock evidence, label historical rates/projection uncertainty, and keep actual transactions manual. Final combined browser worker owns integration/visual QA and the single PR.
