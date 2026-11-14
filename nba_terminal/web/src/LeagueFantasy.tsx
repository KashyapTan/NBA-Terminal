import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  type ConnectLeague,
  categoryValue,
  compareCategory,
  DEFAULT_ESPN_LEAGUE_ID,
  DEFAULT_ESPN_SEASON_ID,
  eligibleCandidates,
  formatCategory,
  LEAGUE_CATEGORIES,
  type LeagueSnapshot,
  type LeagueTeam,
  type PlannerPreferences,
  type WaiverPlan,
} from "./league-fantasy-model";
import "./league-fantasy.css";
import { ActualSources } from "./ActualSources";
import { EspnBrowserConnect } from "./EspnBrowserConnect";
import { useWaiverPlan } from "./fantasy-lifecycle";
import { InfoTooltip } from "./InfoTooltip";
import { matchupForecastData } from "./MatchupForecast";
import { bindUsage } from "./usage-declaration";
import { OverallPlanImpact, WaiverArithmetic } from "./WaiverArithmetic";
import { DEFAULT_PICKUP_FILTERS, WaiverWorkspace, type WorkspaceStop } from "./WaiverWorkspace";

export { useLeagueFantasy } from "./use-league-session";

import { useLeagueFantasy } from "./use-league-session";
export type LeagueFantasyState = Omit<
  ReturnType<typeof useLeagueFantasy>,
  "refreshStatus" | "lifecycle"
> & {
  lifecycle?: import("./fantasy-lifecycle").FantasyLifecycle;
  refreshStatus?: () => Promise<void>;
};

export function LeagueConnection({ state }: { state: LeagueFantasyState }) {
  const [privateLeague, setPrivateLeague] = useState(false);
  const localHost = ["localhost", "127.0.0.1", "[::1]", "::1"].includes(window.location.hostname);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const input: ConnectLeague = {
      league_id: Number(fields.get("league")),
      season_id: Number(fields.get("season")),
    };
    if (privateLeague) {
      input.swid = String(fields.get("swid") ?? "").trim();
      input.espn_s2 = String(fields.get("s2") ?? "").trim();
    }
    // Clear sensitive DOM inputs immediately; credentials are never kept in React state or browser storage.
    form.reset();
    await state.connect(input);
    delete input.swid;
    delete input.espn_s2;
  }
  if (!localHost)
    return (
      <section className="league-panel" aria-label="ESPN league connection">
        <h2>ESPN connection requires local access</h2>
        <p>
          Open NBA Terminal on localhost or 127.0.0.1 using its single-process local server. Remote
          hosting does not support ESPN sessions. Keep private cookies in your own local connection
          form; never send them in chat or issue reports.
        </p>
      </section>
    );
  return (
    <section className="league-panel" aria-label="ESPN league connection">
      <h2>Connect your ESPN league</h2>
      <p>
        Read-only recommendations. No roster changes are submitted. Requires this app running
        locally on loopback; unofficial ESPN access may be unavailable.
      </p>
      {state.loading && <p role="status">Loading league connection…</p>}
      {state.error && <p role="alert">{state.error}</p>}
      {state.status.connected ? (
        <>
          <p>
            Connected · {state.status.auth_mode} access ·{" "}
            {state.status.ownership_verified
              ? "Team ownership verified"
              : "Team ownership unverified"}
          </p>
          <label>
            Your team
            <select
              aria-label="Your ESPN team"
              value={state.status.team_id ?? ""}
              onChange={(event) => void state.selectTeam(Number(event.target.value))}
            >
              <option value="" disabled>
                Select your team
              </option>
              {state.status.teams?.map((team) => (
                <option key={team.id} value={team.id} disabled={!team.selectable}>
                  {team.name}
                  {team.ownership_verified ? " · verified" : ""}
                </option>
              ))}
            </select>
          </label>
          {state.status.expires_at && (
            <p>
              Session expires{" "}
              <time dateTime={state.status.expires_at}>{state.status.expires_at}</time>. Restarting
              the server disconnects it.
            </p>
          )}
          <button type="button" disabled={state.loading} onClick={() => void state.disconnect()}>
            Disconnect ESPN
          </button>
        </>
      ) : (
        <>
          <EspnBrowserConnect onConnected={state.refreshStatus} />
          <details className="manual-espn-connect">
            <summary>Manual or public league fallback</summary>
            <form onSubmit={submit} autoComplete="off">
              <div className="league-fields">
                <label>
                  Manual league ID
                  <input
                    name="league"
                    type="number"
                    min="1"
                    step="1"
                    required
                    defaultValue={state.status.league_id ?? DEFAULT_ESPN_LEAGUE_ID}
                  />
                </label>
                <label>
                  Manual season ending year
                  <input
                    name="season"
                    type="number"
                    min="2019"
                    max="2100"
                    step="1"
                    required
                    defaultValue={state.status.season_id ?? DEFAULT_ESPN_SEASON_ID}
                  />
                </label>
              </div>
              <label className="league-check">
                <input
                  type="checkbox"
                  checked={privateLeague}
                  onChange={(event) => setPrivateLeague(event.target.checked)}
                />
                Private league
              </label>
              {privateLeague && (
                <fieldset>
                  <legend>Private ESPN cookies</legend>
                  <p>
                    While signed in to ESPN in your browser, open developer tools →
                    Application/Storage → Cookies for ESPN. Copy SWID and espn_s2 here. This is
                    cookie-based access, not OAuth; never share these values. They are sent once in
                    the connection POST body, retained only in server memory for this session, and
                    cleared by disconnect.
                  </p>
                  <label>
                    SWID
                    <input name="swid" type="password" autoComplete="off" required />
                  </label>
                  <label>
                    espn_s2
                    <input name="s2" type="password" autoComplete="off" required />
                  </label>
                </fieldset>
              )}
              <button type="submit" disabled={state.loading}>
                Connect manually
              </button>
            </form>
          </details>
        </>
      )}
    </section>
  );
}

function SnapshotHeading({
  snapshot,
  loading,
  onRefresh,
}: {
  snapshot: LeagueSnapshot;
  loading?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <header className="league-heading">
      <div>
        <span className="league-eyebrow">
          {snapshot.league.name} · {snapshot.league.team_count} teams
        </span>
        <p>
          Matchup period {snapshot.period.matchup_period_id} ·{" "}
          {snapshot.period.start_date ?? snapshot.period.dates[0] ?? "Date unavailable"} –{" "}
          {snapshot.period.end_date ?? snapshot.period.dates.at(-1) ?? "Date unavailable"}
        </p>
        <small>
          ESPN unofficial · Updated{" "}
          <time dateTime={snapshot.fetched_at}>
            {new Date(snapshot.fetched_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </time>
          {loading ? " · Refreshing…" : ""}
        </small>
      </div>
      {onRefresh && (
        <button type="button" disabled={loading} onClick={onRefresh}>
          Refresh league
        </button>
      )}
    </header>
  );
}
function TodayRoster({ team, scoringPeriodId }: { team: LeagueTeam; scoringPeriodId: number }) {
  const players = team.roster.filter((player) => player.today === true);
  const missing = team.roster.some((player) => player.today === null);
  return (
    <section className="league-roster">
      <h3>{team.name} · Today</h3>
      {players.length === 0 && (
        <p>
          {missing
            ? "Today's schedule is unavailable for some players."
            : "No scheduled players reported today."}
        </p>
      )}
      <ul>
        {players.map((player) => (
          <li key={player.id}>
            <b>{player.name}</b>
            <span>
              {player.lineup_slot ?? "Slot unknown"} ·{" "}
              {player.schedule?.some(
                (game) => game.started && game.scoring_period_id === scoringPeriodId,
              )
                ? "Game started (not live status)"
                : "Scheduled"}{" "}
              · {player.injury_status ?? "Injury status unknown"}
            </span>
          </li>
        ))}
      </ul>
      {missing && players.length > 0 && <small>Some roster schedules are unavailable.</small>}
    </section>
  );
}
export function Matchups({
  snapshot,
  loading = false,
  error,
  onRefresh,
}: {
  snapshot: LeagueSnapshot | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}) {
  const [comparisonId, setComparisonId] = useState<number | null>(null);
  useEffect(() => {
    setComparisonId(null);
  }, [snapshot?.league.id, snapshot?.selected_team_id, snapshot?.period.matchup_period_id]);
  if (!snapshot)
    return (
      <section className="league-panel league-matchups">
        <h2>Matchups</h2>
        <p role={error ? "alert" : "status"}>
          {error ??
            (loading
              ? "Loading matchup…"
              : "Connect ESPN and select your team to view current matchup totals.")}
        </p>
      </section>
    );
  const user = snapshot.teams.find((team) => team.id === snapshot.selected_team_id);
  const opponent = snapshot.teams.find((team) => team.id === snapshot.opponent_team_id);
  const comparison =
    snapshot.teams.find((team) => team.id === comparisonId && team.id !== user?.id) ?? opponent;
  const results = LEAGUE_CATEGORIES.map((category) => ({
    ...category,
    user: categoryValue(user?.totals ?? null, category.key),
    opponent: categoryValue(comparison?.totals ?? null, category.key),
  }));
  const tally = results.reduce(
    (counts, row) => {
      counts[compareCategory(row.user, row.opponent, row.key)]++;
      return counts;
    },
    { winning: 0, tied: 0, losing: 0, unknown: 0 },
  );
  return (
    <section className="league-panel league-matchups">
      <h2>Current opponent: {opponent?.name ?? "Not available"}</h2>
      {error && <p role="alert">{error}</p>}
      {!snapshot.league.supported && (
        <p role="alert">
          {snapshot.league.unsupported_reason ?? "This league format is unsupported."}
        </p>
      )}
      <div className="matchup-scoreboard" aria-live="polite">
        <div>
          <span className="league-kicker">
            {comparison?.id !== opponent?.id ? "Hypothetical comparison" : "Current matchup"}
          </span>
          <h3>
            {user?.name ?? "Your team"} <span>vs {comparison?.name ?? "Unavailable"}</span>
          </h3>
          <p>Category score · current cumulative totals</p>
        </div>
        <div className="matchup-record">
          <strong aria-label={`${tally.winning} wins, ${tally.losing} losses, ${tally.tied} ties`}>
            <span className="league-winning">{tally.winning}</span>-
            <span className="league-losing">{tally.losing}</span>-
            <span className="league-tied">{tally.tied}</span>
          </strong>
          <span>WINS · LOSSES · TIES</span>
          {tally.unknown > 0 && <small>{tally.unknown} categories unavailable</small>}
        </div>
      </div>
      <SnapshotHeading snapshot={snapshot} loading={loading} onRefresh={onRefresh} />
      <div className="matchup-controls">
        <label>
          Compare same-period totals
          <select
            aria-label="Compare league team"
            value={comparison?.id ?? ""}
            onChange={(event) => setComparisonId(Number(event.target.value))}
          >
            {!comparison && <option value="">Select a team</option>}
            {snapshot.teams
              .filter((team) => team.id !== snapshot.selected_team_id)
              .sort(
                (a, b) =>
                  Number(b.id === snapshot.opponent_team_id) -
                  Number(a.id === snapshot.opponent_team_id),
              )
              .map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                  {team.id === snapshot.opponent_team_id ? " · current opponent" : ""}
                </option>
              ))}
          </select>
        </label>
      </div>
      <div className="league-table-wrap">
        <table>
          <caption>
            Current cumulative matchup totals · {user?.name ?? "Your team"} vs{" "}
            {comparison?.name ?? "Team unavailable"}
          </caption>
          <thead>
            <tr>
              <th>Category</th>
              <th>{user?.name ?? "Your totals"}</th>
              <th>{comparison?.name ?? "Compared totals"}</th>
              <th>Standing</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => {
              const state = compareCategory(row.user, row.opponent, row.key);
              return (
                <tr key={row.key} className={`category-row category-${state}`}>
                  <th scope="row">
                    {row.label}
                    <small>{row.key === "to" ? "Lower is better" : "Higher is better"}</small>
                  </th>
                  <td>{formatCategory(row.user, row.key)}</td>
                  <td>{formatCategory(row.opponent, row.key)}</td>
                  <td className={`league-${state}`}>
                    <span className="category-status">
                      {state === "winning"
                        ? "↑ Leading"
                        : state === "losing"
                          ? "↓ Trailing"
                          : state === "tied"
                            ? "= Tied"
                            : "— Unknown"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p>
        FG% and FT% use total makes ÷ attempts when available. Unknown categories do not count as
        wins; ties remain ties.
      </p>
      <ActualSources teams={[user, comparison]} />
      <div className="league-rosters">
        {user && <TodayRoster team={user} scoringPeriodId={snapshot.period.scoring_period_id} />}
        {comparison && (
          <TodayRoster team={comparison} scoringPeriodId={snapshot.period.scoring_period_id} />
        )}
      </div>
      <DataGaps gaps={snapshot.data_gaps} />
    </section>
  );
}
function DataGaps({ gaps }: { gaps: string[] }) {
  return gaps.length > 0 ? (
    <details className="league-gaps">
      <summary>Data gaps ({gaps.length})</summary>
      <ul>
        {gaps.map((gap, index) => (
          <li key={`${index}-${gap}`}>{gap}</li>
        ))}
      </ul>
    </details>
  ) : null;
}
export function WaiverWire({
  snapshot,
  onPlan,
  loading = false,
  error,
  onRefresh,
}: {
  snapshot: LeagueSnapshot | null;
  onPlan?: (preferences: PlannerPreferences) => Promise<WaiverPlan>;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}) {
  if (!snapshot)
    return (
      <section className="league-panel">
        <h2>Waiver Wire</h2>
        <p role={error ? "alert" : "status"}>
          {error ??
            (loading
              ? "Loading your league…"
              : "Connect ESPN and select your team to find matchup opportunities.")}
        </p>
        {!loading && <a href="/fantasy?fantasyTab=dashboard">Connect ESPN</a>}
      </section>
    );
  const contextKey = `${snapshot.league.id}:${snapshot.league.season_id}:${snapshot.selected_team_id}:${snapshot.period.matchup_period_id}`;
  return (
    <WaiverStrategy
      key={contextKey}
      snapshot={snapshot}
      onPlan={onPlan}
      loading={loading}
      error={error}
      onRefresh={onRefresh}
    />
  );
}

function WaiverStrategy({
  snapshot,
  onPlan,
  loading,
  error: leagueError,
  onRefresh,
}: {
  snapshot: LeagueSnapshot;
  onPlan?: (preferences: PlannerPreferences) => Promise<WaiverPlan>;
  loading: boolean;
  error?: string | null;
  onRefresh?: () => void;
}) {
  const capStorageKey = `nba-terminal:matchup-cap:${snapshot.league.id}:${snapshot.league.season_id}`;
  const [preferences, setPreferences] = useState<PlannerPreferences>(() => {
    const declaredCap =
      snapshot.league.id === DEFAULT_ESPN_LEAGUE_ID &&
      snapshot.league.season_id === DEFAULT_ESPN_SEASON_ID
        ? 7
        : null;
    try {
      const saved = localStorage.getItem(capStorageKey);
      // User-confirmed configuration applies only to this league and season;
      // it never supplies today's acquisition usage.
      const cap = saved === null ? declaredCap : Number(saved);
      return cap != null && Number.isInteger(cap) && cap >= 0
        ? { matchup_add_limit_fallback: cap }
        : {};
    } catch {
      return declaredCap == null ? {} : { matchup_add_limit_fallback: declaredCap };
    }
  });
  const advancedPanel = useRef<HTMLDetailsElement>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (
      preferences.user_confirmed_counts &&
      !preferences.usage_declaration &&
      preferences.counts_snapshot_at !== snapshot.fetched_at
    )
      setPreferences((current) => ({ ...current, user_confirmed_counts: false }));
  }, [
    preferences.user_confirmed_counts,
    preferences.usage_declaration,
    preferences.counts_snapshot_at,
    snapshot.fetched_at,
  ]);
  const { plan, busy, error, lifecycle, cancelSearch } = useWaiverPlan(
    snapshot,
    preferences,
    onPlan,
    attempt,
    !!leagueError,
    loading,
  );
  function edit(patch: Partial<PlannerPreferences>) {
    setPreferences((current) => ({ ...current, ...patch }));
  }
  function override(id: string, patch: { injured?: boolean; protected?: boolean }) {
    edit({
      player_overrides: {
        ...preferences.player_overrides,
        [id]: { ...preferences.player_overrides?.[id], ...patch },
      },
    });
  }
  const user = snapshot.teams.find((team) => team.id === snapshot.selected_team_id);
  const opponent = snapshot.teams.find((team) => team.id === snapshot.opponent_team_id);
  const candidates = eligibleCandidates(snapshot);
  const relevant = [...(user?.roster ?? []), ...candidates];
  const players = Object.fromEntries(
    [...snapshot.teams.flatMap((team) => team.roster), ...snapshot.free_agents].map((player) => [
      player.id,
      player,
    ]),
  );
  const selectedCategories = preferences.selected_categories ?? plan?.selected_categories ?? [];
  const filters = { ...DEFAULT_PICKUP_FILTERS, ...preferences.pickup_filters };
  const moves = plan?.recommended_plan?.moves ?? [];
  const samples = Object.fromEntries(
    moves.map((move) => [
      move.add_id,
      {
        minutes:
          move.pickup_sample?.minutes ?? players[move.add_id]?.pickup_sample?.minutes ?? null,
        games: move.pickup_sample?.games ?? players[move.add_id]?.pickup_sample?.games ?? null,
        teamGames:
          move.pickup_sample?.team_games ?? players[move.add_id]?.pickup_sample?.team_games ?? null,
      },
    ]),
  );
  const espnLimit =
    snapshot.league.acquisition_settings.matchup_add_limit ??
    snapshot.league.acquisition_settings.weekly_add_limit;
  const budget = plan?.acquisition_budget
    ? plan.acquisition_budget.remaining
    : plan?.recommended_plan
      ? plan.recommended_plan.budget_before
      : user?.remaining_adds;
  const remainingAddsLabel =
    budget != null
      ? `${budget} adds left`
      : snapshot.league.acquisition_settings.unlimited
        ? "Matchup uncapped · adds unverified"
        : "Adds unverified";
  const search = plan?.search;
  const stop: WorkspaceStop | undefined = (() => {
    if (search?.phase === "paused") return "paused";
    if (search?.phase === "searching") return "searching";
    if (search?.phase === "cancelled") return "cancelled";
    if (plan?.evaluation_state === "no_qualified_pickups") return "empty_qualified_pool";
    if (plan?.evaluation_state === "required_inputs_unknown" || plan?.status === "unavailable")
      return "required_data_missing";
    if (
      search?.stop_reason === "unknown_budget" ||
      plan?.evaluation_state === "conditional_opportunities"
    )
      return "unknown_budget";
    if (search?.stop_reason === "no_remaining_dates") return "no_remaining_dates";
    if (plan?.evaluation_state === "known_zero_acquisitions") return "budget_exhausted";
    if (plan?.status === "ready" && !moves.length && (plan.outcome_policy?.rejected_plans ?? 0) > 0)
      return search?.phase === "finished"
        ? snapshot.market_complete === true
          ? "finished_guard"
          : "partial_guard"
        : "category_outcome_guard";
    if (search?.phase === "finished")
      return snapshot.market_complete !== true ? "partial_market" : "finished_scoped";
    if (search?.selected_plan_stop_reason === "acquisition_budget_used") return "budget_exhausted";
    if (
      search?.evaluation_limit_reached ||
      search?.layer_pruned ||
      search?.beam_pruned ||
      search?.candidate_truncated ||
      plan?.evaluation_state === "search_incomplete"
    )
      return "search_limit";
    return plan ? "no_positive_continuation" : undefined;
  })();
  const problem =
    !onPlan ||
    leagueError ||
    error ||
    !snapshot.league.supported ||
    plan?.status === "unavailable" ||
    plan?.evaluation_state === "required_inputs_unknown";
  function controls(rows: typeof relevant) {
    return rows.map((player) => {
      const out =
        preferences.player_overrides?.[player.id]?.injured ??
        (player.health_status
          ? player.health_status === "out"
          : ["OUT", "O", "INJURY_RESERVE", "SUSPENSION", "RESERVE_RETIRED"].includes(
              player.injury_status ?? "",
            ));
      const hardProtected =
        player.undroppable === true || player.droppable === false || player.locked === true;
      const protectedPlayer =
        preferences.player_overrides?.[player.id]?.protected ??
        (hardProtected || Boolean(plan?.protected_players?.[player.id]));
      return (
        <div className="player-control" key={player.id}>
          <div>
            <b>{player.name}</b>
            <small>
              {player.current_rates?.minutes == null
                ? "Minutes unavailable"
                : `${player.current_rates.minutes.toFixed(1)} MPG`}{" "}
              · {player.remaining_games ?? "?"} games left{player.locked ? " · Locked" : ""}
              {plan?.protected_players?.[player.id]
                ? ` · ${plan.protected_players[player.id]}`
                : hardProtected
                  ? " · Official ESPN restriction"
                  : ""}
            </small>
          </div>
          <div className="player-switches">
            <button
              type="button"
              className={out ? "availability-out" : "availability-in"}
              aria-label={`${player.name} availability: ${out ? "Out" : "Available"}`}
              aria-pressed={out}
              onClick={() => override(player.id, { injured: !out })}
            >
              {out ? "Out" : "Available"}
            </button>
            {user?.roster.some((row) => row.id === player.id) && (
              <button
                type="button"
                aria-label={`Protect ${player.name}`}
                aria-pressed={protectedPlayer}
                disabled={hardProtected}
                onClick={() => override(player.id, { protected: !protectedPlayer })}
              >
                {protectedPlayer ? "◆ Protected" : "◇ Protect"}
              </button>
            )}
          </div>
        </div>
      );
    });
  }
  return (
    <WaiverWorkspace
      generation={
        search?.job_id && search.publication != null
          ? `${search.job_id}:${search.publication}`
          : undefined
      }
      sequenceImpact={plan?.recommended_plan?.realized_impact}
      matchup={`${user?.name ?? "Your team"} vs ${opponent?.name ?? "Opponent unverified"}`}
      remainingAddsLabel={remainingAddsLabel}
      refreshedLabel={`Updated ${new Date(snapshot.fetched_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
      updating={loading || busy}
      searching={search?.phase === "searching"}
      onCancelSearch={cancelSearch}
      readOnly={lifecycle.readOnly}
      resultState={lifecycle.state}
      onRefresh={onRefresh}
      status={
        problem
          ? {
              actionHref:
                lifecycle.state === "reconnect-needed"
                  ? "/fantasy?fantasyTab=dashboard"
                  : undefined,
              text:
                lifecycle.state === "reconnect-needed"
                  ? "Reconnect ESPN to build a plan"
                  : lifecycle.state === "stale"
                    ? "Showing saved plan · refresh needed"
                    : "Plan needs updated data",
              actionLabel: lifecycle.state === "reconnect-needed" ? "Reconnect" : "Retry",
              onAction: () => {
                onRefresh?.();
                setAttempt((value) => value + 1);
              },
            }
          : undefined
      }
      targets={selectedCategories}
      strategy={plan?.strategy}
      onTargetsChange={(categories) => edit({ selected_categories: categories })}
      filters={filters}
      onFiltersChange={(pickup_filters) => edit({ pickup_filters })}
      moves={moves}
      players={players}
      samples={samples}
      forecast={matchupForecastData(plan)}
      baseline={plan?.baseline}
      projected={plan?.projected}
      scheduleCounts={moves.map((move) => ({
        addRemainingGames: move.schedule_explanations?.add.remaining_games ?? null,
        dropRemainingGames: move.schedule_explanations?.drop.remaining_games ?? null,
      }))}
      stop={stop}
      rosterControls={
        <details className="ww-control">
          <summary>Roster settings</summary>
          <div className="ww-roster-settings">
            <label>
              <input
                type="checkbox"
                checked={preferences.allow_core_drops ?? false}
                onChange={(event) => edit({ allow_core_drops: event.target.checked })}
              />{" "}
              Allow core-player drops
            </label>
            <InfoTooltip label="About roster protection">
              Official locks and your Protect choices remain enforced. Availability defaults to
              available unless reported out.
            </InfoTooltip>
            {controls(relevant)}
          </div>
        </details>
      }
      analysis={
        <>
          <p>
            {leagueError ??
              error ??
              snapshot.league.unsupported_reason ??
              (!onPlan ? "Optimizer integration is unavailable." : null)}
          </p>
          <ActualSources teams={[user, opponent]} />
          <h3>Category outlook · all nine</h3>
          <div className="league-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>You</th>
                  <th>Opponent</th>
                  <th>Outlook</th>
                </tr>
              </thead>
              <tbody>
                {LEAGUE_CATEGORIES.map(({ key, label }) => (
                  <tr key={key}>
                    <th>{label}</th>
                    <td>{formatCategory(plan?.strategy?.[key]?.projected_user ?? null, key)}</td>
                    <td>
                      {formatCategory(plan?.strategy?.[key]?.projected_opponent ?? null, key)}
                    </td>
                    <td>{plan?.strategy?.[key]?.explanation ?? "Unknown"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {plan?.recommended_plan?.arithmetic && (
            <OverallPlanImpact arithmetic={plan.recommended_plan.arithmetic} />
          )}
          <h3>Pickup qualification</h3>
          {plan?.pickup_filter_summary && (
            <>
              <p>
                {plan.pickup_filter_summary.qualified} of {plan.pickup_filter_summary.requested}{" "}
                current samples qualify
              </p>
              <ul>
                {plan.pickup_filter_summary.exclusions.map((row) => (
                  <li key={row.player_id}>
                    {row.name}: {row.reasons.join(", ")}
                  </li>
                ))}
              </ul>
            </>
          )}
          <h3>Search & source diagnostics</h3>
          <pre className="ww-diagnostics">
            {JSON.stringify(
              {
                search: plan?.search,
                outcome_policy: plan?.outcome_policy,
                filters: plan?.pickup_filter_summary,
                market: snapshot.market_coverage,
                acquisition_budget: plan?.acquisition_budget,
                projection: snapshot.projection_metadata,
              },
              null,
              2,
            )}
          </pre>
          <details>
            <summary>
              Competing single-move alternatives ({plan?.recommendations?.length ?? 0})
            </summary>
            {plan?.recommendations?.map((move, index) => (
              <section key={index}>
                <h4>
                  {players[move.add_id]?.name} / {players[move.drop_id]?.name}
                </h4>
                <WaiverArithmetic
                  move={move}
                  addPlayer={players[move.add_id]}
                  dropPlayer={players[move.drop_id]}
                />
              </section>
            ))}
          </details>
        </>
      }
      technicalControls={
        <details className="waiver-advanced" ref={advancedPanel}>
          <summary>Advanced inputs & data notes</summary>
          <p>
            Only override acquisition counts with verified matchup values. Unknown usage is never
            treated as zero.
          </p>
          {espnLimit == null && preferences.matchup_add_limit_fallback == null && (
            <button
              type="button"
              onClick={() => {
                try {
                  localStorage.setItem(capStorageKey, "7");
                } catch {
                  /* Memory preference remains usable. */
                }
                edit({ matchup_add_limit_fallback: 7 });
              }}
            >
              Save my confirmed cap of 7 for this league
            </button>
          )}
          <label>
            My league’s matchup cap fallback (used only if ESPN cap is unavailable)
            <input
              type="number"
              min="0"
              step="1"
              value={preferences.matchup_add_limit_fallback ?? ""}
              placeholder="7 — your confirmed league cap"
              onChange={(event) => {
                const cap = event.target.value === "" ? null : Number(event.target.value);
                if (cap != null && (!Number.isInteger(cap) || cap < 0)) return;
                try {
                  if (cap == null) localStorage.removeItem(capStorageKey);
                  else localStorage.setItem(capStorageKey, String(cap));
                } catch {
                  /* Preferences remain usable without storage. */
                }
                edit({ matchup_add_limit_fallback: cap });
              }}
            />
          </label>
          <p>
            This setting is saved only for {snapshot.league.name}, season{" "}
            {snapshot.league.season_id}. It never replaces unknown acquisition usage.
          </p>
          <div className="league-fields">
            {(
              [
                ["weekly_add_limit", "Matchup acquisition cap"],
                ["used_adds", "Matchup acquisitions used"],
                ["available_adds", "Adds remaining"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={preferences[key] ?? ""}
                  onChange={(event) =>
                    edit({ [key]: event.target.value === "" ? null : Number(event.target.value) })
                  }
                />
              </label>
            ))}
          </div>
          <label className="league-check">
            <input
              type="checkbox"
              checked={preferences.user_confirmed_counts ?? false}
              onChange={(event) =>
                edit({
                  user_confirmed_counts: event.target.checked,
                  counts_snapshot_at: event.target.checked ? snapshot.fetched_at : undefined,
                  usage_declaration:
                    event.target.checked && preferences.used_adds != null
                      ? bindUsage(snapshot, preferences.used_adds, new Date().toISOString())
                      : undefined,
                })
              }
            />
            Use my verified matchup counts
          </label>
          <p>
            Current-season per-game rates and remaining lineup opportunity drive estimates. Prior
            season is fallback when the current sample is too small. Extra turnovers can hurt;
            shooting percentages use makes and attempts.
          </p>
          {snapshot.market_coverage && (
            <p className={snapshot.market_complete ? "search-summary" : "league-tied"}>
              Market coverage: {snapshot.market_coverage.observed} observed of{" "}
              {snapshot.market_coverage.provider_total ?? "unknown total"} ·{" "}
              {snapshot.market_complete ? "provider exhaustion observed" : "partial / unverified"} ·
              bound {snapshot.market_coverage.limit ?? "unknown"} players · fetched{" "}
              {snapshot.market_coverage.fetched_at ?? "time unavailable"}. Market coverage qualifies
              search, independently of matchup scoring completeness.
            </p>
          )}
          {snapshot.free_agents_truncated && (
            <p>
              The returned free-agent pool is limited; these are the best supported alternatives
              within that pool.
            </p>
          )}
          {plan && (
            <>
              <p>
                Uncertainty source: {plan.uncertainty?.source ?? "Unavailable"} · uncalibrated
                estimates, not guarantees.
              </p>
              <ul>
                {[...plan.assumptions, ...plan.limitations, ...plan.reasons].map((item, index) => (
                  <li key={`${index}:${item}`}>{item}</li>
                ))}
              </ul>
              <DataGaps gaps={plan.data_gaps} />
            </>
          )}
          <DataGaps gaps={snapshot.data_gaps} />
          {!!snapshot.modeling_notes?.length && (
            <details>
              <summary>Model scope & provider notes</summary>
              <ul>
                {snapshot.modeling_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </details>
          )}
        </details>
      }
    />
  );
}

export function LeagueDashboardSummary({ state }: { state: LeagueFantasyState }) {
  const team = state.snapshot?.teams.find((team) => team.id === state.snapshot?.selected_team_id);
  const opponent = state.snapshot?.teams.find(
    (team) => team.id === state.snapshot?.opponent_team_id,
  );
  return (
    <div className="league-dashboard">
      <LeagueConnection state={state} />
      {state.snapshot && (
        <section className="league-panel">
          <SnapshotHeading
            snapshot={state.snapshot}
            loading={state.loading}
            onRefresh={() => void state.refresh()}
          />
          <h2>{team?.name ?? "Your league"}</h2>
          <p>Current opponent: {opponent?.name ?? "Unavailable"}</p>
          <p>
            {team?.remaining_adds ?? "Unknown"} matchup acquisitions remaining ·{" "}
            {state.snapshot.period.remaining_dates.length} remaining dates reported.
          </p>
          <p>
            Open Matchups to compare category totals; use Waiver Wire to create a recommendation
            plan.
          </p>
          <DataGaps gaps={state.snapshot.data_gaps} />
        </section>
      )}
    </div>
  );
}
