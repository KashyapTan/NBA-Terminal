# V6 engine contract (early integration contract)

Preferences: `pickup_filters: {min_minutes: 15, min_games: 2, min_participation: 0.5}`. Optional fields default individually. Finite validated ranges: minutes 0..48; games integral 1..82; participation 0..1. Invalid filters return unavailable with an explicit reason.

Result: `pickup_filter_summary` has `thresholds`, `requested`, `qualified`, `exclusions` (player_id, name, reasons), `source_coverage` (current_sample, team_games), and `basis`. Qualification uses observed CURRENT regular-season rates/GP, never projected/prior-season rates. Own-roster drops are not gated. `candidate_coverage` retains downstream usable/scheduled/selected counts separately from required roster completeness.

Normalized players carry `pickup_sample`: minutes, games, team_games, season_id, source, denominator_source, as_of. Missing or inconsistent data excludes a pickup. NBA LeagueDashTeamStats Base/PerGame/Regular Season supplies batched team GP alongside current player stats; verified full regular-season completed schedules provide fallback. Trades use one aggregate GP sample (never aggregate plus splits); ambiguous team/sample alignment is excluded explicitly.

`search.stop_reason` distinguishes evaluation_limit, layer_limit, acquisition_budget, no_legal_continuation, unknown_budget, no_remaining_dates. `search` includes depth reached, per-layer counts and pruning flags. Best explored is not global optimality. No-benefit claims are scoped to explored states.

Each move retains existing `arithmetic.categories` (all nine), primitives add/drop/spillover/net, and `add_starts`/`drop_starts`; `pickup_sample` and `drop_sample` expose observed MPG/GP/team GP for compact cards. No numeric win-probability claim is authorized by this contract.

Diagnosis: budget is not hardcoded to one. First-layer dates × candidates × drops may exhaust the shared 5000-evaluation cap, preventing depth two. Beam width 8 and repeated commuting same-day states reduce diversity. The selected-five edge objective saturates and materiality requires .005 net plus .01 gain in a non-cushion target; soft season penalty discounts low sample/low MPG. Hard star/user/provider guards and max stream roots constrain legal moves. Daily lineups use a shared greedy nine-category policy, independent of selected five. The repair reserves exploration for deeper layers, deduplicates equivalent ledgers, and discloses actual stop/pruning bounds; no forced move count.
