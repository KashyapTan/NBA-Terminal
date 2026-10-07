# NBA web refactor review note

## Findings addressed

- Existing NBA service functions use synchronous calls and often allow 60-second waits. The web routes now offload calls to a four-worker executor, use 12-second endpoint timeouts, and reject excess concurrent upstream work.
- Upcoming games are date-scoped and use the current server-local date plus the following day. Only rows NBA Stats marks scheduled are shown. Scoreboard does not supply phase, so known game-ID prefixes are mapped and unknown IDs remain `Phase unavailable`.
- Historical feed rows are grouped by stable game ID across preseason, regular season, and playoff requests; only rows with completed outcomes are shown. Seasons before 1996-97 are explicitly unsupported in this view.
- Game/player pages use NBA box-score rows. Shot charts plot only shot-detail coordinates returned by NBA Stats; missing and failed chart queries have separate states.
- In-memory caches are capped at 250 entries and documented with TTLs. User picks were not modified.

## Remaining risks

- NBA Stats endpoints are unofficial, can rate-limit/time out or change schema, and were not live-queried as part of this change. Phase availability and historical coverage must be verified against NBA Stats over time.
- `ShotChartDetail` coverage is not established across all seasons. The UI reports per-game absence/failure and draws no substitute locations.
- The prior player projections, team defense, consistency, slate scanning, API catalog, and Picks Archive remain available only in the optional PyQt app; they are not yet migrated to web pages.
