# NBA Terminal - Agent Guide

This project is a PyQt desktop app for NBA analytics: player stats, player prop prediction, team defense boards, coefficient-of-variation consistency views, slate scanning, historical picks, and NBA API exploration. Treat it as the first version of an NBA-focused Bloomberg Terminal.

## Project Shape

The supported application lives in `nba_terminal/`.

- `nba_terminal/app.py` - main PyQt shell and left-side navigation.
- `nba_terminal/assets/fonts/` - bundled Qt UI font assets. Keep UI fonts packaged here so headless and desktop rendering do not depend on host font discovery.
- `nba_terminal/pages/` - one module per terminal tab.
- `nba_terminal/services/` - data access wrappers for NBA API calls and local picks.
- `nba_terminal/ui/` - shared Qt widget/layout helpers.
- `nba_terminal/analytics.py` - pure ranking, formatting, and summarization helpers.
- `tests/` - unit tests for pure app logic.
- `nba_terminal/data/picks/` - historical pick notes used by the Picks Archive tab.
- `archive/` - old prototypes, experiments, and generated artifacts. The terminal app must not import from here.

## Python and UV

Use UV for the whole Python project. Do not add `requirements.txt` or ad hoc pip instructions unless there is a specific compatibility reason.

```powershell
uv sync --all-extras --dev
uv run python -m nba_terminal
uv run nba-terminal
uv run ruff check .
uv run coverage run -m pytest
uv run coverage report
```

For headless Qt smoke checks:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; uv run python -c "from PyQt6.QtWidgets import QApplication; from nba_terminal.app import NBATerminal; from nba_terminal.theme import apply_app_theme; app=QApplication([]); apply_app_theme(app); window=NBATerminal(); print(window.stack.count())"
```

## Development Rules

- Keep each tab in its own `nba_terminal/pages/<feature>.py` file.
- Put NBA API calls, cache logic, and expensive data workflows in `nba_terminal/services/`.
- Put pure calculations in `nba_terminal/analytics.py` or a focused module under `nba_terminal/`.
- Do not add import-time prompts, network calls, GUI launches, cache deletion, or file writes.
- Do not block the Qt UI thread with NBA API calls. Use `QThread` workers or service functions called from workers.
- Prefer batch endpoints such as `LeagueDashPlayerStats`, `LeagueDashTeamStats`, and `LeagueDashTeamShotLocations` before per-player loops.
- Handle NBA API failures explicitly. These endpoints can timeout, rate-limit, return empty frames, or drift schemas.
- Keep betting-facing output honest: if data is missing or defaulted, show that state instead of silently implying certainty.
- Use `nba_terminal/data/picks/` only as user data. Do not rewrite historical pick files unless asked.
- No terminal page or service may import or reference root-level legacy scripts or files under `archive/`.

## Lint and Tests

Ruff is configured for the supported app package and tests. Legacy prototype scripts are excluded from the formal lint gate while their logic is migrated into `nba_terminal/`.

Coverage is intentionally enforced at 100% for the tested pure modules. GUI and live NBA API paths are not counted in coverage yet because they need either Qt test tooling or mocked service boundaries.

When adding code:

1. Add or update pure helper tests for deterministic logic.
2. For UI pages, smoke-test import/instantiation with `QT_QPA_PLATFORM=offscreen`.
3. Run `uv run ruff check .`.
4. Run `uv run coverage run -m pytest` and `uv run coverage report`.

## Review Expectations

Use `CODE_REVIEW_GUIDE.md` for substantive changes. Focus on correctness, API resilience, UI responsiveness, data honesty, and maintainable app structure.

For high-risk changes such as model logic, slate scanner logic, cache policy, or broad service refactors, create a review note under `code_review/` summarizing findings, fixes, and remaining risks.
