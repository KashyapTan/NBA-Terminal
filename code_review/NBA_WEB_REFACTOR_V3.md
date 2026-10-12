# NBA Game Center schedule and UI review

## Findings addressed

- The old upcoming path made two date-scoped `ScoreboardV2` requests and filtered their response rows to scheduled games. A failure in either request propagated through the API as HTTP 502; the client displayed a schedule error, not an empty slate. The implementation now queries the NBA season schedule once, selects the current and following Eastern calendar dates, and falls back to the NBA.com current-season schedule CDN if Stats fails. If both official sources fail, the UI keeps an error state. A valid empty response remains distinct from an exception.
- The schedule normalizer validates the `SeasonGames` fields it depends on. Missing fields, malformed IDs, dates, statuses, or team identities raise errors that remain visible as API failures. It reads `gameDateEst` for league calendar grouping and `gameDateTimeUTC` for start-time conversion in the browser's local zone.
- The schedule inventory includes completed preseason, regular-season, All-Star, play-in, playoff, and NBA Cup Final games. Known game-ID prefixes provide labels; unknown prefixes remain `Phase unavailable` rather than being guessed or dropped.
- Game detail uses the selected season's schedule row to identify away and home teams, orders team score lines and player groups away/left then home/right, and retains player analysis links. If the schedule does not contain the game, the box score remains available in source order with that limitation stated.
- The shell uses a dark palette with blue accent and reusable color, spacing, panel, and table primitives. Date groups are ordered oldest-to-newest for upcoming games and newest-to-oldest for history. Schedule errors have an explicit retry state.

## Schedule diagnosis and source evidence

The code path behind “Schedule unavailable” was an upstream exception from the two `ScoreboardV2` calls; this was distinguishable in the API response and must not be converted into an empty schedule. The former path did not preserve the source's season-wide schedule metadata or use Eastern time as the NBA calendar boundary. The new path requests the current season's `ScheduleLeagueV2` response and normalizes its game dates and UTC tip times. If that Stats request fails, it tries the current-season static schedule JSON published by NBA.com; it does not use CDN data for a different season.

The endpoint URL and `LeagueID`/`Season` request parameters are listed in the [`nba_api` ScheduleLeagueV2 endpoint reference](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/scheduleleaguev2.md). Its `SeasonGames` schema includes `gameDateEst`, `gameDateTimeUTC`, `gameId`, `gameStatus`, `gameStatusText`, and flattened home/away team IDs, names, tricodes, and scores. The [official NBA schedule page](https://www.nba.com/schedule) exposes distinct preseason, regular-season, and NBA Cup schedule views.

I attempted live requests to the NBA Stats schedule endpoint and NBA's static schedule CDN from the allocated worktree. Stats timed out at 10 seconds; the NBA CDN returned HTTP 403. Therefore, the schema is checked against the pinned `nba_api` parser contract and deterministic response fixtures, but a live NBA payload and deployed-host connectivity could not be verified here. The application fails visibly if that endpoint is unavailable or drifts schema.

## Verification and remaining risk

- Deterministic mocked-data captures: [desktop Game Center](visual-evidence/game-center-desktop.png) and [mobile team box score](visual-evidence/team-boxscore-mobile.png).
- Python service tests exercise timezone rollover, both schedule dates, all six phase labels, contract drift, and matchup alignment.
- Web tests and Playwright fixtures cover date grouping, retry/error states, responsive team columns, and player links.
- The live NBA Stats network path remains an external dependency and needs a smoke check from the target runtime. The endpoint is unofficial and can rate-limit, time out, or change schema.
- ShotChartDetail coverage remains variable by game; the UI reports absent and failed shot data separately and does not invent locations.
