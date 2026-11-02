# CONNECTION source handoff

Accepted base: 4e9f94f51fa2ab402e2a913023bfc28a49358553. Local branch: mx/NBA_WAIVER_V6_CONNECTION. No remote publication, PR preparation or merge.

Integration contract: ../../v6-connection-contract.md. Review note: ../../../code_review/v6-connection-lifecycle.md.

Route/UI ownership: the exported useLeagueFantasy import remains compatible at LeagueFantasy.tsx. Controller implementation lives in use-league-session.ts; semantic identity and useWaiverPlan live in fantasy-lifecycle.ts. WaiverStrategy currently consumes that hook and retains its existing markup. The final UI worker can wire the new sibling workspace after cherry-picking this local commit. Forward snapshot/loading/error and the plan callback; do not key/remount on loading, error, fetched_at, session expiry or status object changes. Use lifecycle.readOnly and action for retained-result badges. Detailed contract covers result identity and auth revocation.

ENGINE: pickup_filters is in the authenticated plan API allowlist and PlannerPreferences typing. Engine validation/defaulting remains ENGINE-owned. No engine/data files or shared engine fixtures were changed. No numeric budget/model policy changes. Existing fixed source/usage declaration evidence is preserved; expiry triggers reevaluation without changing original confirmation/lease times.

Root causes proven in source and route tests: status-object/expiry dependency churn; loading-driven plan clearing/cancellation; session rotation revoking in-flight work; status queued behind long provider/model locks; generic 409/429 treated as logout; equivalent fresh/cached provenance treated as new data; two extension poll loops plus null-fingerprint retries. Fixes and exact invariants are documented in the review note.

Evidence map:

- backend-focused.log: early focused real ASGI bridge/API tests. python-tests.log and python-coverage.log: latest full Python suite and coverage gate. ruff.log: latest lint.
- frontend-final.log, frontend-coverage.log, lint.log, format.log, typecheck.log, build.log: latest frontend gates. extension.log: source extension test suite; packaged v1.0.1 zips rebuilt reproducibly from the corrected source.
- browser-current-backend.log: fast real-route cases rerun after pairing TTL was bounded; Python suite covers actual pairing expiry and source error recovery.
- browser-final.log: real HTTP routes via Vite 4212 -> backend 8212 and production bundle directly on 8212. Controlled ESPN/NBA transports, real normalization/adapter/optimizer. Three accelerated refresh intervals plus focus/visibility, stable strategy DOM/protection, zero timestamp-only reanalysis; 503/429/504 failure/recovery, transient extension error, definitive 401/account change; slow snapshot plus rapid team edits, slow/out-of-order plan responses and preferences.
- wall-clock-soak.json: three actual wall-clock polling intervals with retained strategy and no extra plan calls. Unlike the deterministic timer cases, this uses no browser clock override.
- proxy/production-counts.json, source-debug.json.gz and retained.png: synthetic request/source and visual evidence. Full debug source intentionally contains synthetic fixtures only; gzip retains the exact original JSON bytes without a large generated-text review diff. Original diagnostic log files remain, including failed attempts before fixes/test-harness corrections; they are not passing check claims.
- private-browser.txt: one bounded Firefox availability attempt timed out. Private account/real signed-in plan UNKNOWN. No browser credentials/stores/cookies exported; no user-server mutation.

Scope limitations: final compact UI and current-season eligibility/multi-move engine acceptance belong to the UI/ENGINE streams and require combined integration gates. Synthetic provider fixtures do not verify the private account. This task did not access or stop/restart the user's server or primary checkout. All servers started here are test-only processes owned by Playwright on 4212/8212 and cleaned on suite exit.
