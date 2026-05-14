# NBA Terminal

NBA Terminal is a PyQt desktop app for NBA research, player stats, projection work, team defense views, consistency analysis, slate scanning, NBA API discovery, and historical picks.

The supported app code lives under `nba_terminal/`. Old prototypes and exploratory scripts are archived under `archive/`.

## Run

```powershell
uv sync --all-extras --dev
uv run python -m nba_terminal
```

Equivalent script entrypoint:

```powershell
uv run nba-terminal
```

## Dev Commands

```powershell
uv run ruff check .
uv run coverage run -m pytest
uv run coverage report
```

Headless Qt startup smoke test:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; uv run python -c "from PyQt6.QtWidgets import QApplication; from nba_terminal.app import NBATerminal; from nba_terminal.theme import apply_app_theme; app=QApplication([]); apply_app_theme(app); window=NBATerminal(); print(window.stack.count())"
```

## Structure

```text
nba_terminal/
  app.py                  # main PyQt shell and sidebar navigation
  analytics.py            # pure ranking/formatting helpers
  assets/fonts/           # bundled Qt UI font for reliable desktop/headless rendering
  data/picks/             # historical pick notes used by Picks Archive
  pages/                  # one module per terminal tab
  services/               # NBA API and data services
  ui/                     # shared Qt helpers
  theme.py                # colors and app stylesheet
tests/                    # unit and architecture tests
code_review/              # review notes
archive/                  # old prototypes, experiments, and generated artifacts
```

## Tabs

- Dashboard
- Player Analytics
- Points Predictor
- Team Defense
- Consistency
- Slate Scanner
- Stats Explorer
- Picks Archive

## Notes

NBA Stats endpoints are unofficial and can timeout, rate-limit, return empty frames, or drift schemas. New terminal features should keep API calls in `nba_terminal/services/`, run expensive work off the Qt UI thread, and show clear no-data/error states.
