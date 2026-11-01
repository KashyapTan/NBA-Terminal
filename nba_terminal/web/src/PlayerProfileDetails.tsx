import { useEffect, useMemo, useState } from "react";
import { GameLogTable, StatDistribution, StatTrend } from "./PlayerAnalysis";
import type { PlayerGameLogRow } from "./model";
import {
  getPlayerHistory,
  getPlayerMeasure,
  getPlayerShooting,
  searchPlayers,
  type PlayerSearchResult,
  type PlayerProfile,
  type ProfileMeasureData,
  type ShootingTables,
} from "./player-browser-api";
import { PROFILE_METRICS, type ProfileMeasure } from "./player-profile-metrics";

function format(value: unknown, kind = "number") {
  if (value == null || value === "" || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  return kind === "pct"
    ? (n * 100).toFixed(1) + "%"
    : kind === "integer"
      ? n.toFixed(0)
      : (kind === "signed" && n > 0 ? "+" : "") + n.toFixed(1);
}
export function PlayerSeasonMeasures({ profile }: { profile: PlayerProfile }) {
  const [measure, setMeasure] = useState<ProfileMeasure>("Advanced");
  const [data, setData] = useState<ProfileMeasureData | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (measure === "Advanced") {
      setData({
        measure,
        row: profile.advanced,
        state: profile.advanced_state,
        note: profile.advanced_note,
        source: profile.advanced_source,
        season: profile.season,
        phase: profile.phase,
      });
      setError("");
      return;
    }
    const controller = new AbortController();
    setData(null);
    setError("");
    getPlayerMeasure(profile.player_id, measure, profile.season, profile.phase, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [profile, measure, attempt]);
  return (
    <section className="player-analysis__section" aria-label="Full season profile tables">
      <h3>Full season profile</h3>
      <label>
        Season dashboard{" "}
        <select
          aria-label="Season dashboard measure"
          value={measure}
          onChange={(e) => setMeasure(e.target.value as ProfileMeasure)}
        >
          {Object.keys(PROFILE_METRICS).map((key) => (
            <option key={key}>{key}</option>
          ))}
        </select>
      </label>
      <p className="player-analysis__formula">
        Base = production/shooting, Misc = scoring situations/fouls, Scoring = scoring mix, Usage =
        team shares, Defense = defensive box-score measures. Values are per game unless labeled %,
        rating, ratio, or count. Double/triple doubles and wins/losses are counts. Usage MIN is
        total minutes even with PerGame requested; other displayed MIN fields are minutes per game.
        NBA Fantasy points use NBA scoring, not private-league scoring.
      </p>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading {measure} season table…</p>}
      {data && (
        <>
          <p className="player-analysis__formula">
            {data.source} · {data.season} · {data.phase} · GP {format(data.row.GP, "integer")} ·{" "}
            {measure === "Usage" ? "Total minutes" : "MPG"} {format(data.row.MIN)}
          </p>
          {data.state !== "available" ? (
            <p role={data.state === "error" ? "alert" : "status"}>
              {data.state === "error" ? "Request failed: " : "Unavailable: "}
              {data.note}
            </p>
          ) : (
            <div className="player-analysis__table-wrap">
              <table className="player-analysis__table player-analysis__profile-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {PROFILE_METRICS[measure].map(([key, label, kind]) => (
                    <tr key={key}>
                      <th>{label}</th>
                      <td>{format(data.row[key], kind)}</td>
                      <td>
                        {kind === "pct"
                          ? "%"
                          : /RATING/.test(key)
                            ? "points / 100 possessions"
                            : key === "PACE"
                              ? "possessions / 48 min"
                              : key === "POSS"
                                ? "possessions"
                                : /AST_TO/.test(key)
                                  ? "assists / turnover"
                                  : /AST_RATIO/.test(key)
                                    ? "assists / 100 plays"
                                    : key === "GP" ||
                                        key === "W" ||
                                        key === "L" ||
                                        key === "DD2" ||
                                        key === "TD3"
                                      ? "games"
                                      : key === "DEF_WS"
                                        ? "NBA provider DEF_WS"
                                        : key === "MIN"
                                          ? "minutes / game"
                                          : /_PG$/.test(key)
                                            ? "per game"
                                            : "provider per-game value"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {(error || data?.state === "error") && measure !== "Advanced" && (
        <button type="button" onClick={() => setAttempt((v) => v + 1)}>
          Retry season table
        </button>
      )}
    </section>
  );
}
const SPLITS = [
  "Overall",
  "Shot Area",
  "Distance 5ft",
  "Distance 8ft",
  "Assisted",
  "Shot Type Summary",
];
const SHOOTING_COLUMNS = [
  "GROUP_VALUE",
  "FGM",
  "FGA",
  "FG_PCT",
  "FG3M",
  "FG3A",
  "FG3_PCT",
  "EFG_PCT",
  "PCT_AST_2PM",
  "PCT_UAST_2PM",
  "PCT_AST_3PM",
  "PCT_UAST_3PM",
  "PCT_AST_FGM",
  "PCT_UAST_FGM",
];
export function PlayerShootingBreakdowns({ profile }: { profile: PlayerProfile }) {
  const [open, setOpen] = useState(false);
  const [split, setSplit] = useState("Overall");
  const [data, setData] = useState<ShootingTables | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setData(null);
    setError("");
    getPlayerShooting(profile.player_id, profile.season, profile.phase, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [profile.player_id, profile.season, profile.phase, open, attempt]);
  const table = data?.tables[split];
  const columns = SHOOTING_COLUMNS.filter((key) => table?.rows.some((row) => key in row));
  return (
    <section className="player-analysis__section" aria-label="Shooting breakdowns">
      <h3>Shot area, distance, assisted &amp; shot type</h3>
      {!open ? (
        <button type="button" onClick={() => setOpen(true)}>
          Load shooting breakdowns
        </button>
      ) : (
        <>
          <label>
            Breakdown{" "}
            <select
              aria-label="Shooting breakdown"
              value={split}
              onChange={(e) => setSplit(e.target.value)}
            >
              {SPLITS.map((label) => (
                <option key={label}>{label}</option>
              ))}
            </select>
          </label>
          <p className="player-analysis__formula">
            {data?.source || "PlayerDashboardByShootingSplits · Totals"} · {profile.season} ·{" "}
            {profile.phase}. FGM/FGA and 3PM/3PA are total makes/attempts; percentages are 0–100.
            Assisted and unassisted fields describe shares of made shots. No rows means unavailable,
            not zero attempts.
          </p>
          {!data && !error && <p role="status">Loading six shooting tables…</p>}
          {error && <p role="alert">{error}</p>}
          {data && !table && (
            <p role={data.state === "error" ? "alert" : "status"}>
              {data.note || "This shooting table was not returned."}
            </p>
          )}
          {table && table.state !== "available" && (
            <p role={table.state === "error" ? "alert" : "status"}>
              {table.state === "error" ? "Request failed: " : "Unavailable: "}
              {table.note}
            </p>
          )}
          {table?.state === "available" && (
            <div className="player-analysis__table-wrap">
              <table className="player-analysis__table player-analysis__profile-table">
                <caption>{split} · season totals</caption>
                <thead>
                  <tr>
                    {columns.map((key) => (
                      <th key={key}>
                        {key === "GROUP_VALUE" ? "Breakdown" : key.replaceAll("_", " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, index) => (
                    <tr key={String(row.GROUP_VALUE) + index}>
                      {columns.map((key) => (
                        <td key={key}>
                          {key === "GROUP_VALUE"
                            ? row[key]
                            : format(row[key], key.includes("PCT") ? "pct" : "integer")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(error || data?.state === "error") && (
            <button type="button" onClick={() => setAttempt((v) => v + 1)}>
              Retry shooting tables
            </button>
          )}
        </>
      )}
    </section>
  );
}
const SAMPLE_STATS: Array<[keyof PlayerGameLogRow, string]> = [
  ["pts", "Points"],
  ["reb", "Rebounds"],
  ["ast", "Assists"],
  ["stl", "Steals"],
  ["blk", "Blocks"],
  ["fg3m", "3PM"],
  ["pra", "PRA"],
  ["pr", "Points + rebounds"],
  ["pa", "Points + assists"],
  ["ra", "Rebounds + assists"],
  ["stocks", "Steals + blocks"],
];
function opponent(row: PlayerGameLogRow) {
  return (
    row.matchup
      ?.split(/\s+(?:vs\.?|@)\s+/i)[1]
      ?.trim()
      .toUpperCase() || ""
  );
}
function filtered(rows: PlayerGameLogRow[], team: string, window: string) {
  const matched = team ? rows.filter((row) => opponent(row) === team) : rows;
  return window === "season" ? matched : matched.slice(0, Number(window));
}
export function summarizePlayerSample(
  rows: PlayerGameLogRow[],
  stat: keyof PlayerGameLogRow,
  line: number,
) {
  const values = rows
    .map((row) => row[stat])
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v))
    .sort((a, b) => a - b);
  const n = values.length;
  if (!n)
    return {
      n,
      mean: null,
      sd: null,
      cv: null,
      p25: null,
      median: null,
      p75: null,
      max: null,
      hits: 0,
      rate: null,
    };
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = n > 1 ? Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (n - 1)) : 0;
  const percentile = (p: number) => {
    const position = (n - 1) * p;
    const lower = Math.floor(position);
    return values[lower] + (values[Math.ceil(position)] - values[lower]) * (position - lower);
  };
  const hits = values.filter((v) => v >= line).length;
  return {
    n,
    mean,
    sd,
    cv: mean > 0 ? sd / mean : 0,
    p25: percentile(0.25),
    median: percentile(0.5),
    p75: percentile(0.75),
    max: values[n - 1],
    hits,
    rate: hits / n,
  };
}
export function PlayerSampleExplorer({ profile }: { profile: PlayerProfile }) {
  const [stat, setStat] = useState<keyof PlayerGameLogRow>("pts");
  const [team, setTeam] = useState("");
  const [window, setWindow] = useState("season");
  const [line, setLine] = useState(20);
  const [season, setSeason] = useState(() => {
    const start = Number(profile.season.slice(0, 4)) - 1;
    return `${start}-${String(start + 1).slice(-2)}`;
  });
  const [requested, setRequested] = useState<string | null>(null);
  const self = { player_id: profile.player_id, name: profile.player_name, active: true };
  const [comparisonPlayer, setComparisonPlayer] = useState<PlayerSearchResult>(self);
  const [requestedPlayer, setRequestedPlayer] = useState<PlayerSearchResult>(self);
  const [playerQuery, setPlayerQuery] = useState("");
  const [playerResults, setPlayerResults] = useState<PlayerSearchResult[]>([]);
  const [playerSearchError, setPlayerSearchError] = useState("");
  useEffect(() => {
    if (playerQuery.trim().length < 2) {
      setPlayerResults([]);
      setPlayerSearchError("");
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPlayerSearchError("");
      searchPlayers(playerQuery, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) setPlayerResults(data.players);
        })
        .catch((err) => {
          if (!controller.signal.aborted) setPlayerSearchError(err.message);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [playerQuery]);
  const [comparison, setComparison] = useState<PlayerProfile["history"] | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!requested) return;
    const controller = new AbortController();
    setComparison(null);
    setError("");
    getPlayerHistory(requestedPlayer.player_id, requested, profile.phase, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setComparison(data.history);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });
    return () => controller.abort();
  }, [requestedPlayer.player_id, profile.phase, requested, attempt]);
  const teams = useMemo(
    () =>
      Array.from(
        new Set(
          [...profile.history.games, ...(comparison?.games || [])].map(opponent).filter(Boolean),
        ),
      ).sort(),
    [profile.history.games, comparison],
  );
  const rows = filtered(profile.history.games, team, window);
  const comparisonRows = filtered(comparison?.games || [], team, window);
  const samples = [
    { name: profile.season, player: self, history: profile.history, rows },
    ...(comparison
      ? [{ name: requested!, player: requestedPlayer, history: comparison, rows: comparisonRows }]
      : []),
  ];
  const label = SAMPLE_STATS.find(([key]) => key === stat)?.[1] || "Points";
  return (
    <section className="player-analysis__section" aria-label="Opponent and season comparison">
      <h3>Player, opponent &amp; season comparison</h3>
      <div className="player-analysis__history-controls">
        <label>
          Opponent{" "}
          <select
            aria-label="Profile opponent"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
          >
            <option value="">All opponents</option>
            {teams.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Stat{" "}
          <select
            aria-label="Profile sample stat"
            value={stat}
            onChange={(e) => setStat(e.target.value as keyof PlayerGameLogRow)}
          >
            {SAMPLE_STATS.map(([key, name]) => (
              <option key={key} value={key}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sample{" "}
          <select
            aria-label="Profile sample window"
            value={window}
            onChange={(e) => setWindow(e.target.value)}
          >
            <option value="season">Season</option>
            {[5, 10, 15, 20].map((n) => (
              <option key={n} value={n}>
                Last {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Line{" "}
          <input
            aria-label="Profile sample line"
            type="number"
            min="0"
            step="0.5"
            value={line}
            onChange={(e) => setLine(Number(e.target.value))}
          />
        </label>
        <label>
          Find comparison player
          <input
            aria-label="Find comparison player"
            type="search"
            value={playerQuery}
            placeholder="Name (2+ letters)"
            onChange={(e) => setPlayerQuery(e.target.value)}
          />
        </label>
        <label>
          Compare player
          <select
            aria-label="Comparison player"
            value={comparisonPlayer.player_id}
            onChange={(e) => {
              const chosen = [self, comparisonPlayer, ...playerResults].find(
                (item) => item.player_id === Number(e.target.value),
              );
              if (chosen) setComparisonPlayer(chosen);
            }}
          >
            {Array.from(
              new Map(
                [self, comparisonPlayer, ...playerResults].map((item) => [item.player_id, item]),
              ).values(),
            ).map((item) => (
              <option key={item.player_id} value={item.player_id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Compare season{" "}
          <input
            aria-label="Comparison season"
            value={season}
            pattern="[0-9]{4}-[0-9]{2}"
            placeholder="2024-25"
            onChange={(e) => setSeason(e.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={
            !/^\d{4}-\d{2}$/.test(season) ||
            (season === profile.season && comparisonPlayer.player_id === profile.player_id)
          }
          onClick={() => {
            setRequestedPlayer(comparisonPlayer);
            setRequested(season);
            setAttempt((v) => v + 1);
          }}
        >
          Compare season
        </button>
      </div>
      <p className="player-analysis__formula">
        {label} · {team || "All opponents"} · {profile.phase}. Opponent filter applies before the
        most recent game window in both samples. Valid stat counts exclude unknown values. Hit = at
        or above line; descriptive historical frequency, not a forecast. Percentiles use linear
        interpolation at (n−1) × p; each sample retains its own source games.
      </p>
      {requested && !comparison && !error && <p role="status">Loading {requested} comparison…</p>}
      {error && <p role="alert">{error}</p>}
      {playerSearchError && <p role="alert">Comparison search: {playerSearchError}</p>}
      <div className="player-analysis__table-wrap">
        <table
          className="player-analysis__table player-analysis__profile-table"
          aria-label="Season sample comparison"
        >
          <thead>
            <tr>
              <th>Player</th>
              <th>Season / phase</th>
              <th>Valid n</th>
              <th>Mean</th>
              <th>Sample SD</th>
              <th>CV</th>
              <th>25th</th>
              <th>Median</th>
              <th>75th</th>
              <th>Max</th>
              <th>Hits ≥ {line}</th>
              <th>Hit rate</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((sample) => {
              const s = summarizePlayerSample(sample.rows, stat, line);
              return (
                <tr key={`${sample.player.player_id}:${sample.name}`}>
                  <th>{sample.player.name}</th>
                  <td>
                    {sample.name} · {profile.phase}
                  </td>
                  <td>{s.n}</td>
                  <td>{format(s.mean)}</td>
                  <td>{format(s.sd)}</td>
                  <td>{format(s.cv, "pct")}</td>
                  <td>{format(s.p25)}</td>
                  <td>{format(s.median)}</td>
                  <td>{format(s.p75)}</td>
                  <td>{format(s.max)}</td>
                  <td>
                    {s.hits}/{s.n}
                  </td>
                  <td>{format(s.rate, "pct")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="player-analysis__formula">
        Sample SD uses ddof=1; one observation gives SD 0 by the retained convention. CV = SD /
        positive mean, otherwise 0 (legacy convention). Small or zero samples do not establish
        consistency. Players, seasons and phases stay separate.
      </p>
      {samples
        .filter((s) => s.history.state !== "available")
        .map((s) => (
          <p
            key={`${s.player.player_id}:${s.name}`}
            role={s.history.state === "error" ? "alert" : "status"}
          >
            {s.name}: {s.history.note}
          </p>
        ))}
      <div className="player-analysis__visuals">
        <StatTrend rows={rows} statKey={stat} statLabel={`${profile.season} ${label}`} />
        <StatDistribution rows={rows} statKey={stat} statLabel={`${profile.season} ${label}`} />
      </div>
      <details>
        <summary>Filtered game log · {rows.length} games</summary>
        <GameLogTable
          rows={rows}
          season={profile.season}
          phase={profile.phase}
          playerId={profile.player_id}
        />
      </details>
      {comparison && (
        <div className="player-analysis__comparison-sample">
          <h4>
            {requestedPlayer.name} · {requested} · {profile.phase}
          </h4>
          <div className="player-analysis__visuals">
            <StatTrend
              rows={comparisonRows}
              statKey={stat}
              statLabel={`${requestedPlayer.name} ${label}`}
            />
            <StatDistribution
              rows={comparisonRows}
              statKey={stat}
              statLabel={`${requestedPlayer.name} ${label}`}
            />
          </div>
          <details>
            <summary>
              {requested} comparison game log · {comparisonRows.length} games
            </summary>
            <GameLogTable
              rows={comparisonRows}
              season={requested!}
              phase={profile.phase}
              playerId={requestedPlayer.player_id}
            />
          </details>
        </div>
      )}
    </section>
  );
}
