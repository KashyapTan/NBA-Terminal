# NBA Terminal Code Review Guide

Use this guide for reviewing changes to the PyQt NBA Terminal. The goal is not cosmetic churn; the goal is a reliable analytics desktop app that can grow into a serious NBA terminal.

## Review Scope

Review the supported app first:

- `nba_terminal/app.py`
- `nba_terminal/pages/`
- `nba_terminal/services/`
- `nba_terminal/ui/`
- `nba_terminal/analytics.py`
- `tests/`
- import-safe helpers in `nba_terminal/services/` and `nba_terminal/analytics.py`

Archived prototype scripts are useful source material only. The terminal app must not import from `archive/` or from root-level legacy scripts. If old logic is still important, migrate it into a page, service, or pure helper module under `nba_terminal/`.

## Reviewer A - Correctness and Data Logic

Check:

- The tab fulfills the stated user workflow.
- Team/player lookup handles abbreviations, nicknames, full names, ambiguous matches, and missing teams.
- Season strings and season types are passed correctly to NBA API endpoints.
- DataFrames are checked for emptiness before indexing with `iloc[0]`.
- Numeric columns are coerced safely before sorting, averaging, or formatting.
- Rankings sort in the intended direction, especially defense boards where lower opponent FG% is better.
- Prediction inputs match the model feature order and expected units.
- Home/away, rest days, opponent, pace, and zone-score calculations are not mixed between teams.
- UI filters refresh the displayed data without mutating cached source data incorrectly.
- Importing a module never prompts for input or launches a GUI.

Output format:

```markdown
## Reviewer A - Correctness and Data Logic

### Findings
- [SEVERITY] file:line - Issue - Suggested fix

### Verdict
PASS / FAIL
```

## Reviewer B - API Resilience and User Safety

Check:

- All live NBA API calls run outside the UI thread.
- Network calls use endpoint timeouts where the endpoint supports them.
- Long scans communicate progress and disabled states clearly.
- Empty API responses produce visible "no data" states, not misleading zeros.
- Broad exception handlers do not silently hide failures that affect betting-facing output.
- Pick archive reads are path-scoped to `nba_terminal/data/picks/`.
- Cache reads/writes are explicit and do not delete user data at import time.
- No secrets, tokens, or local absolute machine-specific paths are committed.
- The app avoids claiming certainty when data is stale, missing, or defaulted.

Output format:

```markdown
## Reviewer B - API Resilience and User Safety

### Findings
- [SEVERITY] file:line - Issue - Suggested fix

### Verdict
PASS / FAIL
```

## Reviewer C - Structure, Performance, and Testability

Check:

- Every terminal tab has its own page module.
- Shared logic is not duplicated across pages.
- NBA API access is in `services/`, not scattered through widget callbacks.
- Pure calculations are covered by deterministic tests.
- Heavy per-player loops are avoided where batch endpoints can work.
- UI widgets use stable layouts and do not resize unpredictably with dynamic data.
- The app remains navigable when a page fails to load.
- Ruff and coverage commands pass through UV.
- New dependencies are declared in `pyproject.toml` only.

Output format:

```markdown
## Reviewer C - Structure, Performance, and Testability

### Findings
- [SEVERITY] file:line - Issue - Suggested fix

### Verdict
PASS / FAIL
```

## Severity

- Critical: app cannot start, data corruption, destructive file behavior, or silently wrong betting-facing output.
- High: realistic crash, UI freeze, bad model input, missing API failure handling, or unbounded expensive scan.
- Medium: edge-case incorrectness, duplicated logic, weak test boundary, or unclear default/fallback behavior.
- Low: naming, small style issues, minor UI polish, or documentation gaps.

## Final Report Format

```markdown
# Code Review - <topic>

## Critical
- None / findings

## High
- None / findings

## Medium
- None / findings

## Low
- None / findings

## Changes Made
- Finding -> fix

## Tests and Commands
- `uv run ruff check .`
- `uv run coverage run -m pytest`
- `uv run coverage report`
- Optional Qt smoke command

## Remaining Risks
- Any API, model, UX, or data-quality caveats

## Verdict
READY / READY WITH CAVEATS / NOT READY
```

## Readiness Checklist

- The app starts through `uv run python -m nba_terminal`.
- No import-time prompts, network calls, GUI launches, or destructive writes.
- No terminal code imports from `archive/` or root-level prototype files.
- Navigation exposes the expected terminal tabs.
- Live API paths are threaded or otherwise non-blocking for the UI.
- Pure helper logic has tests.
- Ruff passes.
- Coverage report passes the configured threshold.
- Documentation reflects the actual project structure and commands.
