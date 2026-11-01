# Read-only waiver engine V4

`services/fantasy_optimizer.py::plan_waivers(payload)` is pure. The snapshot adapter normalizes server-owned facts; the HTTP worker still owns bounded execution. No transaction, authentication or network behavior is introduced. Examples and tests are synthetic.

The primary additive result is `recommended_plan`: one best explored ordered plan, including the empty baseline. `recommended_plan.moves`, legacy `actions` and `plan` refer to the same coherent sequence. Each step specifies one add, one owned drop and one effective date. `recommendations` remain secondary, mutually competing one-move alternatives; `recommendation_kind=alternatives` describes that legacy list. `primary_recommendation_kind=ordered_plan` describes the primary result. Counts are acquisition transactions, never card quotas.

## Forecast and data basis

Both sides use banked actual primitives plus season per-game rates times remaining usable starts. The daily matching policy enforces supplied active slots, position eligibility, started-slot occupancy, availability and effective dates. IR/inactive players retain legal drop identity but receive no starts; no activation is inferred. Each player may start at most once per day. Opponent starter identities are frozen from the symmetric baseline across every user counterfactual. Already-started games receive no extra full-game projection; their unplayed live remainder is unmodeled.

FG/FT use summed makes divided by summed attempts; zero denominators are unknown. Raw TO decreases are beneficial. Current rates remain primary in games 1–2 with a small-sample label; missing current fields can use a labeled prior fallback, with shooting pairs from the same sample. Normalized `season_rates` and original `rate_provenance` from DATA take precedence. Rates and starts used in arithmetic are returned directly.

When `team.actuals` exists, the adapter consumes `forecast_totals` only with `forecast_complete=true`. Official ESPN totals and all actuals metadata remain intact in snapshot/provenance. Explicit incomplete actuals/projection metadata blocks confidence and confirmed moves. Legacy snapshots without new metadata still work using official totals with a legacy-source disclosure; completeness must be established by the caller, not inferred from the absence of a flag. The adapter detects missing current/opponent rosters, schedule/rate/position failures. Missing drop rates, even on an out/IR player, never become zero opportunity cost.

Required projection gaps clear **all** numerical edges, favored/cushion/attainability labels, selected safe lists and flags together. Missing one shooting denominator blocks the complete recommendation rather than ranking a hidden partial objective. Missing candidate inputs exclude that candidate locally with an explanation. Market coverage is independent: a partial market permits best-explored recommendations without claiming whole-market coverage. Missing acquisition counts allow conditional secondary alternatives, with no confirmed ordered moves. Unsupported daily limits need an external daily ledger and remain conditional.

An explicitly confirmed `matchup_finalized=true` with no remaining dates compares actual wins/losses/ties exactly; actual ties count as zero outright wins. No-date snapshots without final confirmation retain a provisional heuristic comparison.

## Common feasible plans and five-category choice

Every explored full-roster projection is reused across all 126 choices of five. The lineup policy is a shared deterministic greedy nine-category marginal-edge matching policy, including optional benching of individually harmful starts. It is not reoptimized for each focus subset. This avoids choosing categories from incompatible gross pickup upside, while remaining an approximate lineup policy: greedy one-start utility may miss benefits from combinations of starts.

For selected set S and feasible plan P:

`Q(P,S) = mean(model_edge[P,k] for k in S) - sum(season_cost)`.

Edges are a normal-margin **heuristic sensitivity score**, not matchup win probability. The legacy independent-nine `win_at_least_five_probability` diagnostic remains for compatibility and is not optimized. Margins use raw category comparisons and reverse TO. Historical weekly margins affect the heuristic scale/context, never replace this week's roster/schedule forecast. Scale floors remain .025 for shooting and max(2, .12 × banked combined counts, .12 × scheduled volume when history is absent) for counts. History with >=3 rows uses sample deviation above the floor. None of these are calibrated remaining-horizon errors.

Labels are cushion >=.80, favored >=.60, swing >=.40, otherwise trailing. Reachable additionally requires an explored legal one-move plan with material selected-route gain; it does not assert a guaranteed flip. The weakest selected edge and `viable_five` (all five >=.40) expose a difficult route explicitly.

Automatic focus includes all baseline cushions when there are <=5; with more, the strongest five form the retained set. Manual five-category choices are honored. Default guards apply to **every prefix**: no selected baseline cushion may cross below .80, and the number of selected viable edges >=.40 cannot decline. `aggressive_cushion_sacrifice=true` explicitly releases those guards; all losses still appear. A terminal recommendation needs net Q improvement >=.005 and a selected non-cushion edge gain >=.01. These are product thresholds, not significance tests. No useful plan leaves the budget untouched.

Tie breaks use highest score, fewer acquisitions, smaller soft cost, stronger weakest selected edge and stable ordered IDs/dates. The five are frozen for all per-step explanations and secondary alternatives. A 1.5× wider-scale sensitivity calculation is returned for the chosen plan, clearly labeled as fixed-plan sensitivity, not a reranking guarantee.

## Core guard and soft cost

ESPN locks/undroppable and explicit user Protect always apply. Automatic core protection uses caller `core_player` designation or positive season rank <=50, with source shown. When rank evidence is absent/incomplete, a visible conservative per-game fallback protects >=25 PTS or season-value proxy >=3. It is a policy guard, not proof of season rank or future-week value. Missing provenance is labeled unknown.

Player `core_protection_override=true` or global `allow_core_drops=true` releases only automatic protection. Setting `protected=false` alone is not a core override. No override releases an ESPN or explicit user lock.

The separate soft season cost remains `.035 × max(0, drop_proxy - stability × add_proxy)`, where proxy is `PTS/25+REB/10+AST/8+STL/1.5+BLK/1.5+3PM/3-TO/4+(FGM-.47FGA)/3+(FTM-.78FTA)/2`; stability is `.6+.4×min(1,current_games/15)`, times .8 below 18 MPG. It is a per-game opportunity-cost heuristic, not future-season simulation. Score before/after, focus gain and soft cost are separately returned.

## Search and arithmetic

Chronological beam expansion evaluates eligible pickups against all legal owned drops for each effective date until explicit bounds. Nonbeneficial prefixes are retained for expansion; only terminal plans must clear materiality. Ownership, ever-acquired IDs, stream-root ancestry and budget are re-evaluated after every move. Original user drops are not put back into the free-agent pool; reacquisition/waiver cooldown is not invented. Input order cannot change stable tie breaks.

Limits: <=14 dates, <=1000 normalized players, <=20 slots, <=1000 candidate limit, <=32 beam states (default8), <=4 distinct stream roots (adapter default2), <=20,000 forecasts (default/adapter5,000). A narrower explicit stream-root preference is honored. Bounds may omit better plans; no global optimality claim. First-layer pair/date evaluations and completeness are separate from beam pruning and upstream market completeness. Alphabetical candidate enumeration can bias a truncated pool; the output discloses the bound.

All eleven primitive rows satisfy `before + add - drop + spillover = after`. All nine category rows include raw before/after/net and unchanged opponent comparison; shooting rows expose that identity separately for makes/attempts plus percentage-point change. Summed step arithmetic telescopes to the total plan. For a zero-start drop the factual reason is returned, so net=gross is explainable. `add_starts/drop_starts` are usable starts, not scheduled games. Losing categories remain visible even if aggregate Q improves.

See [V4 interface](fantasy_optimizer_v4_interface.md) for optional input fields and integration notes. Unsupported season/position start caps, intraday waiver processing and lock semantics must be marked incomplete by the data adapter; the engine enforces supplied daily slot caps but does not infer missing league rules. No live-account or frontend verification is claimed by the pure engine delivery.
