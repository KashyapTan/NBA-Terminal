# V4 engine self-review

Scope: pure optimizer, optimizer-facing snapshot adapter, engine tests and documentation. Base `258f3c320580c6cfd65fb38b0f38963c9c013589`; isolated branch `mx/NBA_WAIVER_V4_ENGINE`. `CODE_REVIEW_GUIDE.md` is absent at this base. No independent review claimed.

Read approved original artifacts:
- `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_VPLAN/plan.html`
- `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_VPLAN_DESIGN/report.md`
- `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_VPLAN_AUDIT/report.md`, original `evidence/audit_examples.py`, `examples.json`, `focused-tests.txt` and referenced fixed-base sources
- `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_VPLAN_NBA/report.md`
- DATA revision1 early interface `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_V4_DATA/early-interface.md` (working schema only, not completed source commit).

## Findings fixed

1. Replaced gross schedule reachability with a common full-roster feasible-plan library and consistent evaluation of all126 focus sets. Kept shared approximate lineup policy and frozen opponent scenario explicit.
2. Added one primary ordered recommended_plan, empty baseline, deterministic selection, complete score/cost breakdown and all-nine/primitive arithmetic. Legacy alternatives remain secondary and never imply simultaneous ownership.
3. Removed improving-only prefix pruning; terminal gates enforce .005 benefit, .01 non-cushion edge and default cushion/viability guards at each prefix. Partial search and upstream partial market are separately disclosed.
4. Added visible automatic core guard and distinct override; ESPN/user locks cannot be bypassed. No invented future-week objective or certainty in missing season rank provenance.
5. Cleared every confidence label on required input gaps, including old safe/favored fields. Stopped unknown IR/out season values from becoming zero drop cost.
6. Adapter preserves IR legal drop identity without activation, consumes optional normalized season_rates and actuals forecast_complete contract, and preserves official totals/source evidence.
7. Preserved current-season games1–2, weighted makes/attempts, inverse TO and banked credit. Explicit final actual comparisons resolve ties without normal-model half-wins.

## Verification

Final exact commands/results are retained in task delivery evidence and completion report. Focused engine/adapter/production-shaped mocked API tests and repository Ruff/coverage checks are required before commit. All tests are deterministic synthetic fixtures; no NBA/ESPN/live-user requests were made. No frontend files, services/fantasy_nba.py or services/espn_fantasy.py were changed.

## Remaining risks and integrator handoff

- Bounded beam and shared greedy lineup selection can miss global optima, especially crowded-slot combinations and per-start utility saturation; optional benching is myopic. No per-subset lineup refinement is claimed. Uncertainty is uncalibrated and independent-category P5 remains diagnostic only.
- Supports supplied daily slots/started occupancy, availability and effective dates, not unprovided league season/position limits, intraday transaction timing, waiver cooldown or IR activation/active-roster capacity transitions. Upstream must establish legal add/drop facts and flag unsupported constraints. No opponent response/acquisitions or live remaining-game production is modeled.
- Legacy inputs without optional completeness metadata retain caller responsibility for complete rosters/history/actual basis. Explicit false metadata/gaps suppresses all confidence. Market incompleteness does not itself fabricate roster gaps.
- DATA exact interface commit `7c820454da5b470a393738c0a3b2b6b779d4502d` was read and compatibility-tested with synthetic field shapes, without cherry-picking it. UI and combined source commits were not consumed; integrator must verify finalized optional field shapes, actual source selection, confidence clearing, score/arithmetic rendering and real-card zero/nonzero drop examples. Fixed-plan cautious-scale sensitivity does not claim alternative rankings remain stable.
- Default rate-proxy core guard is deliberately conservative and visibly overridable; source/rank gaps remain inspectable. Current-week score alone cannot protect stars.
- Same-day complementary prefixes may temporarily lower score; their individual downsides are returned even if the joint terminal plan passes the thresholds. Guards still apply to every prefix unless aggressive opt-in is explicit.

Final focused check: `uv run pytest tests/test_fantasy_optimizer.py tests/test_fantasy_optimizer_v4.py tests/test_fantasy_strategy_v2.py tests/test_fantasy_strategy_v3.py tests/test_fantasy_integration.py -q`: 125 passed. Added independent user/opponent daily capacity regression after finding that the legacy pure default inherited user consumed slots on the opponent; fixed opponent fallback to its own base slots. Synthetic 100-FA/11-drop/500-evaluation benchmark completed in 0.578s here; no live latency claim or production performance guarantee.

Final repository verification: `uv run ruff check .` passed; `uv run coverage run -m pytest` passed277 tests in10.31s; `uv run coverage report` passed97% total (webapp100%, game_center96%). Configured coverage does not include fantasy services; no fantasy100% coverage claim. `git diff --check` passed. Logs retained at `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_V4_ENGINE/`. No GUI/frontend changes, so Qt/Bun checks are not applicable to this branch.

Known integration overlap: `tests/test_fantasy_integration.py` engine edits add a distinct core override in preferences and expect incomplete when IR season value is missing; DATA adds a historical-view transport mock in the same file. Integrator should retain both changes. No sibling-owned service/frontend source edits occurred.
