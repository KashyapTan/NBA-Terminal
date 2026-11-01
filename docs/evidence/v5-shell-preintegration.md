# V5 shell preparation from early PLAYER contract

NBA_V5_APP preparation only. Source contract: parent-delivered `early-player-contract.md` and `early-legacy-inventory.md` under `/Users/kash/.local/share/multplx/home/data/NBA_V5_PLAYER/`, read 2026-11-01. PLAYER's accepted scope is now revision 2; its exact final typed revision-2 commit/evidence, FANTASY, and LEGACY are still prerequisites. These early files are not completion evidence.

## Prepared boundary

`GameCenterShell.tsx` defines the documented structural props `{ season, phase, playerId?, onPlayerSelect? }` and URL-controlled `PlayersWorkspace`. It restores `/players` and `/players/:playerId` context; season and phase changes remain in the URL; selecting a player creates a direct profile URL. Invalid IDs produce an actionable search link without issuing profile calls. Games/Players navigation preserves season and phase while removing game-specific query context.

`AppRoutes` accepts an optional actual PlayerBrowser component. Only supplying it enables the Players section and route; production currently supplies no component. Tests use a clearly identified contract double solely to validate shell behavior, not player search, provider data, profile charts, or completion. After the verified PLAYER revision-2 cherry-pick, wire its real `PlayerBrowser` import to the default AppRoutes binding and run real component/API/browser integration checks. No sibling file or backend route was modified during preparation.

Existing direct `/game/:gameId`, `/game/:gameId/player/:playerId`, and Fantasy query routes remain. Contract tests follow an actual game ID from a simulated profile log into the real GameDetails loader, assert the game+season arguments, retain optional `player` context and restore the selected profile through browser back. The real supplied GameLogTable still requires integration validation.

## Analytics destinations from inventory

The shell now has a gated **Analytics Tools** destination alongside Games and Players, with prepared `/tools`, `/tools/:tool` and `?tool=` direct initial selection for the six meaningful standalone retained pages: Points predictor, Team consistency/CV, Team defense, Slate scanner, Picks archive, API reference. These are route/composition destinations, not implemented ports in this preparation. The `AnalyticsTools` component binding and backend `/api/tools` router/HTML shell serving wait for its exact source handoff. They will be exposed only with the actual LEGACY implementation and API contract. Raw estimates, definitions, valid sample counts, partial errors and unavailable metrics must remain visible.

The initial inventory's remaining usable Player Profile dashboard/shooting/opponent/multi-season gaps are assigned to PLAYER revision 2, not silently dropped into documentation. Final parity must reconcile the revision-2 inventory with actual implementations. The missing archive `helper` source remains a genuine exact-parity limitation; its absent algorithm cannot be claimed as ported.

## Validation scope

Three focused shell tests cover season/phase selection, keyboard selection, browser-back restoration, direct reload context, malformed IDs, hidden unintegrated destinations and unchanged Fantasy deep links. These validate composition only. Whole-frontend lint/format/type/build passed after preparation, along with all 72 unit tests and six existing desktop/mobile schedule/game/player browser checks. Current screenshots are retained in `v5-game-center/desktop.png` and `v5-game-center/mobile.png`. Full combined provider/player/fantasy/legacy validation and publication remain pending exact dependency handoffs.

## Subsequent verified integration

PLAYER revision 2 source d7e9aec was integrated as 0b083ac. The real production Players routes are now enabled; see `code_review/v5_app/player-integration.md` for current production-route validation and the added two-player sample comparison. Analytics Tools remains gated pending exact LEGACY source. Earlier paragraphs preserve the preparation-stage facts, not current completion claims.
