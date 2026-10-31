# Connecting ESPN Fantasy basketball

> Data-source update: [Fantasy data V2](fantasy-data-v2.md) supersedes the original weekly-count, schedule, injury and drop-metadata limitations below. V2 uses verified ESPN matchup counters/droppable fields and bounded NBA enrichment; unknown health follows available-unless-out authorization. Planner/UI behavior is documented separately by its owning workstream.

The read-only adapter uses ESPN's unofficial Fantasy API. It does not implement OAuth, ask for an ESPN password, or perform roster transactions. League settings, availability and results can change between retrieval and a decision. Refresh and verify any proposed action in ESPN.

Run NBA Terminal's existing single-process loopback server (`uv run nba-terminal`) and open its local browser page. The API deliberately rejects remote/nonloopback clients and Host names. A hosted deployment needs authenticated user isolation, a trusted-proxy policy and a real secret store before enabling private connections. Do not merely remove the loopback restriction. Browser development requests must go through a same-origin local proxy; direct cross-origin browser calls are rejected.

Use the league ID from ESPN and the **ending** season year (for example, the 2026–27 NBA season uses 2027). Public leagues need no private credentials. Select a team returned by the league; ownership cannot be verified for public access. The adapter reports actual team count and scoring categories, and returns an unsupported-scoring explanation for leagues outside standard head-to-head nine-category scoring. It never assumes 14 managers or a seven-add cap.

For private access, sign into ESPN directly in your own browser. ESPN's existing browser session may expose `SWID` and `espn_s2` under its domain's developer-tools cookie storage. Supply only those two values to the local connection form when it is available; send them only in the same-origin JSON POST body. Do not send passwords, put values in a URL, copy them to issue reports, or store them in browser localStorage. Clear the form fields after submission. If cookies are absent, expired, or ESPN denies access, renew the session through ESPN itself; this application does not automate login or bypass access restrictions.

The supplied SWID is checked against the selected team's ESPN owner IDs, after ESPN grants league access. This is a cookie-to-owner consistency check, not an independently authenticated OAuth identity assertion; the local client is trusted to supply its own session. A private connection can first omit team selection to discover selectable teams.

Credentials stay in per-browser backend memory behind an opaque HttpOnly SameSite=Strict session cookie. The cookie is Secure over HTTPS; plain HTTP is permitted only on loopback. Sessions expire after eight hours without extension, have a global cap of 64, and are lost on restart. Expired records are removed lazily on the next session access; disconnect revokes immediately and drops credential/cache references, or clears them when a currently running worker finishes. Python does not guarantee physical memory zeroization. Never enable request-body/header debug capture around connection requests.

## HTTP contract

All routes live under `/api/fantasy/espn`. Send `X-Fantasy-Request: 1` for POST, PUT and DELETE. POST/PUT require `Content-Type: application/json`; browser requests use same-origin credentials. Responses are `Cache-Control: no-store`.

| Route | Input / result |
|---|---|
| POST `/connect` | Body: `league_id`, `season_id`, optional `team_id`, optional paired `swid` and `espn_s2`. Creates a session only after a successful ESPN league read; returns connection status and selectable teams. |
| GET `/status` | Returns `connected`, league/year/team, public/private auth mode, owner-match status, selectable teams and expiry; no ESPN network fetch. |
| PUT `/team` | Body: `team_id`. Validates existence and private owner match; invalidates snapshot cache. |
| GET `/snapshot` | Optional `refresh=true` and `compare_team_id`. Requires team selection. Returns normalized snapshot, actual opponent and same-period category comparison against any returned team. |
| POST `/plan` | Snapshot-bound planner preferences and explicit confirmations; returns recommendations or precise missing-input reasons. Never performs transactions. |
| DELETE `/connection` | Revokes this browser session and removes its cookie. No ESPN-side account/session changes. |

Errors contain `detail.code` and a static `detail.message`. Codes distinguish invalid input, local-only/origin denial, missing connection/team, team owner mismatch, unavailable league, access denial, upstream throttling/timeouts/network/schema failures, capacity and busy workers. Upstream bodies and exception text are never returned or logged by this adapter. Transient errors are not cached or silently replaced with stale success. Normalized snapshots cache for 60 seconds per connection; refresh bypasses that cache. Connections share the app's four bounded worker slots, and cancelled browser requests retain a slot until their underlying worker actually finishes.

The normalized contract and synthetic example are also delivered as coordination artifacts. The repository fixture `tests/fixtures/espn_fantasy_synthetic.json` is entirely invented **test data**, not live league data. It covers 14 teams, nine categories, shooting attempts, current/prior season samples, schedules and current/prior matchups. Tests never require real credentials or ESPN access.

## Data sources and recommendation inputs

The [V2 data-source guide](fantasy-data-v2.md) describes verified fields, provenance and remaining limits. Current season rates use actual cumulative totals/GP; bounded NBA batches fill missing minutes/category rates and professional schedules. The ending ESPN season year maps explicitly to the NBA season. Weekly matchup indices are expanded using verified daily scoring-date anchors; individual schedules retain actual UTC starts and Eastern dates.

Free-agent output remains a bounded top-100 ESPN sample, with rostered IDs and duplicates excluded. FREEAGENT plus returned active-slot eligibility establishes eligibility; WAIVERS rows stay visible with immediate eligibility false because claim timing is unknown.

Matchup caps accept integral JSON numbers, including floats, only when ESPN explicitly specifies a matchup rather than daily limit. Complete matchup usage comes from `transactionCounter.matchupAcquisitionTotals`; the season total and daily transaction log are separate. Missing counter keys remain null. Known droppable/team transaction-lock metadata is retained. Unknown health is assumed available unless ESPN explicitly reports out, with source metadata; the planner/UI may apply immediate availability overrides. Missing injury or exact drop-lock fields add no blanket confirmation barrier. Recommendations remain read-only and transactions remain manual in ESPN.

## Primary source evidence and limits

Inspected 2026-10-31, source revision `700e15ddbb91124f031473d2411c8a6285944274` of the community-maintained [espn-api repository](https://github.com/cwendt94/espn-api/tree/700e15ddbb91124f031473d2411c8a6285944274):

- [Transport and request views](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/requests/espn_requests.py): league/season endpoints, cookies, pro schedules, batched player cards and explicit aggregate split filters.
- [Basketball league](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/league.py): free-agent filters, matchup scoring views, current-day transactions and activity topic pagination.
- [Basketball stat/slot IDs](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/constant.py), [player samples](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/player.py), [category totals](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/box_score.py), [settings](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/base_settings.py) and [team counters](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/team.py).

These are primary source-code evidence for a community client, not official ESPN API documentation or authorization. No supported OAuth flow, guaranteed daily transaction-log completeness, per-player drop-lock expiry, or real private-league credential test was established. Actual matchup counters and droppable/team-lock fields were subsequently verified in public ESPN responses; see the V2 guide. ESPN may change response schemas or deny access. No ESPN write endpoints are used.
