# V4 engine integration contract (early handoff)

`plan_waivers(payload)` and `plan_snapshot_waivers(snapshot, preferences)` remain entry points. Existing fields remain additive-compatible. Primary `recommended_plan` is an object with ordered `moves`, selected categories, score before/after, net score gain, complete primitive and all-nine arithmetic, budget, coverage and best-explored qualification. Legacy `plan`/`actions` alias its moves; `recommendations` remain competing single-move alternatives.

Optional normalized engine inputs:
- `projection_metadata`: mapping of component names to `{complete: bool, source?, as_of?, reason?}`. Any explicit incomplete component invalidates every confidence label/estimate and confirmed recommendation. Existing `data_gaps` remains supported. Unknown metadata is disclosed, never asserted verified.
- `market_complete`: bool or null; absence means upstream market coverage unverified, not exhaustive market search.
- Player `season_rank` / `season_rank_source`, `core_player` / `core_player_source`: inspectable default core protection. Missing metadata uses disclosed conservative per-game guard (25 PTS or season-value proxy >=3); not a future-season simulation.
- `core_protection_override: true` on a player bypasses automatic core protection only. Global `allow_core_drops: true` does the same. Neither bypasses ESPN locks/undroppable or explicit user protection.
- Player `active: false` or `lineup_slot: IR/IR+` prevents starts while retaining drop identity. No activation inferred.
- Player `available_from`, `earliest_add_date`, `earliest_drop_date` (ISO date); `transaction_locked_dates` and `unavailable_dates` ISO lists. Engine enforces effective dates and chronological ownership.
- `aggressive_cushion_sacrifice: true` explicitly permits selected cushion/viability tradeoffs. Default protects baseline selected edges >=.80 and does not reduce the number of viable selected edges >=.40.

Adapter forwards snapshot `projection_metadata`, `market_complete` and preference `allow_core_drops`, `aggressive_cushion_sacrifice`, per-player `core_protection_override`. Data owns official/NBA actual selection and metadata; engine consumes banked `current_totals`/`opponent_totals` without reconstruction. Do not replace historical eligibility with today's roster.

All nine category effects derive from one pair of full-roster forecasts. Count rows satisfy before + added - lost + spillover = after. Shooting rows expose the same identity for makes/attempts and percentage-point change, never additive player percentages. Zero lost starts has an explicit factual reason; missing inputs cannot manufacture zero loss.

Search uses one deterministic shared nine-category greedy daily lineup policy and frozen opponent starts. Every explored full-roster forecast is reused across all 126 sets. Intermediate nonbeneficial moves remain eligible for beam expansion; only terminal materially beneficial plans pass recommendation gates. Bounds and upstream coverage are separate. This is best explored, not proven globally optimal.

Confirmed DATA interface: exact commit `7c820454da5b470a393738c0a3b2b6b779d4502d`, `docs/fantasy_data_v4_interface.md`. Adapter consumes its `season_rates`/`rate_provenance` and `actuals.forecast_totals` gated by `forecast_complete`; keeps actuals provenance intact and honors every boolean `projection_metadata` component. `league_fallback_7` cap source is preserved separately from observed usage. No DATA files were imported or cherry-picked for this engine delivery.

Additional output details: `arithmetic.primitives` has eleven exact identity rows; `arithmetic.categories` has nine rows, with shooting `makes`/`attempts` subrows and `percentage_points`. Per-move `add_rates`, `drop_rates`, `rate_provenance`, `rate_evidence`, `add_starts`, `drop_starts` and `zero_drop_reason` support visible arithmetic. `primary_recommendation_kind=ordered_plan`; legacy `recommendation_kind=alternatives` still describes the secondary list. `search.first_layer_pairs_evaluated/first_layer_pairs_total` measures received legal pair/date coverage, `first_layer_complete` excludes shortlist/evaluation interruption, and upstream market completeness stays separate.

Unknown budget yields an empty confirmed move ledger plus conditional secondary alternatives; required projection gaps yield `recommended_plan=null` with confidence cleared. Known no-benefit yields an explicit empty `recommended_plan.moves` baseline and untouched budget. Optional `matchup_finalized=true` with no remaining dates compares actual wins/losses/ties exactly.
