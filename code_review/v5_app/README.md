# V5 final integration review and evidence index

NBA_V5_APP, accepted base `15ffa760f605a3bdd4bffe8c0c25e72f5bca2a8a`, isolated branch `mx/NBA_V5_APP`. Final commit/check/PR identity is recorded in exact-current task evidence and the registered PR. Only humans merge. No primary checkout/server, user Firefox, private credentials or fantasy roster was changed.

## Verified source integration

| Part | Exact verified source | Local cherry-pick | Original evidence |
|---|---|---|---|
| FANTASY revision1 | `382a5df459c256fd6f452bb3121079e88d68d037` | `0ef90c6` | `code_review/v5_fantasy/README.md`, adjacent original check/probe logs and `visual-evidence/fantasy-v5/` |
| PLAYER revision2 | `d7e9aecbe0243ee95d9d282591479eaac7df9ef4` | `0b083ac` | `code_review/NBA_V5_PLAYER.md`, `code_review/evidence/v5_player_*`, retained `player-source-completion.md`, `tests/fixtures/PLAYER_SOURCES.md` |
| LEGACY revision1 | `f6f9c484c49ef3b393baf2ef6fa8738a6dbcf4e7` | `af85a68` | `code_review/v5_legacy_tools.md`, `docs/evidence/v5_legacy/` original logs/archive/public observations/all-six screenshots |

Each parent readiness handoff and canonical typed attempt/revision/current commit was inspected before integration. No mutable sibling working files were copied as implementations. [Current complete parity](../../docs/v5_feature_parity.md), original [Qt inventory](../../docs/v5_legacy_parity.md), [standalone formulas](../../docs/v5_standalone_tools_parity.md) and component/API contracts remain in repository.

## Final behavior and integration findings

- N brand button controls persisted collapse, Enter/Space and accessible state; separate collapse arrow removed. Named mobile navigation remains. Compact wide matchup rows retain today+next2Eastern dates, statuses/scores, real NBA logos/alt/fallback and local timezone starts. Supported Stats primary/CDN schedule fallback remains.
- Actual PlayerBrowser is mounted at direct/reloadable `/players` and `/players/:id`, with season/phase URL controls. Existing game/player and fantasy query links remain. Game Center Games/Players/Analytics Tools sections retain context. Six season measures and six on-demand shooting tables preserve units and missing data. APP adds usable two-player/two-season observed samples and distinct game links; exact unlimited legacy cards/absent-helper export formatting are not claimed.
- Actual `create_legacy_tools_router(_cached_call)` is mounted through the existing global bounded worker runner. Six real service tools are mounted at `/tools` and direct `/tools/:tool`; tool selection/back/reload and inherited supported season/phase work. Unsupported inherited phases are disclosed. Metadata/reference and read-only note viewing use actual services; empty notes are labeled explicitly. No fake production placeholders or fixture imports enter application code.
- Three independent source findings are corrected: raw mixed-case PlayerGameLog IDs (aa773f4), Traditional TO→tov for player/team rows, and traded-player opponent-side filtering (4bb6460). [Correction note](review-corrections.md) records raw parser regressions and superseded source-history claim. The unmodified23row game log/current traditional response are committed fixtures. Source worker's pre-fix available-history summary is historical, **not** current proof.
- The independent review's final source report and targeted verification are retained at `/Users/kash/.local/share/multplx/home/data/NBA_V5_REVIEW/report.md` and `fix-verification.md`. Parent accepted bounded R1–R3 verification at exact `4bb6460c97350066733bd2f832cedc29443318f0`: original raw replay plus9targeted regressions passed; all three original findings resolved. This is **not** a comprehensive independent review of final integrated UI or private ESPN state. APP performed the combined checks/render inspection.
- Existing architecture guard matched `nba_terminal.legacy` as a substring of the new supported `legacy_tools_api`. It now matches the exact forbidden module-name boundary, preserving rejection of actual old imports while allowing the supported module. No root/archive production import was added.
- Browser suites formerly overwrote inherited V4/original screenshots. Those tracked originals were restored, original generated runs retained locally, and all inherited screenshot outputs now go to separate `generated/` directories. The stale mobile test expecting the old collapse control to be hidden now verifies the visible N brand control.

## Validation and screenshots

Combined repository Python gate after corrections:365 tests passed, one expected installed TraditionalV2 deprecation warning; game_center96%, webapp100%, configured combined97% (threshold93%). Whole frontend lint/format/types/build and104 unit/coverage tests passed at the unchanged93% line threshold. Final exact-HEAD logs are retained at `generated/final/` and referenced by task evidence. The committed frontend log copy removes trailing table-padding whitespace; the original unmodified command output remains in `generated/final/frontend-precommit.log`.

Browser checks:14 default headless checks,12 real-route Fantasy proxy/production checks,4 served-production Players/all-six-tools desktop1440/mobile390 flows. Final gates run after the final code commit. Source Legacy's two standalone all-six harness flows are separately retained; they are not substituted for integrated production checks.

New production suite uses actual served built JS, HTML reload routes, API/cache/worker/service/normalizer boundaries. Test-only NBA transport mixes captured real V3/Shai23game-log/season/shooting schemas with explicitly synthetic second-player/batch/box-score inputs. Fantasy tests replace external ESPN/NBA transport. None is private-account or fresh live-provider success evidence. Public observations remain separately attributed to their original source logs.

Visual inspection: Game Center and new profiles/selected-game views, all six tools and compact Fantasy status at desktop/mobile. Assertions cover card height (<115px), no document overflow, proportional bounded charts, full-width desktop CV table, local phone table scroll, real player search, URL reload/back/game links, brand state, turnover value, dashboard/split requests, two-player samples and all-six serialized analyses. Current selected screenshots: `visual-evidence/v5-integrated/`; full original generated screenshots/logs: `generated/player/`, `generated/tools/`, `generated/fantasy/`, `generated/fantasy-dashboard/`. Images using deterministic transport are labeled as such in the parity/evidence docs.

## Remaining genuine limits

Private current waiver benefit remains undetermined: no successful Firefox/private-account inspection. Optional NBA reconstruction failure does not invalidate complete official ESPN banked totals and does not establish no useful free agent; required private ownership/eligibility/budget inputs remain authoritative. Conditional budget-unknown pairs are unconfirmed; no live transactions or new authentication behavior.

Provider availability/schema/history/static-directory freshness, cache lag and process-local caching remain; browser abort does not interrupt a running provider thread. TraditionalV2 is deprecated, but independent current public V2/V3 probes succeeded—no current outage is inferred solely from the warning. Predictors/trends are uncalibrated, rest uses phase-specific returned samples, rosters are not point-in-time guarantees, and standalone tools cover30 NBA teams/four supported phases. Absent helper exact interpolation/export/PNG formatting cannot be recovered; new percentile definitions and two-sample limit are explicit. No source-risk blocker or human product decision is hidden.
