# NBA Terminal

NBA Terminal is a responsive React web app for NBA game research. Its dashboard opens to the current season, lists today's and tomorrow's scheduled games, and links completed game feeds to box scores and player-in-game analysis. The web app is the primary entry point. Existing PyQt analytics remain available as a secondary desktop app while they are migrated.

## Stack and startup

Python 3.10+, UV, FastAPI, Uvicorn, `nba_api`, pandas, Bun, React, Vite, and Biome. The React client source is in `nba_terminal/web/`.

```sh
uv sync --all-extras --dev
cd nba_terminal/web
bun install --frozen-lockfile
bun run dev
```

`bun run dev` starts Vite and the FastAPI server together. Their logs and errors appear in the same terminal; press Ctrl+C to stop both. Open <http://127.0.0.1:5173>. Vite proxies `/api` to the local FastAPI service at port 8000. For a production-style local run, build the client with `cd nba_terminal/web && bun run build`, then open <http://127.0.0.1:8000>. Both development servers bind to localhost only. The retained desktop shell starts with `uv run nba-terminal-desktop`.

## API, cache, and data limits

`nba_terminal/services/game_center.py` owns NBA Stats endpoint calls and normalization. `/api/upcoming` queries the next two server-local calendar dates; `/api/games?season=YYYY-YY` combines preseason, regular-season, and playoff team game logs; `/api/games/{game_id}` returns the traditional box score; `/api/games/{game_id}/players/{player_id}?season=...&phase=...` returns the player's game line and available shot attempts. Scoreboard rows do not include a phase field, so upcoming phase labels use the known NBA Stats game-ID prefix; an unrecognized prefix is shown as unavailable. Requests run in a four-worker pool with a short admission limit and 12-second endpoint timeouts.

Successful results use a bounded in-memory TTL cache: 2 minutes for schedule, 15 minutes for season feeds, and 60 minutes for box scores/player views. The cache is cleared when the server restarts; no data is written to disk. The browser shows loading, empty, unsupported-season, API failure, and shot-chart unavailable states separately.

The season menu covers 1996-97 through the current season. NBA Stats is an unofficial source; it can rate-limit, time out, return empty results, or change its schema. Historical phase coverage and schedule rows vary. `ShotChartDetail` coordinate coverage is not established across every season; shot charts plot only real `LOC_X`/`LOC_Y` values returned for that player and game, and never estimate missing locations.

The existing desktop player projections, consistency analysis, defense boards, slate scanner, API explorer, and Picks Archive are not yet ported into web pages. Their implementations remain available in the optional desktop app. Files under `nba_terminal/data/picks/` are user data and were not changed.

## Verification commands

From the project root, backend checks use UV and enforce each new Python web/API module separately:

```sh
uv run ruff check .
uv run pytest tests
uv run pytest --cov=nba_terminal.services.game_center --cov-report=term-missing --cov-fail-under=93 tests
uv run pytest --cov=nba_terminal.webapp --cov-report=term-missing --cov-fail-under=93 tests
```

From `nba_terminal/web/`:

```sh
bun run test
bun run coverage
bun run lint
bun run format:check
bun run typecheck
bun run build
bun run e2e
```
