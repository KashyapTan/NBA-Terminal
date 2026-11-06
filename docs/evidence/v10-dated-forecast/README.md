# Dated forecasts and category-outcome guard — accepted revision 2

Base: `cebd6205925961d93faa9d068a45ac6399efbefc` (human merge of PR19), fast-forwarded only in the owned worktree. Prior revision1 artifacts remain unchanged.

Original screenshot retained byte-for-byte as [original.png](original.png). Original source: `/var/folders/hc/g8p_srxs10z73zqvvxztzkq00000gn/T/codex-clipboard-images/F82CA680-EC93-479D-998C-30B31C5DD84C.png`; accepted copy/context: `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_V9_CHAIN/followup-dated-forecast/`. User reports Green → Merrill already executed; remaining recommendation is Nov8 Jones for Merrill.

## Verified finding

The controlled fixture reproduces the screenshot's all-nine rounded totals. Shooting attempt/make volumes are constructed test inputs because private volumes were not supplied; banked counts are integers and forecast season-rate volumes reproduce the displayed weighted percentages. Aggregate background rosters are synthetic, not the user's roster. At the exact base the optimizer recommends Nov8, keeps Merrill's Nov6/7 starts, and adds only Jones's Nov8 game. TO goes from73.7 to74.8 against74.2; AST, STL and 3PM were already won, REB remains lost. Projected W/L/T goes4–5–0 →3–6–0. This is an objective/guard defect, not a reproduced date-accounting defect. No private-league reproduction is claimed.

`_forecast` already applies transactions only on their effective date and preserves earlier starts plus banked actuals. The normalizer's ET scoring date, started-game exclusions, actuals and authoritative ownership/usage are used by the adapter. The browser displays these forecast totals; it does not sum per-move projections into the matchup. Refresh identity includes roster, usage and actual facts. The new integration test verifies pre-transaction Green ownership → authoritative Merrill ownership/one acquisition used → later Jones ownership/two used, with no replay of an already-executed action. Stable observation-only refresh does not rerank or consume quota.

The former final guard protected only .80 cushion and .40 viability edge thresholds. Losing a small positive TO margin could remain above .40 while smooth modeled gains elsewhere justified the move. The old module and full result are retained externally; [before-after-summary.json](before-after-summary.json) records the exact before/after totals and today-versus-Sunday ownership comparison.

## Corrected policy

Every final recommendation and one-add alternative must preserve BOTH all-nine and selected-five outright wins and wins-minus-losses versus keeping the current roster. A lost winning category needs sufficient compensating real category outcome. The existing aggressive cushion option does not waive this new final-outcome floor.

Within eligible explored plans, ranking prefers five outright wins, then wins-minus-losses, outright wins, selected wins and fewer losses, then the existing soft-cost-adjusted smooth focus score and acquisition efficiency. The wins-minus-losses comparison keeps a two-win/no-loss/seven-tie result ahead of three wins/four losses/two ties. At equal W/L/T, material smooth robustness gains remain allowed; they cannot compensate an actual lost projected win. Existing .005 materiality/.01 selected-edge criteria, prefix .80/.40 guards, season protection, availability, locks, ancestry, no-readd and acquisition constraints remain. Non-improving prefixes can still lead to a valid final dated chain; the final-outcome guard is applied to the complete plan, not mistaken for temporary prefix tenure.

Shortcut comparisons preserve actual category outcomes too; fewer adds cannot trade away a projected win merely because smooth edges are nearly equivalent. No player names or screenshot constants enter production logic. No additional forecast evaluations are introduced; at most eight already-explored rejected examples are exposed for technical audit, with a truncation flag. Search remains bounded and heuristic.

Backend projected states now use the same1e-9 tie tolerance as the browser. Both compute weighted FG/FT from the same primitive makes/attempts and reverse TO direction. Cards label the transaction “Effective [date]”; current daily lineup remains current-roster by default. A rejected-only search visibly says to keep the current roster; technical policy/examples stay in collapsed analysis. Existing visible Get/Lose/Net and scheduled-versus-usable counts remain.

## Verification and raw artifacts

- New controlled real HTTP suite uses production routes/provider normalizer/adapter/optimizer with external ESPN/NBA transports controlled. The NBA schedule outage deliberately exercises verified ESPN schedule fallback.
- Screenshot case: baseline exact all-nine values, Sunday4→3 rejected, Friday versus Sunday distinction, retained Merrill dates and weighted percentages.
- Valid case: REB flips while TO stays won, giving five wins; Sunday Jones ownership only, Merrill Friday/Saturday retained.
- Executed-transaction refresh: authoritative rosters and1→2 used quota, old plan removed, prior Merrill games banked on Sunday.
- ET boundary/live game: Nov7 01:00UTC remains Nov6 scoring day, started Friday game is banked/locked; after05:01UTC Saturday's date/actuals update without duplicate future production.
- Unit tests also cover compensating real wins, full ten-slot capacity, strict position mismatch and dated transaction locks. Existing V7/V8/week-reset/V9 provider/lineup/refresh/math assertions remain intact and run locally sequentially with the new suite.

Full raw responses are outside Git under `/Users/kash/.local/share/multplx/.multplx-homes-2bf4cbefadc55a81/NBA_WAIVER_V9_CHAIN/data/revision2/`. [raw-artifacts.json](raw-artifacts.json) records exact byte/hash references. Old-base source/result are `optimizer-cebd620.py` and `before-full-plan.json` there. Only compact summaries, logs and essential desktop/mobile screenshots are tracked.

Reproduce new HTTP evidence from `nba_terminal/web`: `V10_RAW_EVIDENCE_DIR=/absolute/evidence/path bunx playwright test --config playwright.v10.config.ts`. Existing V7/V8 use `E2E_PORT=4219 FANTASY_E2E_PORT=8219 EVIDENCE_DIR=/absolute/evidence/path`, week-reset uses8219, V9 uses its4219/8219 config plus an external raw directory. Run sequentially. No user5173 server, credential store or fantasy transaction is touched.

See checks.txt and code_review/waiver-v10-dated-outcomes.md. Exact new HEAD/PR and current remote CI belong to revision2 typed delivery evidence. Only humans merge.
