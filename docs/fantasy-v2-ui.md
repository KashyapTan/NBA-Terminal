# Matchup and waiver strategy V2

The Dashboard and global navigation retain their existing content. Matchups shows the actual opponent first, a bold wins–losses–ties score, explicit category standing labels with green/red/yellow accents, today's players, a readable fetched timestamp, and the existing hypothetical comparison selector. Missing category totals remain unavailable and do not become zeroes or wins.

Waiver Wire automatically analyzes the connected server-owned snapshot. The first view shows up to three priority targets tied to the highest-ranked alternatives, their current totals and prior-week comparison, projected margins, and whether an explored pickup can flip the lead. A compact disclosure contains all nine categories. Up to seven ranked ADD + DROP alternatives show net gains after the dropped player's lost opportunity, with current rates, minutes, schedule opportunity, shooting impacts and season-value tradeoffs available on demand. The separate combined weekly plan is sequential and constrained by verified acquisition counts; alternatives are never presented as seven executable moves.

Available/Out and Protect controls recalculate immediately. Unknown availability assumes Available unless explicitly reported Out; the compact legend states that policy. Normalized health policy takes precedence over ESPN's broad raw injury boolean, which can also describe questionable players. Explicit out statuses remain out until a user Available override. Known locks, ESPN undroppable and first-round evidence remain protected; inferred core protection can be reviewed through the toggle. Edits survive harmless snapshot refreshes, reset when league/season/team/week changes, and stale asynchronous results cannot replace a newer analysis. No recommendation submits a transaction.

`remaining_adds` in the planner response is the balance after its proposed sequence. The top budget display restores the sequence length to show the actual pre-plan budget; the weekly-plan disclosure identifies its after-plan balance. Unknown usage and unsupported daily ledgers retain conditional alternatives without implying a feasible weekly sequence. Weighted FG/FT net gains come from before/after team percentages, rather than summing player percentages.

## Source coverage

See [data normalization and NBA sources](fantasy-data-v2.md) and [model assumptions and limits](fantasy_optimizer.md). ESPN supplies league format, actual category totals/history, matchup counters, draft/drop metadata and player samples. NBA batches fill only missing usable current rates/identities/schedules. No scores, schedules, cap or usage values are invented. Upstream failures retain usable ESPN data and appear in compact data notes.

The user's connected app at `127.0.0.1:5173` was inspected firsthand in Firefox before implementation. The original UI showed the real 4–5–0 result buried in text, a stale single-date matchup calendar, unknown weekly counts, and a long confirmation/free-agent-table workflow. The private before screenshots remain local outside the repository. No cookies, account exports or private raw league responses were extracted or committed. The primary checkout, server and connected session were preserved.

Final changed-branch visuals use deterministic synthetic data and the real HTTP/session/normalizer/NBA fallback/planner chain, at desktop and 390px mobile sizes. The dedicated local demo preview uses the test-only external transports; it is not the user's league. A repeat native-browser preview attempt encountered active user browser changes, so final visual verification used isolated Playwright screenshots. No claim of live NBA fallback success is made: the source investigation observed CDN HTTP 403, and fallback success/failure is verified with external transport mocks.

## Reproducible checks

Use UV for backend commands and Bun from `nba_terminal/web`:

- `uv run ruff check .`
- `uv run coverage run -m pytest` and `uv run coverage report`
- `bun run lint`, `bun run format:check`, `bun run typecheck`, `bun run coverage`, `bun run build`
- `bun run e2e`: existing game/Leaders/navigation regressions and focused strategy/mobile fixtures.
- `bun run e2e:fantasy`: real HTTP production-build and Vite-proxy paths; 14 teams with 13-player rosters, seven alternatives without manual shortlist, verified cap/usage, target coherence, draft/undroppable protection, availability/protection edits, refresh preservation, NBA schedule/rate fallback, errors, ownership and same-origin restrictions.

`tests/test_fantasy_v2_chain.py` explicitly restores the real NBA loader despite the general offline fixture. Only external NBA/ESPN transports are mocked. It verifies CDN failure followed by the season-specific schedule endpoint, unique identity/rate enrichment, current minutes, actual remaining games, weekly counts, automatic alternatives, first-round protection, and failure preserving ESPN. Supplemental coverage measures the changed ESPN API/data, NBA enrichment, optimizer and adapter modules separately from the existing configured coverage gate.

## Remaining limits

ESPN access is unofficial and NBA endpoints can fail. Missing complete acquisition usage remains unknown. A daily acquisition cap needs a daily ledger before a sequential plan can be declared feasible. IR activation and precise per-player lock expiry are not modeled. Small current samples use a labeled prior-season fallback. Stable minutes, independent category variation, greedy daily lineup matching and bounded search are model assumptions; estimates are uncalibrated and the search may miss combinations. The season-value cost is a documented replacement-value heuristic, not a full-season simulation or a guarantee. Transactions remain manual in ESPN.
