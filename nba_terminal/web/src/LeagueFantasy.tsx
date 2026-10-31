import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { leagueFantasyApi, type LeagueFantasyApi } from "./league-fantasy-api";
import {
  LEAGUE_CATEGORIES,
  categoryValue,
  compareCategory,
  eligibleCandidates,
  formatCategory,
  type ConnectLeague,
  type LeagueSnapshot,
  type LeagueStatus,
  type LeagueTeam,
  type PlannerPreferences,
  type WaiverPlan,
} from "./league-fantasy-model";
import "./league-fantasy.css";

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
  return {
    status,
    snapshot,
    loading,
    error,
    connect: (input: ConnectLeague) => run(() => api.connect(input), true),
    selectTeam: (id: number) => run(() => api.selectTeam(id), true),
    disconnect: () => run(() => api.disconnect(), true),
    refresh: () => run(() => api.snapshot({ refresh: true })),
  };
}
export type LeagueFantasyState = ReturnType<typeof useLeagueFantasy>;

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
        <form onSubmit={submit} autoComplete="off">
          <div className="league-fields">
            <label>
              League ID
              <input name="league" type="number" min="1" step="1" required />
            </label>
            <label>
              Season ending year
              <input
                name="season"
                type="number"
                min="2019"
                max="2100"
                step="1"
                required
                placeholder="2027"
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
                While signed in to ESPN in your browser, open developer tools → Application/Storage
                → Cookies for ESPN. Copy SWID and espn_s2 here. This is cookie-based access, not
                OAuth; never share these values. They are sent once in the connection POST body,
                retained only in server memory for this session, and cleared by disconnect.
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
            Connect ESPN
          </button>
        </form>
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
          {snapshot.period.dates[0] ?? "Date unavailable"} –{" "}
          {snapshot.period.dates.at(-1) ?? "Date unavailable"}
        </p>
        <small>
          ESPN unofficial · Updated{" "}
          <time dateTime={snapshot.fetched_at}>{snapshot.fetched_at}</time>
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
  if (!snapshot)
    return (
      <section className="league-panel">
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
    <section className="league-panel">
      <SnapshotHeading snapshot={snapshot} loading={loading} onRefresh={onRefresh} />
      <h2>Current opponent: {opponent?.name ?? "Not available"}</h2>
      {error && <p role="alert">{error}</p>}
      {!snapshot.league.supported && (
        <p role="alert">
          {snapshot.league.unsupported_reason ?? "This league format is unsupported."}
        </p>
      )}
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
      <p className="league-score" aria-live="polite">
        {comparison?.id !== opponent?.id ? "Hypothetical comparison" : "Current matchup"}:{" "}
        {tally.winning} winning · {tally.tied} tied · {tally.losing} losing · {tally.unknown}{" "}
        unknown
      </p>
      <div className="league-table-wrap">
        <table>
          <caption>
            Current cumulative matchup totals · {user?.name ?? "Your team"} vs{" "}
            {comparison?.name ?? "Team unavailable"}
          </caption>
          <thead>
            <tr>
              <th>Category</th>
              <th>Your totals</th>
              <th>Compared totals</th>
              <th>Standing</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row) => {
              const state = compareCategory(row.user, row.opponent, row.key);
              return (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}
                    <small>{row.key === "to" ? "Lower is better" : "Higher is better"}</small>
                  </th>
                  <td>{formatCategory(row.user, row.key)}</td>
                  <td>{formatCategory(row.opponent, row.key)}</td>
                  <td className={`league-${state}`}>{state}</td>
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
const probability = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value) || value < 0 || value > 1
    ? "Unavailable"
    : `${(value * 100).toFixed(1)}%`;

export function WaiverWire({
  snapshot,
  onPlan,
  loading = false,
  error: leagueError,
  onRefresh,
}: {
  snapshot: LeagueSnapshot | null;
  onPlan?: (preferences: PlannerPreferences) => Promise<WaiverPlan>;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}) {
  const [preferences, setPreferences] = useState<PlannerPreferences>({
    user_confirmed_eligibility: false,
    candidate_ids: [],
    droppable_ids: [],
    max_stream_slots: 1,
    weekly_add_limit: null,
    used_adds: null,
    available_adds: null,
    user_confirmed_counts: false,
  });
  const [plan, setPlan] = useState<WaiverPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setPlan(null);
    setBusy(false);
    setError(null);
    setPreferences({
      user_confirmed_eligibility: false,
      candidate_ids: [],
      droppable_ids: [],
      max_stream_slots: 1,
      weekly_add_limit: null,
      used_adds: null,
      available_adds: null,
      user_confirmed_counts: false,
    });
  }, [snapshot]);
  function edit(patch: Partial<PlannerPreferences>) {
    generation.current++;
    setBusy(false);
    setPreferences((current) => ({
      ...current,
      ...patch,
      ...(patch.candidate_ids || patch.droppable_ids ? { user_confirmed_eligibility: false } : {}),
    }));
    setPlan(null);
    setError(null);
  }
  async function generate() {
    if (!onPlan) return;
    const current = ++generation.current;
    setBusy(true);
    setPlan(null);
    setError(null);
    try {
      const result = await onPlan({
        ...preferences,
        context: {
          league_id: snapshot!.league.id,
          team_id: snapshot!.selected_team_id,
          matchup_period_id: snapshot!.period.matchup_period_id,
          fetched_at: snapshot!.fetched_at,
        },
      });
      if (generation.current === current) setPlan(result);
    } catch {
      if (generation.current === current)
        setError("The recommendation could not be calculated. No roster changes were made.");
    } finally {
      if (generation.current === current) setBusy(false);
    }
  }
  if (!snapshot)
    return (
      <section className="league-panel">
        <h2>Waiver Wire</h2>
        <p>Connect ESPN and select your team to inspect eligible unrostered players.</p>
      </section>
    );
  const user = snapshot.teams.find((team) => team.id === snapshot.selected_team_id);
  const candidates = eligibleCandidates(snapshot);
  const actualOpponent = snapshot.teams.find((team) => team.id === snapshot.opponent_team_id);
  const knownLimit =
    snapshot.league.acquisition_settings.limit_per_scoring_period === false
      ? snapshot.league.acquisition_settings.weekly_add_limit
      : null;
  const players = new Map(
    [...snapshot.teams.flatMap((team) => team.roster), ...candidates].map((player) => [
      player.id,
      player,
    ]),
  );
  const validCounts =
    preferences.user_confirmed_counts &&
    preferences.weekly_add_limit !== null &&
    preferences.used_adds !== null &&
    preferences.available_adds !== null &&
    preferences.used_adds + preferences.available_adds <= preferences.weekly_add_limit;
  const serverCounts =
    knownLimit !== null &&
    user?.weekly_used_adds != null &&
    user.remaining_adds != null &&
    user.weekly_used_adds >= 0 &&
    user.remaining_adds >= 0 &&
    user.weekly_used_adds + user.remaining_adds <= knownLimit;
  const planReady = plan?.status === "ready";
  return (
    <section className="league-panel">
      <SnapshotHeading snapshot={snapshot} loading={loading} onRefresh={onRefresh} />
      {leagueError && <p role="alert">{leagueError}</p>}
      {!snapshot.league.supported && <p role="alert">{snapshot.league.unsupported_reason}</p>}
      <h2>Waiver Wire</h2>
      <p>
        Build a rotating shortlist, select roster slots to stream, then request a recommendation.
        Suggestions only; make any approved changes yourself in ESPN.
      </p>
      <div className="league-metrics">
        <p>
          Weekly cap <b>{knownLimit ?? "Unknown"}</b>
        </p>
        <p>
          Used this week <b>{user?.weekly_used_adds ?? "Unknown"}</b>
        </p>
        <p>
          Remaining adds <b>{user?.remaining_adds ?? "Unknown"}</b>
        </p>
      </div>
      <p>
        ESPN season acquisitions are not weekly usage. No seven-add allowance is assumed. Remaining
        dates: {snapshot.period.remaining_dates.join(", ") || "Unavailable or none remaining"}.
        Lineup slots: {snapshot.league.lineup_slots.join(", ") || "Unavailable"}.
      </p>
      <details className="league-gaps">
        <summary>Current matchup gaps vs {actualOpponent?.name ?? "opponent unavailable"}</summary>
        <p>
          Current results only. A deficit is not proof a category is attainable; projected
          schedules, minutes and uncertainty are required before making that judgment.
        </p>
        <div className="league-table-wrap">
          <table>
            <caption>Current matchup category gaps</caption>
            <thead>
              <tr>
                <th>Category</th>
                <th>Your current total</th>
                <th>Opponent current total</th>
                <th>Standing</th>
              </tr>
            </thead>
            <tbody>
              {LEAGUE_CATEGORIES.map((category) => {
                const own = categoryValue(user?.totals ?? null, category.key);
                const other = categoryValue(actualOpponent?.totals ?? null, category.key);
                const standing = compareCategory(own, other, category.key);
                return (
                  <tr key={category.key}>
                    <th scope="row">
                      {category.label}
                      {category.key === "to" ? " · lower is better" : ""}
                    </th>
                    <td>{formatCategory(own, category.key)}</td>
                    <td>{formatCategory(other, category.key)}</td>
                    <td className={`league-${standing}`}>{standing}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
      <fieldset>
        <legend>User-confirmed weekly constraints</legend>
        <p>
          Enter only verified counts from your league. These inputs are user supplied, not reported
          by ESPN. If your league allows seven weekly adds, enter 7 only after checking the current
          matchup's settings in ESPN.
        </p>
        <div className="league-fields">
          {(["weekly_add_limit", "used_adds", "available_adds"] as const).map((key, index) => (
            <label key={key}>
              {["Verified weekly cap", "Verified adds used", "Verified adds remaining"][index]}
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={preferences[key] ?? ""}
                onChange={(event) =>
                  edit({
                    [key]:
                      event.target.value === ""
                        ? null
                        : Math.max(0, Math.min(100, Math.floor(Number(event.target.value)))),
                    user_confirmed_counts: false,
                  })
                }
              />
            </label>
          ))}
        </div>
        <label className="league-check">
          <input
            type="checkbox"
            checked={preferences.user_confirmed_counts}
            onChange={(event) => edit({ user_confirmed_counts: event.target.checked })}
          />
          I verified these weekly counts and remaining adds in ESPN for this whole matchup,
          including any additional acquisition restrictions.
        </label>
        {preferences.user_confirmed_counts && !validCounts && (
          <p role="alert">
            Enter all three counts; used plus remaining must not exceed the weekly cap.
          </p>
        )}
      </fieldset>
      <label>
        Maximum stream slots
        <input
          type="number"
          min="1"
          max="4"
          value={preferences.max_stream_slots}
          onChange={(event) =>
            edit({
              max_stream_slots: Math.max(
                1,
                Math.min(4, Math.floor(Number(event.target.value) || 1)),
              ),
            })
          }
        />
      </label>
      <details className="league-gaps">
        <summary>Complete missing schedules and availability</summary>
        <p>
          Corrections below are your confirmed inputs for this snapshot, not ESPN data. Review both
          full rosters and your shortlist. Enter only remaining games that have not started and for
          which an acquisition can take effect. An empty confirmed schedule means no remaining
          games. Flagged injured players are modeled out unless you explicitly confirm availability
          for these dates. Refresh clears all confirmations.
        </p>
        <label>
          Verified remaining matchup dates (optional override, comma separated YYYY-MM-DD)
          <input
            type="text"
            value={preferences.remaining_dates?.join(", ") ?? ""}
            placeholder={snapshot.period.remaining_dates.join(", ")}
            onChange={(event) =>
              edit({
                remaining_dates: event.target.value.trim()
                  ? event.target.value.split(",").map((value) => value.trim())
                  : undefined,
              })
            }
          />
        </label>
        {[
          ...(user?.roster ?? []),
          ...(actualOpponent?.roster ?? []),
          ...candidates.filter((player) => preferences.candidate_ids.includes(player.id)),
        ].map((player) => {
          const correction = preferences.player_overrides?.[player.id] ?? {};
          const update = (patch: typeof correction) =>
            edit({
              player_overrides: {
                ...preferences.player_overrides,
                [player.id]: { ...correction, ...patch },
              },
            });
          return (
            <fieldset key={player.id}>
              <legend>{player.name}</legend>
              <p>
                Schedule:{" "}
                {player.schedule === null
                  ? "Unknown"
                  : player.schedule
                      .filter((game) => !game.started)
                      .map((game) => game.date)
                      .join(", ") || "No unstarted games reported"}
                . Availability:{" "}
                {player.injured === null
                  ? "Unknown"
                  : player.injured
                    ? "Flagged injured"
                    : "Reported available"}
                .
              </p>
              <label>
                Confirm {player.name} availability
                <select
                  value={
                    correction.injured === undefined
                      ? "reported"
                      : correction.injured
                        ? "out"
                        : "available"
                  }
                  onChange={(event) =>
                    update({
                      injured:
                        event.target.value === "reported"
                          ? undefined
                          : event.target.value === "out",
                    })
                  }
                >
                  <option value="reported">Use reported status (unknown stays unknown)</option>
                  <option value="available">I verified available for modeled dates</option>
                  <option value="out">I verified out for modeled dates</option>
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={correction.schedule !== undefined}
                  onChange={(event) => update({ schedule: event.target.checked ? [] : undefined })}
                />
                I am supplying {player.name} remaining unstarted game dates
              </label>
              {correction.schedule !== undefined && (
                <label>
                  {player.name} verified game dates (comma separated YYYY-MM-DD; empty means none)
                  <input
                    type="text"
                    value={correction.schedule.join(", ")}
                    onChange={(event) =>
                      update({
                        schedule: event.target.value.trim()
                          ? event.target.value.split(",").map((value) => value.trim())
                          : [],
                      })
                    }
                  />
                </label>
              )}
            </fieldset>
          );
        })}
      </details>
      <fieldset>
        <legend>Uncertainty evidence</legend>
        <label>
          Uncertainty mode
          <select
            value={preferences.uncertainty_mode ?? "history"}
            onChange={(event) =>
              edit({ uncertainty_mode: event.target.value as "history" | "sensitivity" })
            }
          >
            <option value="history">
              Use complete historical matchup variation when available
            </option>
            <option value="sensitivity">Explore my explicit sensitivity assumptions</option>
          </select>
        </label>
        <p>
          At least three complete, varying prior weekly comparisons are required for historical
          estimates. Otherwise baseline comparisons remain available. Sensitivity estimates are
          uncalibrated and depend on the values you enter.
        </p>
        {preferences.uncertainty_mode === "sensitivity" && (
          <div className="league-fields">
            {LEAGUE_CATEGORIES.map((category) => (
              <label key={category.key}>
                {category.label} margin standard deviation
                {category.key.endsWith("pct")
                  ? " (fraction: 0.01 = one percentage point)"
                  : " (category total units)"}
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={preferences.margin_sd?.[category.key] ?? ""}
                  onChange={(event) =>
                    edit({
                      margin_sd: {
                        ...preferences.margin_sd,
                        [category.key]:
                          event.target.value === "" ? undefined : Number(event.target.value),
                      },
                    })
                  }
                />
              </label>
            ))}
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>Roster players available to drop</legend>
        <p>
          Select only players you have verified can be dropped now in ESPN. Unknown locks remain
          unknown unless you explicitly confirm each selected player is unlocked. Reported locked
          players are excluded.
        </p>
        {user?.roster.map((player) => (
          <label className="league-check" key={player.id}>
            <input
              type="checkbox"
              disabled={
                player.locked === true ||
                player.lineup_slot === "IR" ||
                player.lineup_slot === "IR+"
              }
              checked={preferences.droppable_ids.includes(player.id)}
              onChange={(event) =>
                edit({
                  droppable_ids: event.target.checked
                    ? [...preferences.droppable_ids, player.id]
                    : preferences.droppable_ids.filter((id) => id !== player.id),
                })
              }
            />
            {player.name} ·{" "}
            {player.lineup_slot === "IR" || player.lineup_slot === "IR+"
              ? "IR moves are not modeled"
              : player.locked === null
                ? "Lock unknown: I verified this player is unlocked"
                : player.locked
                  ? "Locked"
                  : "Reported unlocked"}
          </label>
        ))}
      </fieldset>
      <h3>Eligible unrostered candidates</h3>
      <p>
        Only eligible free agents are listed. Waiver claims and rostered players are excluded.{" "}
        {snapshot.free_agents_truncated &&
          "ESPN returned a limited candidate pool; this is not the entire free-agent market."}
      </p>
      {candidates.length === 0 && <p>No eligible free agents were returned.</p>}
      <div className="league-table-wrap">
        <table>
          <caption>
            Current and prior-season per-game actuals; no future production is implied
          </caption>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Remaining games / minutes</th>
              <th>Current / prior sample</th>
              <th>Category averages · current / prior</th>
              <th>Shortlist</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((player) => (
              <tr key={player.id}>
                <th scope="row">
                  {player.name}
                  <small>
                    {player.positions.join(", ")} · {player.injury_status ?? "Injury unknown"}
                  </small>
                </th>
                <td>
                  {player.remaining_games ?? "Unknown"} games
                  <small>
                    {player.current_rates?.minutes ?? "Unknown"} current minutes/game · future
                    minutes unavailable
                  </small>
                  <small>
                    {player.schedule?.map((game) => game.date).join(", ") ?? "Schedule unknown"}
                  </small>
                </td>
                <td>
                  {player.current_games ?? "Unknown"} / {player.prior_games ?? "Unknown"} games
                </td>
                <td className="league-averages">
                  {LEAGUE_CATEGORIES.map((category) => (
                    <span key={category.key}>
                      {category.label}:{" "}
                      {formatCategory(
                        categoryValue(player.current_rates, category.key),
                        category.key,
                      )}{" "}
                      /{" "}
                      {formatCategory(
                        categoryValue(player.prior_rates, category.key),
                        category.key,
                      )}
                    </span>
                  ))}
                </td>
                <td>
                  <button
                    type="button"
                    aria-pressed={preferences.candidate_ids.includes(player.id)}
                    onClick={() =>
                      edit({
                        user_confirmed_eligibility: false,
                        candidate_ids: preferences.candidate_ids.includes(player.id)
                          ? preferences.candidate_ids.filter((id) => id !== player.id)
                          : [...preferences.candidate_ids, player.id],
                      })
                    }
                  >
                    {preferences.candidate_ids.includes(player.id) ? "Remove" : "Shortlist"}{" "}
                    {player.name}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <label className="league-check">
        <input
          type="checkbox"
          checked={preferences.user_confirmed_eligibility}
          onChange={(event) => edit({ user_confirmed_eligibility: event.target.checked })}
        />
        I verified the shortlisted players can be added now and the selected roster players can be
        dropped now in this matchup.
      </label>
      <h3>Editable rotation shortlist</h3>
      <p>
        Order expresses your preference; the optimizer may select fewer adds or a different order to
        respect dates and constraints. Editing clears the old recommendation.
      </p>
      <ol>
        {preferences.candidate_ids.map((id, index) => (
          <li key={id}>
            {players.get(id)?.name ?? id}{" "}
            <button
              type="button"
              disabled={index === 0}
              aria-label={`Move ${players.get(id)?.name ?? id} earlier`}
              onClick={() => {
                const ids = [...preferences.candidate_ids];
                [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
                edit({ candidate_ids: ids });
              }}
            >
              Earlier
            </button>{" "}
            <button
              type="button"
              onClick={() =>
                edit({ candidate_ids: preferences.candidate_ids.filter((item) => item !== id) })
              }
            >
              Remove
            </button>
          </li>
        ))}
      </ol>
      {!onPlan && (
        <p role="status">
          Optimizer integration is unavailable. No recommendations or probabilities have been
          generated.
        </p>
      )}
      <button
        type="button"
        disabled={
          !onPlan ||
          busy ||
          loading ||
          !!leagueError ||
          (!serverCounts && !validCounts) ||
          preferences.candidate_ids.length === 0 ||
          preferences.droppable_ids.length === 0 ||
          !preferences.user_confirmed_eligibility ||
          !snapshot.league.supported
        }
        onClick={() => void generate()}
      >
        {busy ? "Calculating…" : "Calculate recommendation"}
      </button>
      <p>
        Counts source:{" "}
        {validCounts
          ? "User-confirmed weekly inputs"
          : serverCounts
            ? "ESPN weekly counts"
            : "Missing verified weekly counts"}
        . Five-category estimates require historical uncertainty evidence or your explicitly
        selected sensitivity assumptions. No probabilities are calibrated guarantees.
      </p>
      {error && <p role="alert">{error}</p>}
      {plan && (
        <section aria-label="Waiver recommendation">
          <h3>Recommendation · {plan.status}</h3>
          <ul>
            {plan.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <p>
            Uncalibrated model probability of winning at least five categories: baseline{" "}
            {probability(planReady ? plan.baseline?.probability_five_wins : null)} → recommended{" "}
            {probability(planReady ? plan.projected?.probability_five_wins : null)}. Ties do not
            count as wins.
          </p>
          <p>
            Projected games: {plan.baseline?.games ?? "Unknown"} →{" "}
            {planReady ? (plan.projected?.games ?? "Unknown") : "Unavailable"}; minutes:{" "}
            {plan.baseline?.minutes ?? "Unknown"} →{" "}
            {planReady ? (plan.projected?.minutes ?? "Unknown") : "Unavailable"}. Adds remaining:{" "}
            {plan.remaining_adds ?? "Unknown"}.
          </p>
          <div className="league-table-wrap">
            <table>
              <caption>
                {plan.baseline?.basis === "recorded"
                  ? "Recorded baseline totals; projections withheld"
                  : "Projected end-of-period category totals and gains"}
              </caption>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Baseline</th>
                  <th>Recommended</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {LEAGUE_CATEGORIES.map((category) => {
                  const base = categoryValue(plan.baseline?.totals ?? null, category.key);
                  const next = categoryValue(
                    planReady ? (plan.projected?.totals ?? null) : null,
                    category.key,
                  );
                  return (
                    <tr key={category.key}>
                      <th scope="row">
                        {category.label}
                        {category.key === "to" ? " · lower is better" : ""}
                      </th>
                      <td>{formatCategory(base, category.key)}</td>
                      <td>{formatCategory(next, category.key)}</td>
                      <td>
                        {base === null || next === null
                          ? "Unavailable"
                          : `${next >= base ? "+" : ""}${category.key.endsWith("pct") ? `${((next - base) * 100).toFixed(2)} pp` : (next - base).toFixed(2)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {planReady ? (
            <ol>
              {plan.actions.map((action, index) => (
                <li key={`${index}-${action.date}-${action.add_id}`}>
                  <b>
                    {action.date}: add {players.get(action.add_id)?.name ?? action.add_id}, drop{" "}
                    {players.get(action.drop_id)?.name ?? action.drop_id}
                  </b>
                  <p>
                    Stream slot {action.stream_slot} · modeled probability gain{" "}
                    {action.probability_gain === null
                      ? "Unavailable"
                      : `${(action.probability_gain * 100).toFixed(1)} percentage points`}
                  </p>
                  <p>
                    {Object.entries(action.gains)
                      .map(([key, gain]) => `${key}: ${gain ?? "Unknown"}`)
                      .join(" · ")}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p>No actions are available with incomplete or unavailable inputs.</p>
          )}
          <h4>Assumptions and tradeoffs</h4>
          <ul>
            {[...plan.assumptions, ...plan.limitations].map((item, index) => (
              <li key={`${index}-${item}`}>{item}</li>
            ))}
          </ul>
          <p>
            Probabilities are model sensitivity estimates, not calibrated guarantees. Category
            correlations, injuries, role changes and uncertain schedules can change results. FG/FT
            use makes and attempts; extra turnovers can hurt. Review each add/drop and lineup
            eligibility before acting.
          </p>
          <DataGaps gaps={plan.data_gaps} />
        </section>
      )}
      <DataGaps gaps={snapshot.data_gaps} />
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
            {team?.remaining_adds ?? "Unknown"} weekly adds remaining ·{" "}
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
