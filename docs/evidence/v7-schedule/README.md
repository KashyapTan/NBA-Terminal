# V7 backend schedule repair evidence

Starting revision: `80f2e6c26cf4d1f19acc78703538b9416c7fee9a`. Owned branch: `mx/NBA_WAIVER_V7_SCHEDULE`. The isolated checkout and Git top-level were verified to be the allocated worktree before editing. No primary-checkout edits, private account access, fantasy transactions, user-runtime changes, servers, push, PR or publication preparation occurred.

## Concrete findings and fixes

1. **Provider precedence lost games.** Before repair, `espn_fantasy.normalize` accepted any existing ESPN team map and used NBA only for missing team keys. Thus a cropped ESPN map with two games remained two even when a complete NBA response contained four for that same team. The new production-chain regression crops the existing ATL map, retains the complete NBA transport, and observes four remaining/usable pickup starts. Verified fresh NBA now replaces the team maps.
2. **A nonempty payload/30 dictionary keys were mistaken for coverage.** The NBA parser allocated empty arrays for all teams even from a tiny subset. Schedule endpoint validation checked season and nonempty dates, and the NBA completed-game denominator trusted full-endpoint labels. Coverage now checks a full reciprocal unique game inventory, matching season/calendar, pending Cup assignments and malformed/conflicting records before accepting source completeness or denominators. ESPN completed-only extracts likewise no longer attest complete season denominators. Known unaffected full team inventories can remain usable when an unrelated ESPN team is unavailable.
3. **Old schedule cache could persist an hour.** The schedule cache now uses a new key and a five-minute TTL. Tests observe fresh → cached → failed partial refresh/stale → explicit ESPN fallback → full recovery/fresh. Missing both sources yields unknown schedules and incomplete forecasts, never a verified empty week.
4. **Calendar cropping and count ambiguity.** Daily matchup dates previously stopped at the last observed game rather than the final explicit scoring day. Both daily and weekly calendars now include their full verified scoring dates/off days. Additive metadata distinguishes full-week games, unstarted remaining games, transaction/availability eligible games and actual lineup starts, with reasons. NBA game count is never used unconditionally as fantasy starts.
5. **Clock advancing across tipoff.** Metadata advances lock flags at planner time. A newly started active game requires refreshing banked actuals rather than quietly omitting it from both actual and future production. Already-banked/started games are never projected twice.

These are code-proven causes and regression reproductions. **The exact cause of the user's private-league displayed two starts remains unverified** because no private account was accessed. Two can also be legitimate midweek after earlier games, a transaction effective date, health/IR status, occupied/position-incompatible lineup slots, optional category benching, or an existing qualification/ownership/protection guard. Tests demonstrate four scheduled games becoming two or three transaction-eligible starts, or zero usable starts despite four eligible games under a position-blocked lineup. The repair preserves these constraints and exposes them.

## Observed public source evidence

`public-probes.json` retains exact URLs, UTC request times, bounded `(3.05, 8)` timeouts, HTTP results/bytes or errors. `probe_public_sources.py` reproduces the requests concurrently without credentials. The actual response bodies are retained separately, byte-for-byte (local Git whitespace checking is disabled only for these raw `.response` artifacts):

- `nba-cdn.response`, `nba-cdn-int.response`: HTTP 403; no NBA schedule success claimed.
- NBA Stats `/stats/scheduleleaguev2?LeagueID=00&Season=2026-27`: read timeout at eight seconds; recorded in the manifest.
- `espn-season.response`: actual HTTP 200 public unfiltered season response, 422,881 bytes, 80 assigned games per NBA team. This is the observed-source fixture used by the new tests. Nov 2–8, 2026: IND 3 games (Nov 2/4/7), BOS 4 (Nov 2/4/6/8), ATL 4 (Nov 2/4/6/7), including end-of-week games. It contains pending NBA Cup assignments; an unassigned Cup week is not asserted complete.
- `upstream-doc.response`, `upstream-parser.response`: fetched upstream endpoint documentation/parser, HTTP 200. They describe the season-explicit endpoint and nested schedule fields. These are upstream documentation, not observed NBA production data.

Primary web references consulted: [NBA official 2026–27 release](https://pr.nba.com/2026-27-nba-regular-season-schedule), [nba_api upstream endpoint docs](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/scheduleleaguev2.md), [upstream parser](https://github.com/swar/nba_api/blob/master/src/nba_api/stats/endpoints/_parsers/scheduleleaguev2.py). The NBA release describes an initially assigned 80-game schedule per team with two Cup-related games determined later. Public transport probes, rather than the availability of a web search result, determine operational source availability here.

`tests/fixtures/espn_fantasy_synthetic.json`, `tests/fantasy_v7_fixture.py`, and the NBA shape conversion inside `test_fantasy_v7_schedule.py` are **synthetic**. The latter preserves observed dates/opponents but deliberately creates artificial NBA game IDs; it is not an observed NBA response. The older V6 completed-only observed extract remains unchanged and is now tested as insufficient for full-season attestation.

## Validation

- `uv run ruff check .`: passed; `ruff.txt`.
- `uv run coverage run -m pytest`: 498 passed; `pytest-coverage.txt`. One existing NBA BoxScoreTraditionalV2 deprecation warning.
- `uv run coverage report`: passed, combined 97%; `coverage.txt`.
- `uv run coverage report --include='nba_terminal/services/game_center.py' --fail-under=93`: passed, 96%; `coverage-game-center.txt`.
- `uv run coverage report --include='nba_terminal/webapp.py' --fail-under=93`: passed, 100%; `coverage-webapp.txt`.
- `git diff --check`: passed.

New tests run the real `EspnClient.snapshot → fantasy_nba.load/cache/fetch validation → ESPN/NBA normalizers → planner adapter → optimizer` with external transports mocked, while replaying the actual observed public ESPN response. They cover verified NBA precedence, explicit fallback, complete/partial/stale cache transitions and recovery, both-team start/midweek actual-plus-future forecasts, weighted shooting, TO lower, 0/2/3/4 usable counts, transaction timing versus lineup blocking, negative net/spillover, NY/UTC/DST boundaries, postponements, duplicate/conflicting game IDs, Cup incompleteness and tipoff refresh. Existing ordered multi-step and all-nine net/spillover regressions remain passing.

The final schema is in `docs/fantasy_v7_schedule_contract.md`. Parent must validate the exact local commit and route it to FORECAST. UI/HTTP-proxy/browser integration belongs to FORECAST; no frontend or production user-session claim is made by this backend delivery.
