# V3 UI/integration review

Accepted base: 784a7e4ddd7e3c485ba77f030f3734298f3a74fd. CODE_REVIEW_GUIDE.md is absent; applied AGENTS.md correctness, responsiveness, honesty and boundary checks.

Frontend preserves the Dashboard, matchups table and existing accent hierarchy. Selected five are explicit and editable; safe wins are shown separately from pickup priorities. Recommendations remain ranked mutually exclusive alternatives; repeated drop names are explained. A roster-drop filter and twelve-item expansion remove the fixed seven-result assumption without forcing diversity. Search completeness and upstream pool limits are visible. Per-pair remaining-total arithmetic includes lost starts and other lineup effects; percentages read weighted team makes/attempts rather than subtracting averages. Browser tests retain games/player-analysis/fantasy regressions.

Protection UI now treats only locks, legal undroppability and explicit user Protect as hard constraints. Real-chain tests check a legal first-round player is both evaluated and beneficial in the synthetic league; the same player is excluded after Protect. All returned synthetic pairs have positive selected-five benefit and net score, unique add/drop pairs, and meaningful selected-target categories.

The synthetic full-chain fixture reports six matchup acquisitions, season counters remain separate, and cap seven leaves one. User fallback cap setting is saved by league and season and passed only with current team/matchup context. Unknown usage remains unknown. Final preference route allowlist and new-field HTTP tests await AUTH release because that worker owns the route file until completion.

Authentication UI pairs explicitly and uses secret-free polling/events. The direct ESPN link is provider controlled and supports verification there. Setup artifacts use served endpoints, Firefox temporary-install lifetime is disclosed, manual cookies stay under fallback. No password collection, storage or URL/clipboard transport. Live private login compatibility is not established by simulated transport tests; final backend extension security and package validation await released AUTH commit.

At ENGINE integration checkpoint: full backend241 pass/configured coverage97%; Ruff passes after line formatting; frontend59 pass/93.36% lines, lint/typecheck/build pass; production browser6 pass against Vite proxy and built app. Remaining final AUTH/integrated route/full-chain checks and safe preview/publication are required before completion.
