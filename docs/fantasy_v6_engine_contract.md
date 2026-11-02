# V6 engine integration contract

Engine/data prerequisite from base `4e9f94f51fa2ab402e2a913023bfc28a49358553`. API allowlists, session lifecycle, TypeScript types and React integration belong to the other workers/integrator.

## Preferences and qualification

`pickup_filters: {min_minutes: 15, min_games: 2, min_participation: 0.5}`. Omitted members default individually. Finite validated ranges: minutes 0..48; games integral 1..82; participation 0..1. Unknown keys/invalid values return unavailable with a reason. Qualification precedes candidate ranking. Own-roster drop legality is never filtered by pickup gates.

`pickup_filter_summary` contains:

- `thresholds`: effective three thresholds.
- `requested`, `qualified`: counts before downstream schedule/rate/resource selection.
- `exclusions`: `{player_id, name, reasons: string[]}`.
- `source_coverage`: `{current_sample: number, team_games: number}`.
- `basis`: human-readable current observed regular-season basis.

Exclusion codes: `current_observed_sample_unknown`, `below_min_minutes`, `below_min_games`, `completed_team_games_unknown`, `traded_sample_exposure_unknown`, `sample_team_games_mismatch`, `below_min_participation`. Missing current observation cannot be supplied by prior/projected rates. Counts must be integral; MPG and filter values must be finite. Source and denominator timestamps must match the current New York date. Explicit aggregate/traded NBA samples retain one aggregate GP (never aggregate plus splits) and are excluded until team exposure is verified. Unknown exposure is not assumed eligible.

`candidate_coverage` separately reports usable/scheduled downstream `requested`, `qualified`, `selected`, `limit`, `resource_bound_reached`, `excluded_count`. Pickup exclusions do not become missing required own/opponent roster evidence. No eligible observed pickups gives `evaluation_state: no_qualified_pickups`; missing market evidence/required roster data still blocks projections.

## Sources and provenance

Normalized player/move `pickup_sample`: `{minutes, games, team_games, season_id, source, denominator_source, as_of, sample_as_of, status, aggregate}`. `minutes` is observed current MPG, `games` observed current GP. It is independent of projection fallback rates.

Primary denominator: one NBA `LeagueDashTeamStats` Base/PerGame/Regular Season batch, explicit season and DateTo=current NY date, validated 30 unique NBA teams and finite integral GP. Player batch also uses that DateTo. Status/fetch times retained. It is actual team GP, never maximum player GP or guessed season length.

Fallbacks: full official NBA season-schedule endpoint with matching season, all 30 teams and explicit full-endpoint provenance; count unique final `002` regular-season game IDs before as-of, exclude in-progress/preseason/Cup final/postponements. ESPN season-specific unfiltered `proTeamSchedules_wl` fallback verifies all 30 team maps and reciprocal unique official completed-game records. Only `statsOfficial: true` contributes; missing completion flags/malformed past records invalidate affected team coverage. Partial season extracts cannot establish full coverage. ESPN denominator evidence survives subsequent prior-rate enrichment.

Sources may refresh at different instants within the same day; fetch times remain visible, provider reporting lag is not claimed eliminated. Prior/stale-day/missing denominators do not qualify. Public source facts and captured current ESPN shapes are retained under `code_review/v6_engine/` and `tests/fixtures/fantasy_v6_completed_schedule_observed.json`; this is no private-account verification.

## Ordered plan and compact move fields

Existing `actions`, `plan`, `recommended_plan.moves` are the same legal ordered sequence. `recommendations` are competing single-move alternatives; never concatenate them.

Each move carries `pickup_sample`, `drop_sample`, `add_starts`, `drop_starts`, `add_usable_dates`, `add_rates`, `drop_rates`, `lineup_changes`, and existing `arithmetic.categories` (all nine) / `arithmetic.primitives` (`add`, `drop`, `spillover`, `net`). For percentage categories use existing weighted numerator/denominator arithmetic, not differences of per-player percentages. Detailed arithmetic remains intact for the collapsed analysis view.

`search.stop_reason`: `evaluation_limit`, `layer_limit`, `acquisition_budget`, `no_legal_continuation`, `unknown_budget`, `no_remaining_dates`, `required_inputs_unknown`. `search.selected_plan_stop_reason`: `acquisition_budget_used`, `best_beneficial_explored_continuation`, `no_beneficial_explored_plan`, `unknown_budget`. Distinguish why exploration stopped from why the selected sequence has fewer moves than the allowance.

Also supplied: `depth_reached`, `acquisition_budget`, `layer_evaluations`, `layer_pruned`, `beam_pruned`, `candidate_truncated`, `first_layer_complete`, `lineup_policy`, `candidate_order`, `candidate_priority_evaluations`, existing evaluation/beam/candidate limits. Full-roster evaluations remain bounded to 5000 through the adapter; priority estimates are separate cheap optimistic estimates, not full projections. No-benefit with incomplete exploration returns `evaluation_state: search_incomplete`. Read pruning flags together with the stop reason. `optimality: best explored` never means global proof. No numeric win-probability claim is authorized.

## Diagnosis and repair

Depth was already acquisition-budget driven, not hardcoded to one. The date × candidate × drop first layer could consume all 5000 evaluations, so no second move was explored. Beam width 8 could hold commuting same-day permutations. Candidate admission followed player IDs. Repair reserves evaluations for deeper layers, shares intermediate-layer quotas among beam states, deduplicates commuting ledgers, and ranks candidates with optimistic target contributions before bounded admission. Full ownership/ancestry, ever-acquired set, remaining dates/slots, guards and all-nine arithmetic are recomputed for each actual sequence.

Selected-five edges saturate; materiality still requires .005 net score and .01 gain in a non-cushion category. Season-value penalty discounts low-sample/low-MPG adds. Those intentional controls and provider/user/core protection remain. Explicit selected-five requests now use that lineup objective; automatic set selection retains the shared greedy nine-category lineup policy. A legitimate one-move result may remain the best beneficial explored sequence, with unused allowance explicitly disclosed. No forced seven moves, duplicated pickup ownership, stitched alternatives or removal of legality guards.
