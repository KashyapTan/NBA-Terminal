# NBA_WAIVER_V6_ENGINE local source delivery

Commit: `8b38a377c83bc72611551a8899d4c7bfd13a918a`
Branch: `mx/NBA_WAIVER_V6_ENGINE`
Base: `4e9f94f51fa2ab402e2a913023bfc28a49358553`
Allocation: `/Users/kash/Documents/.multplx-worktrees-ff5b3c227fe18eb4/45590ff690b6be80fe4fa1359d8a10718bc849eff363b8926260f2a2c8937bba`
Attempt: `attempt-18e452c424e84328-94873-0`, generation1, accepted revision1.

Implemented source prerequisite and committed, working tree clean. No PR, push or publication preparation. Cherry-pick this exact commit after parent readiness validation.

Early/final exact contract: `/Users/kash/Documents/.multplx-worktrees-ff5b3c227fe18eb4/45590ff690b6be80fe4fa1359d8a10718bc849eff363b8926260f2a2c8937bba/docs/fantasy_v6_engine_contract.md`. API allowlist/types and React wiring intentionally untouched. Accept `pickup_filters` defaults15/2/.5 and expose `pickup_filter_summary`. Compact moves use `pickup_sample`/`drop_sample`, `add_starts`/`drop_starts`, and all-nine `arithmetic`. New evaluation states: `no_qualified_pickups`, `search_incomplete`. Read `search.stop_reason` and `search.selected_plan_stop_reason` plus pruning flags; no one-move global optimality claim.

Concrete cause/fix: first-layer date×pickup×drop enumeration could consume5000 evaluations before depth2. Search now reserves deeper exploration, shares layer work, deduplicates commuting states, prioritizes candidate admission, and recomputes full ledgers and rosters. Explicit selected-five requests now use selected-five daily lineups. Saturation/materiality/season-value penalties and hard protection remain disclosed. Controlled provider/adapter/optimizer fixtures produce2 legal independent positive moves; repeat pickups cannot combine and a genuine1-move result has honest unused-budget metadata.

Qualification uses current observed MPG/GP and real completed teamgames. One NBA regular-season team batch with exactseason/current-DateTo is primary. Verified NBA full season finals and ESPN30-team reciprocal official completed schedule are fallbacks. Public ESPN source succeeded (31 includingFA,2400 rows; BOS6completed), NBA stats timed out and CDN403. Public retained fixtures are not private-account proof. Explicit trade aggregates never double-count splits and unknown exposure excludes rather than qualifies.

Validation: `uv run ruff check .` passed; `uv run coverage run -m pytest`471passed; `uv run coverage report`97% total,96% game_center,100% webapp. One existing deprecation warning. `git diff --check` passed. Original logs and source requests: `/Users/kash/Documents/.multplx-worktrees-ff5b3c227fe18eb4/45590ff690b6be80fe4fa1359d8a10718bc849eff363b8926260f2a2c8937bba/code_review/v6_engine`. High-risk self-review: `/Users/kash/Documents/.multplx-worktrees-ff5b3c227fe18eb4/45590ff690b6be80fe4fa1359d8a10718bc849eff363b8926260f2a2c8937bba/code_review/v6_engine/review.md`. Runtime:5000forecasts/depth7 in8.08s for synthetic100FA/11drop/7days/7adds; saturated targets yield0materialmoves in that fixture. No production latency or global-optimum claim.

Typed request: `/Users/kash/Documents/.multplx-worktrees-ff5b3c227fe18eb4/45590ff690b6be80fe4fa1359d8a10718bc849eff363b8926260f2a2c8937bba/code_review/v6_engine/delivery-evidence.json`. Required follow-up is UI integrator's combined API allowlist/types, connection and compact UI integration plus full page/production/visual gates. No worker servers started and no user browser controlled.
