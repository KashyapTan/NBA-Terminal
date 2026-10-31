# Fantasy dashboard and navigation handoff

Owned branch: `mx/NBA_FANTASY_DASHBOARD`, accepted base `292e17885ae96613254c936c2189162a8b9bfa0f`.

## Integration seam

`FantasyPage.tsx` default export accepts `FantasyPageProps`: `{ meta: Meta; league?: FantasyLeagueSlots }`.
`FantasyLeagueSlots` has optional `ReactNode` properties `dashboard`, `matchups`, `waiver`. For example, integration can pass `<FantasyPage meta={meta} league={{dashboard: <LeagueSummary />, matchups: <LeagueMatchups />, waiver: <LeagueWaivers />}} />` using actual sibling exports. This branch imports no league implementation or backend/auth types. Integration owns the composition in App.tsx and the provider/state shared between these nodes.

Dashboard league content renders above the season snapshot. Matchups and Waiver Wire render their league slot without fetching season player stats. Missing slots render an honest unlinked prompt, with no nonfunctional connect button. Supply a real connection form/status in these slots; the fallback does not assert any auth support. Slot components own refresh, timestamps, connection state, league totals, loading/errors and transactional restrictions. No credential handling is added here.

URL contract: `/fantasy?fantasyTab=dashboard|matchups|leaders|waiver&season=YYYY-YY`. Missing/unknown tab defaults to Dashboard. Tab and season changes preserve all other query parameters. Subtabs support ArrowLeft/ArrowRight, Home/End, roving focus and labelled panels. Existing player ranking/category/comparison/shortlist tools live in Leaders. App.tsx and shared navigation are untouched; collapsible global navigation remains outside this allocation.

The snapshot uses NBA Stats actuals, not league standings. Nine category cards show per-game leaders, with turnovers ascending and FG/FT derived from makes/attempts. Playing-time filters and percentage attempt limits apply. All default to zero and the UI explicitly warns about small samples. No schedules, ownership, projections or win probabilities are inferred from this player table.

Preferences remain under `nba-terminal.fantasy.preferences.v1`; old settings migrate with zero for the new `minimumMinutesPerGame` and `minimumTotalMinutes` fields. New limits are integer nonnegative values, capped at 1000 MPG and 10000 season minutes, alongside existing games/attempt filters. A positive threshold rejects missing/nonfinite samples. Zero disables that threshold. Shortlist stays device-local. Comparison/search/temporary UI state is retained between Dashboard and Leaders; moving to a league view unmounts season tools, so temporary comparisons reset, while preferences and shortlist persist.

## Review findings and risk

Focused review checked season/tab URL preservation, unknown samples, percentage denominators, lower-is-better turnovers, preference migration and credential-free storage. Nonfinite counting stats, nonfinite game denominators and invalid percentages (negative makes, makes exceeding attempts, nonfinite inputs) now resolve to unavailable rather than sorting as a plausible value. Restored turnover rankings now initialize with ascending order; a persisted turnover category previously displayed the wrong direction until clicked again. No optimizer, probability model, authorization or backend behavior changed.

Production league wiring and combined end-to-end checks belong to integration. The focused fantasy end-to-end test now verifies the new default, selects Leaders and covers persisted MPG and tab/season navigation. Other consumers that expect rankings immediately at `/fantasy` need to select Leaders or use `fantasyTab=leaders`.
