import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { leagueFantasyApi, type LeagueFantasyApi } from "./league-fantasy-api";
import {
  LEAGUE_CATEGORIES,
  DEFAULT_ESPN_LEAGUE_ID,
  DEFAULT_ESPN_SEASON_ID,
  categoryValue,
  compareCategory,
  eligibleCandidates,
  formatCategory,
  type ConnectLeague,
  type Category,
  type LeagueSnapshot,
  type LeagueStatus,
  type LeagueTeam,
  type PlannerPreferences,
  type PlanForecast,
  type WaiverPlan,
} from "./league-fantasy-model";
import "./league-fantasy.css";
import { ActualSources } from "./ActualSources";
import { OverallPlanImpact, WaiverArithmetic } from "./WaiverArithmetic";
import { EspnBrowserConnect } from "./EspnBrowserConnect";

/** Mount once in the integrating app; pass the returned state to the named components. */
export function useLeagueFantasy(api: LeagueFantasyApi = leagueFantasyApi) {
  const [status, setStatus] = useState<LeagueStatus>({ connected: false });
  const [snapshot, setSnapshot] = useState<LeagueSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const revision = useRef(0);
  const run = useCallback(
    async (action: () => Promise<LeagueStatus | LeagueSnapshot>, connection = false) => {
      const current = ++revision.current;
      setLoading(true);
      setError(null);
      if (connection) setSnapshot(null);
      try {
        const result = await action();
        if (current !== revision.current) return;
        if ("connected" in result) {
          setStatus(result);
          if (!result.connected) setSnapshot(null);
        } else setSnapshot(result);
      } catch {
        if (current === revision.current)
          setError(
            "League data could not be loaded. Check your connection and retry; displayed totals may be older.",
          );
      } finally {
        if (current === revision.current) setLoading(false);
      }
    },
    [],
  );
  useEffect(() => {
    void run(() => api.status(), true);
    return () => {
      revision.current++;
    };
  }, [api, run]);
  useEffect(() => {
    if (status.connected && status.team_id) void run(() => api.snapshot());
  }, [api, status, run]);
  const refreshStatus = useCallback(() => run(() => api.status()), [api, run]);
  useEffect(() => {
    const changed = () => void refreshStatus();
    window.addEventListener("nba-espn-bridge", changed);
    const timer = window.setInterval(() => {
      if (status.connected && status.expires_at && Date.parse(status.expires_at) <= Date.now())
        void refreshStatus();
    }, 30000);
    return () => {
      window.removeEventListener("nba-espn-bridge", changed);
      window.clearInterval(timer);
    };
  }, [refreshStatus, status.connected, status.expires_at]);
  return {
    status,
    snapshot,
    loading,
    error,
    connect: (input: ConnectLeague) => run(() => api.connect(input), true),
    selectTeam: (id: number) => run(() => api.selectTeam(id), true),
    disconnect: () => run(() => api.disconnect(), true),
    refresh: () => run(() => api.snapshot({ refresh: true })),
    refreshStatus,
  };
}
export type LeagueFantasyState = Omit<ReturnType<typeof useLeagueFantasy>, "refreshStatus"> & {
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
              disabled={state.loading}
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
    try {
      const saved = localStorage.getItem(capStorageKey);
      const cap = saved === null ? null : Number(saved);
      return cap != null && Number.isInteger(cap) && cap >= 0
        ? { matchup_add_limit_fallback: cap }
        : {};
    } catch {
      return {};
    }
  });
  const [categoryDraft, setCategoryDraft] = useState<Category[] | null>(null);
  const availabilityPanel = useRef<HTMLDetailsElement>(null);
  const [plan, setPlan] = useState<WaiverPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [dropFilter, setDropFilter] = useState("");
  const [visibleCount, setVisibleCount] = useState(12);
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    setPlan(null);
    setError(null);
    if (!onPlan || !snapshot.league.supported) {
      setBusy(false);
      return;
    }
    setBusy(true);
    void onPlan({
      ...preferences,
      context: {
        league_id: snapshot.league.id,
        team_id: snapshot.selected_team_id,
        matchup_period_id: snapshot.period.matchup_period_id,
        fetched_at: snapshot.fetched_at,
      },
    })
      .then((result) => {
        if (current === generation.current) setPlan(result);
      })
      .catch(() => {
        if (current === generation.current)
          setError("Analysis could not be loaded. Retry after checking your league connection.");
      })
      .finally(() => {
        if (current === generation.current) setBusy(false);
      });
    return () => {
      generation.current++;
    };
  }, [snapshot, preferences, onPlan, attempt]);
  function edit(patch: Partial<PlannerPreferences>) {
    generation.current++;
    setPlan(null);
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
  const players = new Map(
    [...snapshot.teams.flatMap((team) => team.roster), ...candidates].map((player) => [
      player.id,
      player,
    ]),
  );
  const recommendations = plan?.recommendations ?? [];
  const filteredRecommendations = recommendations.filter(
    (item) => !dropFilter || item.drop_id === dropFilter,
  );
  const visibleRecommendations = filteredRecommendations.slice(0, visibleCount);
  const dropIds = [...new Set(recommendations.map((item) => item.drop_id))];
  const actions = plan?.plan ?? plan?.actions ?? [];
  const recommendedTargets = [
    ...new Set(recommendations.flatMap((item) => item.target_categories)),
  ];
  const strategyTargets = LEAGUE_CATEGORIES.filter(({ key }) =>
    ["favored", "swing", "reachable", "trailing"].includes(
      plan?.strategy?.[key]?.classification ?? "",
    ),
  )
    .sort(
      (a, b) =>
        (plan?.strategy?.[b.key]?.target_priority ?? 0) -
        (plan?.strategy?.[a.key]?.target_priority ?? 0),
    )
    .map(({ key }) => key);
  const targetCategories = plan?.improvement_categories ?? [
    ...new Set([...recommendedTargets, ...strategyTargets]),
  ];
  const selectedCategories = preferences.selected_categories ?? plan?.selected_categories ?? [];
  const requiredMetadata = snapshot.projection_metadata;
  const confidenceComplete =
    plan?.status === "ready" &&
    [user, opponent].every(
      (team) =>
        !team?.actuals ||
        (team.actuals.forecast_complete &&
          !Object.values(team.actuals.discrepancy ?? {}).some(
            (value) => value != null && Math.abs(value) > 1e-9,
          )),
    ) &&
    (requiredMetadata
      ? Object.values(requiredMetadata).length > 0 &&
        Object.values(requiredMetadata).every((part) => part.complete)
      : plan.data_gaps.length === 0);
  const safeCategories = confidenceComplete
    ? (plan?.safe_categories ?? []).filter((key) => selectedCategories.includes(key))
    : [];
  const categoryLabels = (keys: Category[]) =>
    keys
      .map((key) => LEAGUE_CATEGORIES.find((category) => category.key === key)?.label ?? key)
      .join(" · ");
  const targetKeys = targetCategories.map(
    (key) => LEAGUE_CATEGORIES.find((category) => category.key === key)?.label ?? key,
  );
  const relevantIds = new Set(recommendations.map((item) => item.add_id));
  const relevant = [
    ...(user?.roster ?? []),
    ...candidates.filter((player) => relevantIds.has(player.id)),
  ];
  const settings = snapshot.league.acquisition_settings;
  const espnLimit =
    settings.matchup_add_limit ??
    (settings.limit_per_scoring_period === false ? settings.weekly_add_limit : null);
  const knownLimit = espnLimit ?? preferences.matchup_add_limit_fallback;
  const capSource =
    settings.cap_source === "league_fallback_7"
      ? "League fallback cap (7); ESPN cap unavailable"
      : espnLimit != null
        ? "ESPN matchup cap"
        : preferences.matchup_add_limit_fallback != null
          ? "Your saved league cap fallback"
          : "Cap unavailable";
  const signed = (
    value: number | null | undefined,
    key?: (typeof LEAGUE_CATEGORIES)[number]["key"],
  ) =>
    value == null
      ? "Unavailable"
      : `${value > 0 ? "+" : ""}${key?.endsWith("pct") ? `${(value * 100).toFixed(2)} pp` : value.toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
  function netCategoryGain(
    item: (typeof recommendations)[number],
    key: (typeof LEAGUE_CATEGORIES)[number]["key"],
  ) {
    const impact = item.category_impacts?.[key];
    return key.endsWith("pct") && impact?.before != null && impact.after != null
      ? impact.after - impact.before
      : item.gains[key];
  }
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
    <section className="league-panel league-waiver">
      <SnapshotHeading snapshot={snapshot} loading={loading} onRefresh={onRefresh} />
      <div className="waiver-verdict">
        <div>
          <span className="league-kicker">YOUR PATH TO FIVE CATEGORIES</span>
          <h2>
            {busy
              ? "Finding your matchup edge…"
              : targetKeys.length
                ? `Focus on ${targetKeys.join(" · ")}`
                : "Your matchup strategy"}
          </h2>
          <p>
            Against {opponent?.name ?? "opponent unavailable"}. Compare the net benefit of a pickup
            after the player you drop. Only future playable starts count; recorded stats stay
            banked.
          </p>
          <p className="matchup-horizon">
            {snapshot.period.remaining_dates.length} remaining matchup dates · through{" "}
            {snapshot.period.end_date ?? snapshot.period.dates.at(-1) ?? "unknown end date"}
          </p>
        </div>
        <div className="waiver-budget">
          <b>
            {plan?.remaining_adds != null
              ? plan.remaining_adds + actions.length
              : (user?.remaining_adds ?? "?")}
          </b>
          <span>matchup acquisitions left</span>
          <small>
            {knownLimit ?? "Unknown"} cap · {user?.weekly_used_adds ?? "Unknown"} used
          </small>
          <small>{capSource}</small>
          <small>
            {user?.weekly_usage_source ? "ESPN matchup usage" : "Usage source unavailable"}
          </small>
        </div>
      </div>
      {leagueError && <p role="alert">{leagueError}</p>}
      {!snapshot.league.supported && (
        <p role="alert">
          {snapshot.league.unsupported_reason ?? "This league format is unsupported."}
        </p>
      )}
      {busy && <p role="status">Analyzing current rates, remaining games and your opponent…</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Retry analysis
          </button>
        </div>
      )}
      {!onPlan && (
        <p role="status">
          Optimizer integration is unavailable. Current category totals remain visible.
        </p>
      )}
      {plan?.strategy && (
        <p className="five-category-path">
          <b>{confidenceComplete ? safeCategories.length : "Unverified"} modeled cushions</b>.{" "}
          {targetKeys.length
            ? `Improve ${targetKeys.join(" / ")}; modeled cushions count toward five.`
            : "Review the outlook before using an add."}
        </p>
      )}
      <ActualSources teams={[user, opponent]} />
      <section className="five-selection" aria-label="Five-category strategy">
        <p>
          <b>Selected five:</b>{" "}
          {selectedCategories.length
            ? categoryLabels(selectedCategories)
            : "Awaiting strategy analysis"}
        </p>
        <p>
          <span className="league-winning">
            Modeled cushions: {categoryLabels(safeCategories) || "None established"}
          </span>{" "}
          · Improvement priorities: {categoryLabels(targetCategories) || "None supported"}
        </p>
        <small>
          Modeled cushions count toward five; they are not guaranteed wins. Focus scores are
          heuristics on a 0–100 scale, never matchup win probabilities. Weights affect strategy
          only; raw category totals decide wins.
        </small>
        <details>
          <summary>Edit selected five categories</summary>
          <fieldset className="category-picker">
            <legend>Choose exactly five categories</legend>
            {LEAGUE_CATEGORIES.map(({ key, label }) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={(categoryDraft ?? selectedCategories).includes(key)}
                  onChange={(event) => {
                    const current = categoryDraft ?? selectedCategories;
                    setCategoryDraft(
                      event.target.checked
                        ? [...current, key]
                        : current.filter((item) => item !== key),
                    );
                  }}
                />
                {label}
              </label>
            ))}
          </fieldset>
          <button
            type="button"
            disabled={(categoryDraft ?? selectedCategories).length !== 5}
            onClick={() => {
              edit({ selected_categories: categoryDraft ?? selectedCategories });
            }}
          >
            Recalculate selected five
          </button>
          <button
            type="button"
            onClick={() => {
              setCategoryDraft(null);
              edit({ selected_categories: undefined });
            }}
          >
            Use recommended five
          </button>
        </details>
      </section>
      <p className="availability-assumption">
        Availability: assume Available unless explicitly reported Out.{" "}
        <button
          type="button"
          onClick={() => {
            if (availabilityPanel.current) {
              availabilityPanel.current.open = true;
              availabilityPanel.current.scrollIntoView?.({ block: "start" });
            }
          }}
        >
          Edit player availability
        </button>
      </p>
      <div className="strategy-legend">
        <span className="league-winning">● Modeled cushion: retain</span>
        <span className="league-tied">◆ Close / vulnerable: improve</span>
        <span className="league-losing">↓ Trailing: lower priority</span>
        <span>— Unknown: missing evidence</span>
      </div>
      {snapshot.projection_metadata?.matchup_calendar?.complete === false && (
        <p className="league-tied" role="status">
          Matchup calendar unverified: ESPN scoring-date anchor is missing or conflicting. Official
          banked totals remain visible, but future matchup dates cannot support confirmed plans or
          cushion labels.
        </p>
      )}
      {!confidenceComplete && (
        <p className="league-tied">
          Outlook unverified: required roster, rates, schedules or historical active scoring lineups
          are incomplete. No safe or favored claims are supported.
        </p>
      )}
      <div className="category-strategy-grid" aria-label="Category opportunities">
        {LEAGUE_CATEGORIES.map(({ key, label }) => {
          const strategy = plan?.strategy?.[key];
          const own = strategy?.projected_user ?? null;
          const other = strategy?.projected_opponent ?? null;
          const state = compareCategory(own, other, key);
          const share =
            own != null && other != null && own + other > 0
              ? Math.max(0, Math.min(100, (own / (own + other)) * 100))
              : null;
          return (
            <article
              className={`strategy-category strategy-${confidenceComplete ? (strategy?.classification ?? "unknown") : "unknown"}`}
              key={key}
            >
              <header>
                <b>{label}</b>
                <span>
                  {!confidenceComplete
                    ? "Unverified"
                    : strategy?.safe_win
                      ? "Modeled cushion"
                      : strategy?.classification === "favored"
                        ? "Favored · strengthen"
                        : strategy?.classification === "punt"
                          ? "Trailing"
                          : (strategy?.classification ?? "Awaiting analysis")}
                </span>
              </header>
              <small>
                {selectedCategories.includes(key) ? "Selected five" : "Reserve"} · Current →
                projected final
              </small>
              <div className="forecast-equation">
                <ForecastEquation
                  forecast={plan?.baseline}
                  side="user"
                  category={key}
                  current={strategy?.current_user}
                  final={own}
                />
                <ForecastEquation
                  forecast={plan?.baseline}
                  side="opponent"
                  category={key}
                  current={strategy?.current_opponent}
                  final={other}
                />
              </div>
              <div className="strategy-actuals">
                <strong className={`league-${state}`}>{formatCategory(own, key)}</strong>
                <span>vs {formatCategory(other, key)}</span>
              </div>
              <div className="category-gap-bar" aria-hidden="true">
                {share != null && <span style={{ width: `${share}%` }} />}
              </div>
              <small>Projected final · {key === "to" ? "fewer wins" : "higher wins"}</small>
              <p>
                {confidenceComplete
                  ? (strategy?.explanation.split(". ")[0] ?? "Forecast evidence is unavailable.")
                  : "Confidence withheld until required inputs and scoring-source agreement are verified."}
              </p>
              {strategy && (
                <small>
                  Projected gap {signed(strategy.projected_margin, key)}
                  <br />
                  Prior-week gap {signed(strategy.historical_margin, key)}
                  <br />
                  Last week {formatCategory(strategy.previous_user ?? null, key)} vs{" "}
                  {formatCategory(strategy.previous_opponent ?? null, key)}
                  {strategy.best_pickup_margin != null && (
                    <>
                      <br />
                      Best pickup gap {signed(strategy.best_pickup_margin, key)}
                      {strategy.can_flip_with_one_move ? " · flips lead" : ""}
                    </>
                  )}
                </small>
              )}
            </article>
          );
        })}
      </div>
      <details className="category-overview">
        <summary>
          All nine categories ·{" "}
          {LEAGUE_CATEGORIES.filter(
            ({ key }) =>
              confidenceComplete &&
              selectedCategories.includes(key) &&
              plan?.strategy?.[key]?.safe_win,
          )
            .map(({ label }) => label)
            .join(" · ") || "No projected cushions"}
        </summary>
        <div className="league-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Outlook</th>
                <th>This week: you / opponent</th>
                <th>Last week: you / opponent</th>
                <th>Projected / prior gap</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {LEAGUE_CATEGORIES.map(({ key, label }) => (
                <tr key={key}>
                  <th>{label}</th>
                  <td>
                    {confidenceComplete
                      ? (plan?.strategy?.[key]?.classification ?? "Unknown")
                      : "Unverified"}
                  </td>
                  <td>
                    {formatCategory(categoryValue(user?.totals ?? null, key), key)} /{" "}
                    {formatCategory(categoryValue(opponent?.totals ?? null, key), key)}
                  </td>
                  <td>
                    {formatCategory(plan?.strategy?.[key]?.previous_user ?? null, key)} /{" "}
                    {formatCategory(plan?.strategy?.[key]?.previous_opponent ?? null, key)}
                  </td>
                  <td>
                    {signed(plan?.strategy?.[key]?.projected_margin, key)} /{" "}
                    {signed(plan?.strategy?.[key]?.historical_margin, key)}
                  </td>
                  <td>
                    {confidenceComplete
                      ? (plan?.strategy?.[key]?.explanation ?? "Evidence unavailable")
                      : "Confidence withheld: required inputs or scoring agreement unverified"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <section className="recommended-sequence" aria-label="Recommended ordered plan">
        <span className="league-kicker">ONE COHERENT MATCHUP PLAN</span>
        <h3>Best explored add/drop sequence</h3>
        <p>
          Each step reprojects the whole roster after prior moves. Transactions remain manual in
          ESPN. Bounded search does not prove a globally optimal plan.
        </p>
        {plan?.recommended_plan?.moves.length ? (
          <>
            <p className="focus-score">
              Focus score: {(plan.recommended_plan.score_before * 100).toFixed(1)} →{" "}
              {(plan.recommended_plan.focus_score_after * 100).toFixed(1)} / 100 · heuristic, not
              win probability
            </p>
            <p>
              Soft season-value cost: {(plan.recommended_plan.season_cost * 100).toFixed(2)} score
              points · net strategic score gain:{" "}
              {(plan.recommended_plan.net_score_gain * 100).toFixed(2)}.{" "}
              {plan.recommended_plan.viable_five
                ? "All five selected categories remain modeled viable."
                : "The selected five remain a difficult route; no five-win guarantee."}
            </p>
            <OverallPlanImpact arithmetic={plan.recommended_plan.arithmetic} />
            <ol className="pickup-list">
              {plan.recommended_plan.moves.map((move, index) => (
                <li key={`${index}:${move.add_id}:${move.drop_id}`}>
                  <div className="pickup-rank">{index + 1}</div>
                  <div className="pickup-body">
                    <h4>
                      <span className="league-winning">
                        Add {players.get(move.add_id)?.name ?? move.add_id}
                      </span>{" "}
                      →{" "}
                      <span className="league-losing">
                        drop {players.get(move.drop_id)?.name ?? move.drop_id}
                      </span>
                    </h4>
                    <p>
                      Effective {move.date} ·{" "}
                      {plan.recommended_plan?.budget_before == null
                        ? "Unknown"
                        : plan.recommended_plan.budget_before - index - 1}{" "}
                      acquisitions left · cumulative focus score{" "}
                      {move.score_after == null ? "Unknown" : (move.score_after * 100).toFixed(1)} /
                      100
                    </p>
                    <WaiverArithmetic
                      move={move}
                      addPlayer={players.get(move.add_id)}
                      dropPlayer={players.get(move.drop_id)}
                    />
                  </div>
                </li>
              ))}
            </ol>
          </>
        ) : (
          !busy && (
            <div className="strategy-empty">
              <h4>
                {plan?.remaining_adds === 0
                  ? "No acquisition budget remaining"
                  : plan?.status === "incomplete"
                    ? "Plan unavailable: required inputs incomplete"
                    : "No supported beneficial sequence"}
              </h4>
              <p>
                {plan?.reasons.join(" ") ||
                  "Waiting for a verified ordered plan; competing alternatives do not establish an executable sequence."}
              </p>
            </div>
          )
        )}
      </section>
      <details className="secondary-alternatives">
        <summary>Optional competing single-move alternatives ({recommendations.length})</summary>
        <section className="pickup-section" aria-label="Ranked pickup alternatives">
          <div className="strategy-section-heading">
            <div>
              <span className="league-kicker">SECONDARY OPTIONS</span>
              <h3>Best pickup + drop alternatives</h3>
            </div>
            <span>{recommendations.length} beneficial alternatives</span>
          </div>
          <p>
            Each option is compared with keeping your roster over the remaining matchup. Ranked
            alternatives may share a pickup or drop and cannot be combined into a sequence.
            Transactions remain manual in ESPN.
          </p>
          {plan && plan.remaining_adds == null && (
            <p className="league-tied">
              Conditional alternatives: acquisition limits or usage are not fully verified. Check
              your remaining budget in ESPN before choosing a move.
            </p>
          )}
          {plan?.search && (
            <p
              className={
                plan.search.alternatives_complete === false ? "league-tied" : "search-summary"
              }
            >
              {plan.search.alternatives_complete === false
                ? "Search incomplete: some beneficial alternatives may be omitted. "
                : "Explored one-move pairs and timing; lineup forecasts are approximate. "}
              {plan.search.evaluated_drop_ids?.length ?? "?"} of{" "}
              {plan.search.legal_drop_ids?.length ?? "?"} legal roster drops evaluated ·{" "}
              {plan.search.evaluations} evaluations · {plan.search.candidate_pool ?? "?"}{" "}
              candidates.
              {plan.search.alternatives_complete === false && (
                <>
                  {" "}
                  Bounds: {plan.search.candidate_limit ?? "unknown"} candidates /{" "}
                  {plan.search.evaluation_limit ?? "unknown"} evaluations.
                </>
              )}
            </p>
          )}
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
            <p className="league-tied">
              ESPN returned a limited free-agent pool. Results cover that pool only.
            </p>
          )}
          {recommendations.length > 0 && (
            <label className="pickup-filter">
              Review by roster drop
              <select
                value={dropFilter}
                onChange={(event) => {
                  setDropFilter(event.target.value);
                  setVisibleCount(12);
                }}
              >
                <option value="">All drop options ({dropIds.length})</option>
                {dropIds.map((id) => (
                  <option key={id} value={id}>
                    {players.get(id)?.name ?? id}
                  </option>
                ))}
              </select>
            </label>
          )}
          {recommendations.length > 0 ? (
            <ol className="pickup-list">
              {visibleRecommendations.map((item, index) => (
                <li key={`${item.add_id}:${item.drop_id}`}>
                  <div className="pickup-rank">{index + 1}</div>
                  <div className="pickup-body">
                    <div className="pickup-pair">
                      <div>
                        <span className="league-winning">ADD</span>
                        <h4>{players.get(item.add_id)?.name ?? "Player unavailable"}</h4>
                      </div>
                      <span className="pickup-arrow">→</span>
                      <div>
                        <span className="league-losing">DROP</span>
                        <h4>{players.get(item.drop_id)?.name ?? "Player unavailable"}</h4>
                      </div>
                    </div>
                    <div className="pickup-tags">
                      <b>
                        Target{" "}
                        {item.target_categories
                          .map(
                            (key) =>
                              LEAGUE_CATEGORIES.find((category) => category.key === key)?.label ??
                              key,
                          )
                          .join(" · ") || "overall balance"}
                      </b>
                      <span>{signed(item.games_gain)} net playable starts</span>
                      <span>{signed(item.minutes_gain)} net minutes</span>
                      <span>1 add · {item.date}</span>
                    </div>
                    <div className="pickup-net pickup-target-gains">
                      {item.target_categories.map((key) => (
                        <span key={key}>
                          {LEAGUE_CATEGORIES.find((category) => category.key === key)?.label ?? key}{" "}
                          <b>{signed(netCategoryGain(item, key), key)} net total</b>
                        </span>
                      ))}
                    </div>
                    <div className="pickup-details">
                      <h5>Remaining matchup arithmetic & tradeoffs</h5>
                      <WaiverArithmetic
                        move={item}
                        addPlayer={players.get(item.add_id)}
                        dropPlayer={players.get(item.drop_id)}
                      />
                      <p>
                        {item.season_cost == null
                          ? "Long-term roster value is considered before this drop."
                          : item.season_cost > 0
                            ? "The remaining-matchup gain offsets an estimated long-term roster downgrade. Review this tradeoff before dropping."
                            : "No long-term downgrade is estimated by the season-value model."}{" "}
                        Any legally droppable player can be evaluated. Use Protect to keep a player
                        out of recommendations.
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            !busy && (
              <div className="strategy-empty">
                <h4>No supported pickup improvement yet</h4>
                <p>
                  {plan?.reasons.join(" ") ||
                    "The analysis needs usable current rates, remaining schedules and an eligible add/drop pair. No pickups have been invented."}
                </p>
              </div>
            )
          )}
          {filteredRecommendations.length > visibleRecommendations.length && (
            <button type="button" onClick={() => setVisibleCount((count) => count + 12)}>
              Show more alternatives ({visibleRecommendations.length} of{" "}
              {filteredRecommendations.length})
            </button>
          )}
        </section>
      </details>
      <section className="core-protection" aria-label="Core player protection">
        <h3>Core-player protection</h3>
        <p>
          Default protection keeps core players out of short-horizon drops. This heuristic uses
          available player value metadata; it is separate from immutable ESPN locks and your Protect
          choices.
        </p>
        <label>
          <input
            type="checkbox"
            checked={preferences.allow_core_drops ?? false}
            onChange={(event) => edit({ allow_core_drops: event.target.checked })}
          />{" "}
          Allow core-player drops for this analysis
        </label>
        <small>
          Override recalculates recommendations. ESPN locks, undroppable restrictions and explicit
          Protect choices remain enforced.
        </small>
      </section>
      <details ref={availabilityPanel} className="availability-controls">
        <summary>Edit availability & roster protection</summary>
        <p>
          Assume Available unless explicitly reported Out. Change a player below to recalculate
          immediately. Known locks, undroppable players and your explicit Protect choices are
          respected.
        </p>
        {controls(relevant)}
        <details>
          <summary>
            Other eligible free agents (
            {candidates.filter((player) => !relevantIds.has(player.id)).length})
          </summary>
          {controls(candidates.filter((player) => !relevantIds.has(player.id)))}
        </details>
      </details>
      <details className="waiver-advanced">
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
          This setting is saved only for {snapshot.league.name}, season {snapshot.league.season_id}.
          It never replaces unknown acquisition usage.
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
            onChange={(event) => edit({ user_confirmed_counts: event.target.checked })}
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
      </details>
    </section>
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

function ForecastEquation({
  forecast,
  side,
  category,
  current,
  final,
}: {
  forecast?: PlanForecast | null;
  side: "user" | "opponent";
  category: Category;
  current?: number | null;
  final: number | null;
}) {
  const actual = forecast?.actual_primitives?.[side];
  const remaining = forecast?.remaining_primitives?.[side];
  const finish = side === "user" ? forecast?.totals : forecast?.opponent_totals;
  const volume = (stats: typeof actual) =>
    category === "fg_pct"
      ? `${stats?.fgm ?? "?"}/${stats?.fga ?? "?"}`
      : `${stats?.ftm ?? "?"}/${stats?.fta ?? "?"}`;
  return (
    <span>
      {side === "user" ? "You" : "Opponent"}:{" "}
      {category.endsWith("pct") ? (
        <>
          {volume(actual)} + {volume(remaining)} remaining = {volume(finish)} ·{" "}
          <b>{formatCategory(final, category)}</b>
        </>
      ) : (
        <>
          {formatCategory(current ?? null, category)} +{" "}
          {formatCategory(
            categoryValue(remaining ?? null, category) ??
              (final != null && current != null ? final - current : null),
            category,
          )}{" "}
          remaining = <b>{formatCategory(final, category)}</b>
        </>
      )}
    </span>
  );
}
