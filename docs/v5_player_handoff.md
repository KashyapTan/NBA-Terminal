# V5 PLAYER integration contract

`PlayerBrowser` from `src/PlayerBrowser.tsx` is a standalone CONTENT component, props `{season: string, phase: string, playerId?: number, onPlayerSelect?: (id: number) => void}`. Shell/tab/season/phase/URL ownership remains APP. No App.tsx/styles.css changes here. Suggested `/players` and `/players/:playerId` shell routes; callback should navigate/update selected ID in URL. Component works with local selection when callback omitted. `player-browser-api.ts` owns new API types/fetchers.

GET `/api/players?q=...`: `{players: [{player_id, name, active}]}`. Static directory, accent-insensitive tokens, active-first, limit 30; includes historical players, directory freshness explicitly labeled.
GET `/api/players/:id?season=YYYY-YY&phase=Regular%20Season`: identity/history/shooting + `advanced`, `advanced_state`, `advanced_note`, `advanced_source`. Advanced batch dashboard cached once per season/phase, profiles cached separately, worker pool shared. Failed fetch states bypass cache. `advanced` uses NBA uppercase dashboard columns and fractions, not V3 camelCase.

Existing PlayerAnalysisView props unchanged. GameLogTable exports links `/game/:actualGameId?season=...&phase=...&player=:id`; actual box-score navigation is always valid without APP additions. Optional `player` query is context, not a request to force player drilldown. Ten-character game IDs preserved/zero-padded. Existing direct `/game/:gameId/player/:playerId` route must remain in APP and fresh integration tests must cover it. Backend shell handles `/players` and `/players/:id` direct reload; APP must add client routes.

Advanced game provider is BoxScoreAdvancedV3, returned legacy metric keys preserved except V3 `turnoverRatio` becomes `tov_ratio` (per 100 plays), never `tm_tov_pct` percentage. No retired V2 retry. Missing rows/metrics/DNP => unavailable; transport/parse/schema failures => error with logs. Shot map unchanged. Actual provider regression fixture and live probe result documented in final report.

Inventory: [v5_legacy_parity.md](v5_legacy_parity.md). Initial contract is available while checks are in progress; only parent-verified final commit/evidence authorizes integration.

## Revision2 additive APIs (same PlayerBrowser props)

GET `/api/players/:id/measures/:measure?season=...&phase=...` returns `{measure,row,state,note,source,season,phase}`, `measure` Base/Advanced/Misc/Scoring/Usage/Defense. Full league batch cache is shared per season/phase/measure for 900s; Advanced reuses initial root advanced batch key. One measure selected at a time, no initial six-call cascade. Usage `MIN` is provider total minutes despite PerGame, browser labels it; Base MIN is MPG. DD2/TD3 counts preserved.
GET `/api/players/:id/shooting?season=...&phase=...` returns `{state,note,tables,source,season,phase}`; each named table has independent `{state,note,rows}`. One explicit on-demand request, six retained breakdowns in provider Totals, 900s successful cache. Partial schema errors are never cached. Zero-attempt FG/eFG/3P percentages null.
GET `/api/players/:id/history?season=...&phase=...` returns identity/history/aggregate shooting, using the same profile-history cache as initial root profile and no extra advanced request; used for second-season comparison only on explicit Compare season action.

`PlayerProfileDetails.tsx` owns full-season measure table, shooting table selector, and independent opponent/stat/window/threshold/two-season comparison. `player-profile-metrics.ts` is a static port of retained profile labels/units, no Qt runtime import. Current/compare seasons always retain phase and game IDs. Initial `PlayerBrowser` public props unchanged. API tests guard invalid adjacent season years/phase/measure.

APP must run fresh production shell-route tests for Players URL + back/reload and existing game drilldown after integration. PLAYER headless harness independently verifies content dimensions at 390/1440 and actual historical game-box navigation/reload against fixtures. It does not claim shell integration already exists.
