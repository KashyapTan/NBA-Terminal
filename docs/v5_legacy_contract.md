# Standalone analytics integration contract

Accepted base: 15ffa760f605a3bdd4bffe8c0c25e72f5bca2a8a. No shared shell/player/fantasy files changed.

Backend: `from nba_terminal.legacy_tools_api import create_legacy_tools_router`; `app.include_router(create_legacy_tools_router(_cached_call))` after runner definition. Runner signature is existing `await runner(key: str, ttl: int, function: Callable, *args) -> Any`; must run function off event loop using bounded existing NBA worker pool. Router never imports webapp. Prefix `/api/tools`; GET `/meta`, `/predictor`, `/consistency`, `/defense`, `/slate`, `/picks`, `/catalog`. Query contracts in route signatures/OpenAPI; metadata returns teams, installed static player list and date/current season. Each response includes state/errors/fetched_at/resources; failed independent resources remain separate. Resource cache is bounded, season/phase/date keyed, TTL 15m (schedule 2m), with short failure cooldown.

Frontend: named `AnalyticsTools` export from `src/AnalyticsTools.tsx`, **no required props**, optional `initialTool?: 'predictor'|'consistency'|'defense'|'slate'|'picks'|'catalog'`. Own CSS/API/types in new focused files. APP mounts at its chosen Analytics Tools navigation destination; add shell route serving browser index for direct reload if choosing `/tools`. No sibling imports required.

All six tools are interactive and independently fetched. Predictor accepts manual rest/home/defense/pace overrides labeled user estimates, and discloses unavailable context. No calibrated probability/line advantage claim. Historical date excludes same/future-date logs. Picks are text-only read-only Markdown. Catalog is installed metadata only.

Exact route arguments (all GET):

- `meta`: no query; `{today, season, teams:[{id,abbreviation,full_name}], players:[{id,full_name}], ...status}`. Directory is installed static metadata.
- `predictor`: required `season, player_id, team_id, opponent_id, minutes, day=YYYY-MM-DD`; optional `phase=Regular Season`, `rest_days=0..5`, `is_home=true|false`, `def_rating`, `league_def_rating`, `pace`, `league_pace`. Blank overrides are omitted. Result includes `projection:number|null`, `baseline`, `minutes_adjustment`, `defense_adjustment`, `pace_adjustment`, `rest_adjustment`, `home_adjustment`, sample means/counts/fallback flags, `context`, `context_sources`, `missing_context`.
- `consistency`: required `season,team_id`; optional `phase`, `stat=PTS|REB|AST|STL|BLK`, `window=5|10|15|20`; `rows`, roster/ranked counts, exclusions. Ascending CV top15 with separate `valid_games`/`window`.
- `defense`: required `season`, optional `phase`; `rows`, `league_means`, `league_counts`, `missing_zone_teams`. Zone/rate nulls remain unknown. Tiers use original overall FG% rank.
- `slate`: required `season,day`, optional `phase`; `games,rows,qualified_players,evaluated_players,missing_players,insufficient_players`. Actual date+phase schedule; historical resources end before `day`. No qualification counts are asserted when dashboard unavailable.
- `picks`: optional `q`, `filename`; without filename returns matching `{files:[{filename,preview}],read_only:true}`; filename reads exact allowlisted Markdown as `{filename,content}`.
- `catalog`: optional `q`; `{version,endpoints:[{name,category,parameters,datasets,...}],metadata_only:true}`. Search covers constructor parameters as well as original name/category/schema search blob.

Common status: `state=ready|partial|empty|error`, `errors:string[]`, result assembly `fetched_at`, `resources:{resourceName:{fetched_at,state}}`, cache TTL. Unknown context/defense rates use JSON null. Validation is FastAPI query validation plus known team/window/season checks. Existing runner maps service ValueError to400 and unexpected exceptions502; request saturation stays503. Query keys/caches are namespaced `legacy-tools:`. Partial resource failures are safe structured results with30sec response TTL and30sec resource cooldown, not cached15min as successful NBA resources.

Validation command for isolated component: `bunx playwright test --config playwright.analytics.config.ts` from web directory. Dedicated Vite port5187, no reuse of any existing server, Chromium desktop/mobile, provider-shaped mocked routes with visible fixture banner. Test HTML is an e2e harness, not a production build entry point. APP must import/mount AnalyticsTools for it to enter the integrated production bundle. Main accepted-base build passes but intentionally cannot exercise that sibling-owned shell mount.
