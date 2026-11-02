# New-week acquisition blocker: original primary-source diagnosis

Research task **NBA_WEEK_RESET_RESEARCH**, accepted brief revision1, attempt `attempt-18e449cc39df1bb8-42806-0`. Assessed repository `/Users/kash/Documents/NBA-Terminal` at **53e7ac1f4030d555a957124098e893496690b92e**, read-only, 2026-11-02. No implementation edits/publication, Firefox control, credentials, private payload capture or Fantasy transactions. Public evidence gathered 17:16–17:19 UTC; exact timestamps/requests retained below.

## Immediate outcome

**The daily-ledger blocker is based on a wrong interpretation of ESPN's flag.** ESPN's own basketball settings and team-counter JavaScript shows `matchupLimitPerScoringPeriod=true` means the **matchup acquisition allowance scales with the number of NBA game days in that matchup**. It does not establish a separate per-day transaction ceiling. The prior NBA_WAIVER_DATA_RESEARCH report and this task's early-handoff daily interpretation are superseded by this direct source evidence.

For today, preserve the user's newly supplied **matchup cap7 / used0 / remaining7**, explicitly labeled user-confirmed and bound to league604550749, season2027, current selected team, new matchup and confirmation time. Yesterday's6 is historical and irrelevant. The source correction removes the invented daily-ledger prerequisite; it does not disable any verified real rule. Counter recovery, scope validation, season acquisition limits, availability and other actual legality conditions remain independent.

The user's text proves the application activated its daily guard and could not establish current usage. It does **not** prove the user's actual raw flag/cap/map shape, which raw field triggered the guard, whether the deployed frontend matches source, or why the separate load error occurred. Those remain implementation-owned private diagnostics.

## Primary ESPN code: exact semantics

Live public page: [ESPN basketball league settings](https://fantasy.espn.com/basketball/league/settings?leagueId=1631984064&seasonId=2023). Its HTML supplied these ESPN-owned source URLs, fetched cookie-free:

- [Basketball settings bundle](https://cdn1.espn.net/kona/49f1381346a2-1.522/_next/1904a5b5-6da5-4c47-86b8-1c4b4638d358/page/basketball/league/settings.js), retained `espn-bundle-0.js` (285229 characters), retrieved 17:16:36.607484Z.
- [Basketball team bundle](https://cdn1.espn.net/kona/49f1381346a2-1.522/_next/1904a5b5-6da5-4c47-86b8-1c4b4638d358/page/basketball/team.js), retained `espn-team.js`, discovered through the public `/basketball/team?leagueId=1631984064&seasonId=2023&teamId=1` page at approximately17:17Z. `team-bundle-evidence.json` retains exact URL and offsets; the initial team fetch did not retain a separate precise timestamp.
- [Common bundle](https://cdn1.espn.net/kona/49f1381346a2-1.522/_next/static/commons/main-3005fbcf034081036a77.js), retained `espn-bundle-3.js`, retrieved17:16:36.606657Z.

`bundle-evidence.json` contains request URLs, timestamps, sizes, field offsets and adjacent original source. Offsets below are character offsets in retained minified files; all relevant portions are ASCII. Original files plus SHA256 manifest preserve source authority without relying on a summary.

**Settings module388**, settings-bundle offsets~68100–74100:

- Presents a matchup allowance, with a switch choosing a uniform limit for every matchup versus a proportional allowance. Positive values with scaling enabled are displayed for seven-day matchups.
- Helper `j` converts between persisted raw rate and displayed standard allowance: display uses `Math.round(raw * matchupPeriodLength * 7)`; save divides display amount by that factor. Therefore raw values can legitimately be fractional (e.g.4/7).
- Runtime helper `M` reads raw `matchupAcquisitionLimit`. With flagtrue and raw>0, it calls module310 for actual matchup length and returns **`Math.round(raw * actual_game_days)`**. With flagfalse it retains the raw fixed matchup allowance.
- Matchup sentinels0 and-1 are presented as unlimited. This differs from `acquisitionLimit` season setting, whose0 means no acquisitions and-1 unlimited (settings bundle offsets127600–129600). Do not use one generic count/sentinel decoder for both fields.

**Actual day-count module310**, settings bundle offset48871: obtains professional schedule data, asks module53 for matchup scoring periods, counts those scoring periods where **any professional team has games**, and returns that count; if no game days are found it returns the number of matchup scoring periods instead. This is league-wide game-day coverage, not selected roster games and not a blind calendar-day count. An incomplete schedule can undercount; the user cap7 fallback is appropriate today when API cap derivation cannot be verified.

**Period expansion**, common bundle near702438: gets `league.matchupPeriods[M]`, and expands each period index through `league.scoringPeriods[index-1]`. Common near159000 derives those grouped scoring periods from the selected `periodTypeId`'s segment-period definitions and their daily scoringPeriodStart/End. Thus the weekly `matchupPeriods` map is not generally a list of daily scoring IDs. Current application `matchup_scoring_periods` at espn_fantasy.py:608 recognizes `periodTypeId=2` as weekly and expands using verified date anchors; ordinary weeks and multiweek playoffs must stay distinct. The public historical payload independently shows M22 maps to weeks23/24 while root scoringPeriod176 is a daily ID.

**Counter scope**, team bundle offset50826: ESPN renders its matchup counter with `current: get(c.matchupAcquisitionTotals,e)||0`, where e is its selected matchup context. Its counter display component invokes the same effective matchup cap helper. Common near917036 sums matchup map values when checking the season acquisition allowance, while team UI also displays the separate `transactionCounter.acquisitions` season count. Neither is a daily counter.

**Upstream client verification, not semantic authority:** pinned cwendt94/espn-api revision700e15ddbb91124f031473d2411c8a6285944274 remains under the earlier report's `espn-api/`. [base_settings.py](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/base_settings.py) lines38–46 exposes acquisitionLimit, matchupAcquisitionLimit and optional flag without interpreting units. [settings tests](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/tests/baseball/unit/test_settings.py) test raw preservation and None defaults, not daily legality. They do not justify the prior daily interpretation. ESPN-owned runtime code above is stronger direct evidence.

## Live public basketball payload and zero evidence

`live-public.json` and `probe.py` retain cookie-free GET request details, start/end time, status, redacted useful fields. Unrelated historical public test league1631984064/2023 is schema evidence only, never the user's live usage.

Requests17:16:27.721221–17:16:27.982355Z:

1. `https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2023/segments/0/leagues/1631984064?view=mSettings&view=mTeam` ->200. Raw acquisitionLimit=-1, matchupAcquisitionLimit=1.0, flagtrue; periodTypeId2, currentMatchup22, scoringPeriod176, matchupPeriods22=[23,24]. Some teams have current matchup totals2,6,10 despite raw1. That is consistent with scaling a matchup cap and inconsistent with treating the matchup ledger as a single day's count.
2. Same URL `?view=mTeam` ->200. Returns `status` including currentMatchupPeriod, seasonId, scoringPeriodId and all team counters; no settings needed for this targeted counter refresh. This directly verifies the existing refresh view's useful scope.
3. Same URL `?view=mStatus` ->200, returns context including transactionScoringPeriod176. Status is useful scope/processing metadata, not a transaction ledger.
4. Same URL `?view=mTransactions2&scoringPeriodId=176`, header `x-fantasy-filter: {"transactions":{"filterType":{"value":["FREEAGENT","WAIVER","WAIVER_ERROR"]}}}` ->200 with **transactions key omitted**. A successful request is not evidence of an explicit empty array or zero count.

Historical team2/3/8/10 return present empty matchup maps and season acquisitions0. Team1 returns season acquisitions16 with a sparse map lacking current22; team5 explicitly has22:2, team6 has22:6, team7 has22:10. No explicit matchup-zero entry was observed in this public sample. Combined with ESPN UI's `get(map,M)||0`, this establishes **observable sparse-map zero display behavior**, not an official published JSON serialization guarantee.

Recommended distinctions:

| Evidence | Treatment |
|---|---|
| Fresh selected-team current-M integral API value>0 | Authoritative observed counter. Never replace with older/manual0. |
| Same context explicit API0 | Known0; preserve zero with explicit API provenance. |
| Fresh validated selected-team present object-valued map, current key absent | ESPN UI displays0. A strict app may infer sparse-map0 with distinct provenance, after verifying context and structural completeness; current user0 makes that inference unnecessary today. |
| Whole map/counter absent, null, malformed, team missing, season/M mismatch, stale request | Unknown; do not blanket default0. |
| Current user confirms0 for new M | Authorized explicit fallback; record as user, not API. Invalidate on context change/known acquisition/conflicting newer counter; do not reuse across weeks. |

There was no controlled before/after add event or new-week rollover observation; no Fantasy transaction was executed. Therefore I cannot claim an experimentally verified universal missing-key contract. A counter may also be LM-adjusted: ESPN's [Transaction Counter](https://support.espn.com/hc/en-us/articles/47186978217748-Transaction-Counter), updated2026-04-15, says H2H weekly acquisition counts can be adjusted. Its [settings help](https://support.espn.com/hc/en-us/articles/360000097492-Change-Acquisition-and-Waiver-Settings-LM-Only), updated2026-07-21, distinguishes season and matchup limits and excludes trades from signing limits. These support keeping counted adds separate from drops, lineup activations and trades.

## Current code defects and scope limits

1. **Definite false rule:** espn_fantasy.py:728–746 and:855–865 derive raw_cap via integer-only `count`, set flagtrue's reported scope to day and daily_add_limit to raw_cap. fantasy_planner_adapter.py:238 clears counts unconditionally for that flag/daily field. WaiverStatus.tsx:166 repeats the false daily prerequisite. Fix units at normalization, not only UI copy or a guard bypass. Preserve raw finite scaling rate separately and round only the effective matchup cap using ESPN's positive-value rounding.
2. **Fractional scaling loss:** valid raw4/7 is rejected before scaling. This is independently established by ESPN save conversion and synthetic input; not proof this private league returns a fraction.
3. **Sentinel conflation:** `count(0)` becomes hard zero matchup cap, whereas ESPN matchup UI treats0 as unlimited. Season0 remains prohibited. Do not interpret unlimited as an arbitrary huge budget; user-specified planning budget can bound search while reporting unlimited provider rule honestly.
4. **Not a demonstrated zero-truthiness bug:** `count` (espn_fantasy.py:595), targeted snapshot:204–223 and normalized usage:780–807 preserve explicit0 with `is not None`. Missing map/key is the existing conservative unknown path. The root cause of the private unknown cannot be asserted without sanitized payload diagnostics.
5. **Refresh overbinding:** frontend LeagueFantasy.tsx:573–579 clears manual confirmation when `counts_snapshot_at != snapshot.fetched_at`; adapter:164–172 returns early on the same mismatch. Tests/test_fantasy_provider_recovery.py:185 deliberately asserts that behavior. This prevents a stale zero being silently reconfirmed, but invalidates evidence on every background snapshot, even unchanged league/team/M. Carry a separate user evidence timestamp/context and compare authoritative counter changes or age/event policy. Do not overwrite its confirmation time to pretend a new confirmation occurred. For today's authorized correction, bind fresh7/0 explicitly rather than make the user fill another form.
6. **Season context omission:** adapter expected preference context at:154–161 includes league/team/M but not season. Frontend request context similarly omits season. Snapshot league requests and targeted mTeam refresh do check season, but manual evidence should additionally bind season and transaction/scoring-period context where required. Same league/team/M number can recur next season.
7. **Refresh/race:** snapshot refresh requests mTeam once on missing/invalid selected current key, checking league/season/currentM and selecting team by ID. Live public mTeam confirms status is present. If a week rolls between base and refresh, current code rejects refresh instead of using its counter under oldM; correct rejection. A bounded restart with fresh full context is preferable to mixing periods or retaining last week's manual count. Record request_started_at/completed_at and raw status fields; normalized fetched_at alone is not proof all constituent calls describe the same moment.
8. **Scope of hardcoded fallback:** current normalization contains league604550749/season2027 fallback7 with label league_fallback_7, independent of individual new-matchup confirmation. Today's explicit user cap validates this value for today's scope; it is not a provider default or future-week authorization.

For private implementer diagnostics, request only league_id, seasonId, selectedteam ID, raw and normalized M/D/transactionScoringPeriod, request start/end, flag presence/value, raw limit finite value, derived day count/method, counter/map/key presence and parsed current value. No owners, members, credentials or full private payload are needed. Preserve positive fresh API counter precedence. The generic load error may be a different endpoint; do not attribute it to ESPN fields from UI text alone.

## If a separate real daily rule exists: safe conditions

This is a mathematical fallback for a genuinely verified daily constraint, **not the meaning of ESPN's flag**. Let W be known matchup cap, U a trustworthy nonnegative count of all already-counted acquisitions in that matchup, P total planned counted acquisitions, and Ld each real daily cap. Require U+P<=W. If every relevant day's counted acquisitions are a subset of that same matchup count, no negative/LM adjustments break that inequality, and no unmodeled pending/external acquisitions intervene, existing day usage Bd<=U. Then **U+P<=Ld for every planned day** is sufficient without a full daily ledger. In particular U=0,W=7,P<=7 and Ld>=7 proves the daily bound. More precisely with known daily usage Bd and planned adds pd, require Bd+pd<=Ld, including pending/external adds that count. With no ledger, U+pd<=Ld is a tighter per-day sufficient test than U+P<=Ld.

Do not use this proof if daily window overlaps acquisitions outside the modeled matchup, reset timezone/boundaries differ, U is unknown or adjusted downward, cap units are unknown, the plan crosses matchups, or counted acquisitions include events the planner ignores. Count adds through free agency/waivers; do not count drops/trades/activations as adds. A declaration of cap7 alone does not establish usage0; today's separate user0 does. An explicit zero adjusted matchup counter alone does not prove a historical day ledger sums to0 when negative corrections exist.

## Optional NBA actuals at start of week

Actuals source paths: fantasy_actuals.py:327–363 builds days with p<=current and fetches `mMatchupScore+mScoreboard`, scoringPeriodId=p, filter `{schedule:{filterMatchupPeriodIds:{value:[M]}}}`. reconstruct:235–248 requires each day's historical daily roster before checking whether any bankable game started. Missing today's roster therefore sets expected_player_games=None even if all games are pregame. A valid explicit empty daily roster yields known0; missing is not an empty lineup.

Live [ESPN NBA scoreboard for20261102](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261102) returned200 at17:16:27.982355Z: 15 scheduled games, all statepre, earliest00:00Z Nov3 (7PM EST Nov2). This is current public corroboration of no games begun at observation time, not proof of the user's period calendar, fantasy historical ownership or NBA CDN availability.

When the entire verified matchup-to-now schedule has no started games, known banked production0 can be established without future lineup decisions. Represent `no_started_games`/eligible started-games0 separately from future eligible lineup unknown. If schedule coverage or earlier matchup history is incomplete, retain unknown NBA coverage. For mixed started/unstarted days, require lineup/ownership only where credit could already exist; never invent unknown historical active lineups. NBA supplies production/schedule, not Fantasy ownership; future lineup facts cannot be fetched as settled history.

Current reconstruct:296–318 already selects complete official ESPN primitives whenever NBA basis incomplete; synthetic evidence confirms forecast_complete=true in that case. The user's complete official basis at17:02:22.264988Z is accepted context, not independently fetched private evidence here. Preserve it and show one compact basis line, source response time, optional NBA coverage state and expandable gap reasons. Evaluation time is not feed freshness.

`ActualSources.tsx` computes hasTotals across official/derived/forecast; if any category exists, renders all9 rows in an expandable comparison table. A completely blank comparison is not predicted by this source when official totals are complete; inspect deployed module/CSS/state before claiming cause. Prefer show table only if a source supplies actual numeric values, render missing source cells as unavailable, and show an explicit empty-state explanation if none. Do not hide complete official scoring because comparison source is missing. Zero primitives are valid; FG/FT percentages with0 attempts are undefined, not data gaps or fabricated0%.

## Lightweight transaction metadata

[Basketball client transactions/recent activity](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/basketball/league.py) lines116–195 provide exact optional requests:

- `view=mTransactions2&scoringPeriodId=D`, x-fantasy-filter transaction typesFREEAGENT,WAIVER,WAIVER_ERROR. Prefer retaining returned ID/status/scoring period/execution time/to-team/from-team/item acquisition type for recent-change diagnostics. Upstream docstring calls this recent transactions, not guaranteed complete historical counter reconstruction.
- `/communication/?view=kona_league_communication`, topics filterType ACTIVITY_TRANSACTIONS, limit/offset, message type IDs178,180,179,239,181,244,188; sort descending by messageDate. Unit test basketball/unit/test_league.py:360 verifies filtered request construction, not public accessibility or completeness.

Additional public probes17:18:53Z in `transaction-metadata.json`: D21 transactions request200 with explicit empty list; communication404. D176 omitted transactions key as above. These are different shapes, neither proves user's0 or all adjusted acquisition history. Use the fresh direct counter/user confirmation for today, not a full private transaction reconstruction. Pending/status metadata can invalidate a fallback or explain a changed count, but absence in one limited feed cannot certify no acquisitions.

## Independent synthetic reproductions and minimal regressions

Executed successfully against assessed main without bytecode/check-out writes:

`PYTHONDONTWRITEBYTECODE=1 /Users/kash/Documents/NBA-Terminal/.venv/bin/python /Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_RESEARCH/reproduce.py`

Outputs `reproductions.json`:

- Raw1/flagtrue/currentM explicit0 preserves used0 yet user-confirmed7/0 still returns conditional, actions0, daily-ledger gap. Raw4/7 similarly fails; normalized reported cap becomesNone.
- Raw1/flagtrue/map{} yields usedNone; raw current2 yields used2; these confirm parser distinctions, not live private input.
- Identical league/team/M with only fetched_at changed by1 second rejects confirmed counts as older data.
- Missing today's daily lineup and no production rows yields expectedNone/partial NBA while official zero primitives remain forecast_complete=true. Explicit valid empty lineup yields expected0/complete0. These model the distinction rather than proving private gaps.

Focused regression recipes for implementation:

1. Seven verified NBA game-days: raw1/true=>effective7; raw4/7=>4; six days=>6 forraw1; thirteen days=>13; fixed7/false remains7. Off-day and all-zero-day fallback cases follow provider helper, not selected roster game count. Fractional rate rounding must match JavaScript Math.round for nonnegative values. Missing day coverage uses explicit scoped user7 or unknown, not guessed API7.
2. Matchup0/-1 unlimited, season0 disallows acquisitions, season-1 unlimited; finite season limit independently constrains adds. No daily gate created from scaling flag. Missing optional flag remains unknown scope unless explicit user configuration supplies the required matchup budget.
3. Explicit current-M0 and positive counts survive; present sparse map inference retains separate provenance; missing/null/map malformed/team mismatch/season mismatch/oldM reject. Never use scoringPeriodId as matchup-map key. New week discards old6 and accepts today's bound0; fresh APIpositive defeats stale0.
4. User-confirmed7/0 produces a legal ordered sequence where other required inputs support one. Background same-context refresh must not erase authorized evidence solely for fetched_at; actual acquisition/counter change, conflicting evidence, context change and policy expiry invalidate honestly. No repeated form required for this accepted correction.
5. Week rollover between reads triggers a bounded full-context refresh, not mixed roster/old counter. Season binding part of manual context. Missing selected team cannot become another team's0.
6. Optional NBA missing today's pregame lineup distinguishes future-lineup unknown from no started production. Known no-started-games0 requires complete current matchup schedule; schedule unknown stays unknown. Complete official ESPN basis survives optional NBA failures. Table shows official rows and unavailable optional cells; no blank table shell. No current roster substituted for historical lineup.

No checkout tests were added or implementation tests claimed passed; this task's script is diagnosis, not the implementation worker's final validation. No private current payload was available. No additional user decision is required for the already-authorized today's7/0 fallback.

## Artifact index and delivery

This report is authoritative over `early-handoff.md` where the latter assumes daily semantics. `decisive-correction.md` was sent promptly through task-bound working reports before final delivery. All artifacts retained in `/Users/kash/.local/share/multplx/home/data/NBA_WEEK_RESET_RESEARCH/`:

- `probe.py`, `live-public.json`: exact fresh public endpoint requests/time/context/counters, no member or credential dump.
- `public-page.html`, `espn-bundle-0.js`, `espn-bundle-1.js`, `espn-bundle-2.js`, `espn-bundle-3.js`, `espn-team.js`: original publicly served ESPN source.
- `bundle-evidence.json`, `team-bundle-evidence.json`: source excerpts/offsets/URLs; `transaction-metadata.json`: additional feed probes.
- `reproduce.py`, `reproductions.json`: independent synthetic diagnosis.
- `manifest.json`: hashes/revision/provenance boundary.
- Historical pinned client source and old report remain at `/Users/kash/.local/share/multplx/home/data/NBA_WAIVER_DATA_RESEARCH/`; use its original sources, not its superseded daily interpretation.
