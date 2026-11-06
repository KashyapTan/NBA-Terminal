# V9 dated acquisition efficiency

Original: `/Users/kash/Downloads/SCR-20261106-mojk.png`, inspected directly and retained byte-for-byte as [original.png](original.png). SHA256 `335b4dcc6a6904dc46d274a8029fc9e29444e329875eeb31452647bc9a8b91e7`.

The image shows Nov 6 Jalen Green → Sam Merrill (2 scheduled / 2 usable pickup games versus 1 / 1 drop), followed by Nov 8 Sam Merrill → Derrick Jones Jr. (1 / 1 pickup versus 2 scheduled / 0 usable drop starts). It reports no adds left. The first card claims REB +4.1, AST +0.9, STL +1.1, BLK −0.7, 3PM +2.7, TO −1.7 and FG −0.01 pp; the second REB +5.3, AST +1.4, STL +1.1, 3PM +2.1, TO +1.1 and FT −0.02 pp. Dates differ: two acquisitions are not necessarily wasteful if Merrill actually supplies valuable intervening starts.

## Confirmed code cause, and limits of the image

At base `eac08c6b59eef5a86842793e211418e3fee72b1c`, optimizer `rank` orders by exact selected-five score minus soft season costs, then acquisition count. Any tiny score advantage beats saved quota. Materiality is measured against the unchanged baseline, not a shorter acquisition plan. A bounded date/candidate/beam expansion can also omit a legal direct shortcut. No final shortcut verification existed.

`_describe_move` compares complete-horizon prefix forecasts: its intermediate pickup contribution assumes retention until the horizon ends. Later cards remove that projection again. These prefix differences telescope to the correct final forecast, but individually imply production that the complete plan does not realize. Zero later drop loss has only a step-local meaning. This explains the presentation problem; the screenshot does **not** reveal the private roster, selected five, game locks or actual interim benefit. No private league verification or live fantasy transactions were performed.

## Corrected contract

The focus, baseline actuals, opponent starts and matchup horizon are frozen. Search reserves one third of its existing forecast limit for shortcut replay when more than one add is available. Every applicable ancestry segment can be bypassed, using its terminal pickup on **each** remaining date between the segment's first and last move. Independent move deletion is also compared. Replays re-check original market ownership, ever-acquired prohibition, ancestry/root capacity, protection, acquisition/day budget, earliest add/drop dates, transaction locks, availability and every prefix cushion/viability guard. The same `_forecast` enforces actual positions, daily capacity and banked actuals for both teams. A waiver player not qualified as a free agent cannot become a shortcut. Unknown waiver clearance is not invented.

Prefer a shorter legal plan when its net focus score is no more than .005 below the longer plan and none of its selected category edges is more than .01 lower (inclusive numerical tolerance 1e-12). Soft season costs remain included in net score; ordinary baseline materiality and guards still apply. This policy is disclosed, deterministic and heuristic, not a calibrated win probability. All nine resulting categories, including weighted shooting and lower-is-better turnovers, remain exposed. Meaningful interim production survives. Terminal-roster equality is never used as a production equivalence rule.

Shortcut forecasts and prefixes share the same hard evaluation limit and a ledger cache. If verification cannot finish, the unverified multi-add plan is withheld in favor of an explored legal zero/one-add plan; search metadata exposes incomplete verification. Search bounds, candidate truncation and upstream market coverage remain explicit. Global optimality is not claimed.

Compact cards now report pickup production from **final selected player-dates**, with the date of its later drop when applicable. Retained chains show exact extra acquisition count and selected-five improvement versus their best legal direct shortcut. A visible sequence-level **Get / Lose / Net** strip compares the final selected player-dates with the unchanged roster. Get includes new pickups and recovered starts; Lose includes dropped and displaced starts. Both gross terms use set differences, so temporary retention is never both gained and removed. All nine categories remain visible, selected-five stars and green/red text distinguish gains/losses, TO points down, and shooting shows gross makes/attempts plus the true weighted full-team percentage-point effect. The concise extra-add/date/benefit text keeps the longer heuristic explanation in an i help.

The all-nine direct comparison, prefix arithmetic (explicitly labeled step-local), lost/displaced starts and provider details stay in the bottom collapsed analysis. Overall plan add/drop terms use final-minus-baseline selected starts: unrealized intermediate retention is no longer counted as gross final production. Spillover completes every primitive identity.

## Evidence inventory

`*-plan.json`: actual HTTP responses through provider normalizer → adapter → optimizer. Names/rates/rosters are **controlled synthetic fixtures**, with previously retained public season schedule dates. They are not this user's private plan. `vite-proxy-*` uses 4219, `production-build-*` uses 8219 and the built application. There are no fake optimizer/plan route responses.

- `0` and `0.001`: useless and materially equivalent interim streams produce one direct add, saving one acquisition.
- `2`: useful Nov 6/7 stream → Nov 8 terminal pickup retains two acquisitions. Final cards, final forecast, daily starts, weighted FG/FT, both banked rosters and all-nine arithmetic reconcile.
- `waiver`, `other`, `quota`, `locked`: provider market/ownership/acquisition/immutable-lock boundaries.
- `crowded`: ten occupied slots remove claimed interim value.
- `harmful`: points, shooting and turnover cross-category losses are asserted visible in the sequence summary with analysis closed; desktop/mobile screenshots retained.

Desktop and 390×844 mobile screenshots are retained for each main case through both hosts. The page stays within viewport width; collapsed analysis is asserted. Screenshots were visually inspected. Tests also check the missing-direct bounded-search case, same-day redundancy, re-add prevention, delayed acquisition/transaction lock dates, negative selected shooting/TO tradeoffs and hard evaluation accounting.

See `checks.txt` for exact commands and outcomes, and `code_review/waiver-v9-chains.md` for the high-risk self-review. Remote CI is a separate current-commit requirement, recorded in task delivery evidence. Only a human may merge.
