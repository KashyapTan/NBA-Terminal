# V6 connection/session lifecycle review note

Scope: bridge/session HTTP controller, extension polling, session/snapshot hook and plan lifecycle only. No engine/data/model-budget changes and no waiver redesign. CODE_REVIEW_GUIDE.md is absent at the accepted base.

Confirmed source causes:

- Session expiry renewal changed the status object; the snapshot effect depended on the whole object. Snapshot loading and object changes cleared/restarted the strategy plan. This was sufficient to produce visible disable/re-enable cycles without a real logout.
- Bridge renewal replaced/revoked the session object used by in-flight reads. Non-definitive 409/429 responses also revoked it because all status codes below 500 were treated as auth loss.
- Status requests consumed provider workers and waited on the same lock as long normalization/modeling, so ordinary status polling could fail under load.
- Fresh-to-cached provenance changes represented identical usable facts yet changed the planner request dependency. This was reproduced only on the first cold-cache proxy run and fixed with explicit semantic identity normalization.
- The extension had separate 60-second credential and 2-second status loops; a null fingerprint after a transient error could cause repeated credential attempts. A stable public pairing identity and a single self-scheduled loop now bound this behavior.

Fix invariants:

- Same-account renewal validates current team ownership and retains stable session/context identity. Source failure remains read-only until normalized snapshot recovery. Definitive logout/permission/account/auth failures revoke; local invalid team selection is not provider logout.
- Status is memory-only and independent of provider worker/optimizer locks. Snapshot/plan I/O stays in the existing bounded worker pool. Sensitive values remain redacted and memory-only.
- Snapshot and status requests have separate single-flight/generation control. Writes are serialized and superseded queued selections skipped. Status cannot clear pending-source loading or failed-source stale state. Visibility/focus events coalesce and expensive retries respect backoff.
- Plans depend on normalized source facts plus preferences and immutable declaration expiry, not render callbacks, loading or observational timestamps. Unknown/stale/failed source flags remain meaningful. Late/aborted results cannot overwrite newer contexts; last-good output remains visible as a read-only reference.
- Existing declaration leases, positive usage precedence, tombstones and expiration are retained. The pickup_filters request field passes to ENGINE validation; no candidate/model policy changes here.

Evidence: docs/evidence/v6-connection contains original failed diagnostic runs as well as final gates, synthetic route/provider sources, request counters and screenshots. Tests use real pairing/status/snapshot/plan routes, normalization and optimizer. They do not route.fulfill planner results. Synthetic fixture observations are not private-account verification.

Limitations: the single bounded Firefox getApp attempt timed out; the user's private signed-in league/plan remains unknown. No user-server or primary-checkout lifecycle actions were taken. Production UI integration and final eligibility/multi-move engine acceptance remain the UI/ENGINE workstreams. This is a source-worker local handoff, not PR publication or human merge. No independent/deep review was requested or performed.
