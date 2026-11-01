# Review note

Scoped diagnostic/UI change only; no optimizer scoring, budget computation or legality policy changes. Checked conditional opportunities versus missing required data, zero budget and evaluated-no-benefit. Precise missing-budget diagnostics use existing normalized facts and preserve source uncertainty. Valid user counts rejected by daily-ledger rules must not be mislabeled malformed. Reused the snapshot completeness status for both top status and empty sequence. Bounded tests use different usage values from historical user counts to prevent hardcoding.

Remaining risk: exact current private counter and period-rule fields are inaccessible because native Firefox timed out and unauthenticated ESPN returned401. Do not claim any particular missing private field, verified current usage, beneficial pickup identity or current win probability. Original investigation and UI evidence: docs/evidence/waiver_plan_diagnosis/README.md.
