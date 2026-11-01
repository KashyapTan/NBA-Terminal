import { useEffect, useRef, useState } from "react";
import {
  type AnalyticsTool,
  type ToolMeta,
  type ToolResult,
  type ToolRow,
  getAnalyticsTool,
  getToolsMeta,
} from "./analytics-tools-api";
import "./analytics-tools.css";

const TOOLS: [AnalyticsTool, string][] = [
  ["predictor", "Points Predictor"],
  ["consistency", "Team Consistency"],
  ["defense", "Team Defense"],
  ["slate", "Slate Scanner"],
  ["picks", "Picks Archive"],
  ["catalog", "Stats / API Reference"],
];
const DEFINITIONS: Record<AnalyticsTool, string> = {
  predictor:
    "Uncalibrated points heuristic: 45% season + 35% last 5 + 20% last 10, scaled by projected / average minutes, plus defense, pace, rest and home adjustments. No probability or sportsbook line comparison. Team selection supplies matchup context; roster status is not verified. History ends before the selected date. Defense = 0.10 × opponent-minus-league DEF rating (points allowed / 100 possessions). Pace = 0.35 × opponent-minus-league pace (possessions / 48 min) × projected MIN / 48. Rest ≥ 2 off-days adds 0.4, otherwise −0.4; home adds 0.35, away −0.15.",
  consistency:
    "Ascending CV = most consistent. Sample SD (n−1) / mean, using the newest window of games, then removing null stats. At least the full window of returned games is required; mean ≤ 0 or SD ≤ 0 is excluded, including constant positive values. Current season roster; traded players retain all season games. Top 15 shown. CV tiers: <30% Elite, <50% Good, <70% Average, otherwise Variable.",
  defense:
    "Lower opponent FG% ranks first. Rank tiers: 1–5 Elite, 6–15 Good, 16–20 Average, 21–25 Below Avg, 26+ Poor. Unadjusted for shot quality. League context is the unweighted mean of available team percentages. Corner 3 is the unweighted left/right mean; missing zones stay unknown.",
  slate:
    "Season per-game minutes ≥ 25 and games ≥ 5 on the selected schedule. Recent projection = 60% last 5 + 25% last 10 + 15% season points. Shows absolute difference ≥ 3 from season mean, sorted largest first. No injury/minutes forecast, wagering advantage or calibrated probability. All statistics end before the selected date. L10 falls back to L5 below 10 valid points games; L5 uses up to five valid values after null removal, with at least five returned game rows required.",
  picks:
    "Read-only historical Markdown notes. Search filenames and note text. These user notes are historical opinions, not current recommendations.",
  catalog:
    "Search installed nba_api endpoint names, parameters, datasets and columns. Metadata reference only: installed schemas do not establish live endpoint support. This tool never executes an endpoint.",
};
const GUIDANCE: Record<AnalyticsTool, string> = {
  predictor:
    "Estimate points from scoring history and explicit matchup context. An uncalibrated heuristic, with no sportsbook comparison.",
  consistency:
    "Rank roster players by observed variability. Lower CV means more consistent; zero mean or zero variability is excluded.",
  defense:
    "Compare opponent shot percentages across teams and zones. Missing data stays unknown; lower percentages rank first.",
  slate:
    "Inspect selected-date players whose recent scoring trend differs from their season mean. This is a historical trend comparison.",
  picks:
    "Browse or search historical notes read-only. Notes are historical opinions, not current recommendations.",
  catalog:
    "Search installed endpoint parameters and schemas. Metadata only; live availability is unverified.",
};
const ZONES = [
  "Restricted Area",
  "In The Paint (Non-RA)",
  "Mid-Range",
  "Corner 3",
  "Above the Break 3",
];
type Column = [string, string, "percent"?];
const COLUMNS: Record<string, Column[]> = {
  consistency: [
    ["rank", "Rank"],
    ["player", "Player"],
    ["cv", "CV", "percent"],
    ["mean", "Mean"],
    ["sd", "Sample SD"],
    ["valid_games", "Valid games"],
    ["window", "Window"],
    ["tier", "Tier"],
  ],
  defense: [
    ["rank", "Rank"],
    ["team", "Team"],
    ["tier", "Tier"],
    ["OPP_FG_PCT", "Opp FG", "percent"],
    ["OPP_FG3_PCT", "Opp 3P", "percent"],
    ...ZONES.map((z): Column => [z, z, "percent"]),
  ],
  slate: [
    ["player", "Player"],
    ["team", "Team"],
    ["opponent", "Opponent"],
    ["direction", "Trend"],
    ["season_avg", "Season PTS"],
    ["last_5", "L5"],
    ["last_10", "L10"],
    ["projection", "Projection"],
    ["difference", "Difference"],
    ["minutes", "Season MIN"],
    ["season_games", "Season GP"],
    ["valid_games", "History GP"],
    ["recent_valid_games", "L5 valid"],
  ],
};
function contextLabel(key: string): string {
  return (
    (
      {
        rest_days: "Rest off-days",
        is_home: "Home game",
        def_rating: "Opponent DEF rating",
        league_def_rating: "League DEF rating",
        pace: "Opponent pace",
        league_pace: "League pace",
        OPP_FG_PCT: "Opponent FG",
        OPP_FG3_PCT: "Opponent 3P",
      } as Record<string, string>
    )[key] ?? key
  );
}
function display(value: unknown, percent = false): string {
  if (value == null) return "Unknown";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number")
    return percent
      ? `${(value * 100).toFixed(1)}%`
      : Number.isInteger(value)
        ? String(value)
        : value.toFixed(2);
  return String(value);
}
function ResultTable({ rows, columns }: { rows: ToolRow[]; columns: Column[] }) {
  return (
    <div
      className="at-table-scroll"
      tabIndex={0}
      role="region"
      aria-label="Analytics results table"
    >
      <table>
        <thead>
          <tr>
            {columns.map(([key, title]) => (
              <th key={key} scope="col">
                {title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={String(row.player_id ?? row.team_id ?? i)}
              className={`at-${row.color ?? (typeof row.difference === "number" ? (row.difference > 0 ? "success" : "danger") : "muted")}`}
            >
              {columns.map(([key, , format]) => (
                <td key={key}>{display(row[key], format === "percent")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function PredictorResult({ result }: { result: ToolResult }) {
  return (
    <>
      <p className="at-projection">
        {result.projection == null
          ? "Projection incomplete"
          : `${result.projection.toFixed(1)} estimated points`}
      </p>
      {!!result.missing_context?.length && (
        <p className="at-warning">
          Missing context: {result.missing_context.map(contextLabel).join(", ")}. Enter explicit
          estimates below to complete the heuristic.
        </p>
      )}
      {result.baseline != null && (
        <>
          <ResultTable
            columns={[
              ["season", "Season PTS"],
              ["l5", "L5"],
              ["l10", "L10"],
              ["games", "Valid games"],
              ["minutes", "Average MIN"],
              ["factor", "Minutes factor"],
            ]}
            rows={[
              {
                season: result.season_avg ?? null,
                l5: result.last_5 ?? null,
                l10: result.last_10 ?? null,
                games: result.valid_games ?? null,
                minutes: result.avg_minutes ?? null,
                factor: result.minute_factor ?? null,
              },
            ]}
          />
          <ResultTable
            columns={[
              ["component", "Component"],
              ["points", "Points"],
            ]}
            rows={[
              { component: "Weighted baseline", points: result.baseline },
              ...(["minutes", "defense", "pace", "rest", "home"] as const).map((name) => ({
                component: `${name} adjustment`,
                points: result[`${name}_adjustment`] ?? null,
              })),
            ]}
          />
          <p>
            {result.last_5_fallback ? "L5 falls back to season mean. " : ""}
            {result.last_10_fallback ? "L10 falls back to season mean. " : ""}
            {result.minutes_estimated
              ? "Average minutes missing/nonpositive: minutes factor estimated as 1. "
              : ""}
            Final total is floored at zero.
          </p>
        </>
      )}
      {result.context && (
        <ResultTable
          columns={[
            ["field", "Context"],
            ["value", "Value"],
            ["source", "Source"],
          ]}
          rows={Object.entries(result.context).map(([field, value]) => ({
            field: contextLabel(field),
            value,
            source: result.context_sources?.[field] ?? "unavailable",
          }))}
        />
      )}
    </>
  );
}

export function AnalyticsTools({ initialTool = "predictor" }: { initialTool?: AnalyticsTool }) {
  const [tool, setTool] = useState<AnalyticsTool>(initialTool);
  const [meta, setMeta] = useState<ToolMeta>();
  const [metaError, setMetaError] = useState("");
  const [season, setSeason] = useState("");
  const [phase, setPhase] = useState("Regular Season");
  const [day, setDay] = useState("");
  const [team, setTeam] = useState("");
  const [opponent, setOpponent] = useState("");
  const [playerQuery, setPlayerQuery] = useState("");
  const [player, setPlayer] = useState("");
  const [minutes, setMinutes] = useState("32");
  const [stat, setStat] = useState("PTS");
  const [window, setWindow] = useState("10");
  const [query, setQuery] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ToolResult>();
  const [caption, setCaption] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  useEffect(() => {
    let active = true;
    getToolsMeta()
      .then((data) => {
        if (!active) return;
        setMeta(data);
        setSeason(data.season);
        setDay(data.today);
        setTeam(String(data.teams[0]?.id ?? ""));
        setOpponent(String(data.teams[1]?.id ?? ""));
      })
      .catch((e: Error) => {
        if (active) setMetaError(e.message);
      });
    return () => {
      active = false;
      request.current++;
    };
  }, []);
  const online = !["picks", "catalog"].includes(tool);
  async function load(filename?: string) {
    const id = ++request.current;
    setBusy(true);
    setError("");
    setResult(undefined);
    const params: Record<string, string> = online ? { season, phase } : { q: query };
    if (tool === "slate" || tool === "predictor") params.day = day;
    if (tool === "consistency") Object.assign(params, { team_id: team, stat, window });
    if (tool === "predictor")
      Object.assign(
        params,
        { player_id: player, team_id: team, opponent_id: opponent, minutes },
        Object.fromEntries(Object.entries(overrides).filter(([, v]) => v !== "")),
      );
    if (filename) params.filename = filename;
    const label = online
      ? `${season} · ${phase}${params.day ? ` · before ${day}` : ""}${params.team_id ? ` · ${meta?.teams.find((t) => String(t.id) === team)?.abbreviation}` : ""}${tool === "consistency" ? ` · ${stat} · last ${window}` : ""}`
      : query
        ? `Search: ${query}`
        : "All records";
    try {
      const data = await getAnalyticsTool(tool, params);
      if (id === request.current) {
        setResult(data);
        setCaption(
          tool === "predictor"
            ? `${label} · ${meta?.players.find((p) => String(p.id) === player)?.full_name ?? player} vs ${meta?.teams.find((t) => String(t.id) === opponent)?.abbreviation ?? opponent} · ${minutes} projected MIN`
            : label,
        );
      }
    } catch (e) {
      if (id === request.current)
        setError(e instanceof Error ? e.message : "Unable to load this tool.");
    } finally {
      if (id === request.current) setBusy(false);
    }
  }
  const teamSelect = (label: string, value: string, change: (value: string) => void) => (
    <label className="at-team-field">
      {label}
      <select value={value} onChange={(e) => change(e.target.value)} required>
        {meta?.teams.map((t) => (
          <option key={t.id} value={t.id}>
            {t.abbreviation} · {t.full_name}
          </option>
        ))}
      </select>
    </label>
  );
  const selectedPlayers =
    meta?.players
      .filter((p) => p.full_name.toLowerCase().includes(playerQuery.toLowerCase()))
      .slice(0, 60) ?? [];
  return (
    <section className="analytics-tools" aria-label="Analytics tools">
      <header>
        <h1>Analytics Tools</h1>
        <p>Retained NBA analyses, with visible samples, definitions and source availability.</p>
      </header>
      <nav className="at-tabs" aria-label="Choose analytics tool">
        {TOOLS.map(([key, title]) => (
          <button
            type="button"
            key={key}
            aria-pressed={tool === key}
            onClick={() => {
              request.current++;
              setTool(key);
              setResult(undefined);
              setBusy(false);
              setError("");
              setQuery("");
            }}
          >
            {title}
          </button>
        ))}
      </nav>
      <h2>{TOOLS.find(([key]) => key === tool)?.[1]}</h2>
      <p className="at-definition">{GUIDANCE[tool]}</p>
      <details>
        <summary>Definitions and original method</summary>
        <p>{DEFINITIONS[tool]}</p>
      </details>
      {metaError && online && (
        <p role="alert">Tool setup unavailable: {metaError}. Reload to retry.</p>
      )}
      <form
        className="at-controls"
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        {online && (
          <>
            <label>
              Season
              <input
                value={season}
                onChange={(e) => setSeason(e.target.value)}
                required
                pattern="[0-9]{4}-[0-9]{2}"
                placeholder="YYYY-YY"
              />
            </label>
            <label>
              Phase
              <select value={phase} onChange={(e) => setPhase(e.target.value)}>
                {["Regular Season", "Playoffs", "Pre Season", "All Star"].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
          </>
        )}
        {(tool === "predictor" || tool === "slate") && (
          <label>
            Game date (NBA Eastern)
            <input type="date" required value={day} onChange={(e) => setDay(e.target.value)} />
          </label>
        )}
        {(tool === "predictor" || tool === "consistency") &&
          teamSelect("Player team", team, setTeam)}
        {tool === "predictor" && (
          <>
            {teamSelect("Opponent", opponent, setOpponent)}
            <label>
              Find player
              <input
                value={playerQuery}
                onChange={(e) => {
                  setPlayerQuery(e.target.value);
                  setPlayer("");
                }}
                placeholder="Type a player name"
              />
            </label>
            <label>
              Player
              <select value={player} onChange={(e) => setPlayer(e.target.value)} required>
                <option value="">Choose player (first 60 matches)</option>
                {selectedPlayers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Projected minutes (estimate)
              <input
                type="number"
                min="0.1"
                max="60"
                step="0.1"
                required
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
              />
            </label>
          </>
        )}
        {tool === "consistency" && (
          <>
            <label>
              Statistic
              <select value={stat} onChange={(e) => setStat(e.target.value)}>
                {["PTS", "REB", "AST", "STL", "BLK"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Game window
              <select value={window} onChange={(e) => setWindow(e.target.value)}>
                {[5, 10, 15, 20].map((w) => (
                  <option key={w}>{w}</option>
                ))}
              </select>
            </label>
          </>
        )}
        {!online && (
          <label className="at-search">
            Search {tool === "picks" ? "notes" : "endpoints / parameters / schema"}
            <input value={query} maxLength={200} onChange={(e) => setQuery(e.target.value)} />
          </label>
        )}
        {tool === "predictor" && (
          <details className="at-overrides">
            <summary>Context estimates / overrides (blank = fetch NBA data)</summary>
            <p>
              All entered values are user estimates. Missing context prevents a final total; no
              silent home/rest/league default.
            </p>
            <div className="at-controls">
              {[
                ["rest_days", "Rest off-days (0–5)", "0", "5"],
                ["def_rating", "Opponent DEF rating", "0.1", "250"],
                ["league_def_rating", "League DEF rating", "0.1", "250"],
                ["pace", "Opponent pace", "0.1", "200"],
                ["league_pace", "League pace", "0.1", "200"],
              ].map(([key, label, min, max]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    step="any"
                    min={min}
                    max={max}
                    value={overrides[key] ?? ""}
                    onChange={(e) => setOverrides({ ...overrides, [key]: e.target.value })}
                  />
                </label>
              ))}
              <label>
                Home game
                <select
                  value={overrides.is_home ?? ""}
                  onChange={(e) => setOverrides({ ...overrides, is_home: e.target.value })}
                >
                  <option value="">From schedule / unknown</option>
                  <option value="true">Home (estimate)</option>
                  <option value="false">Away (estimate)</option>
                </select>
              </label>
            </div>
          </details>
        )}
        <button className="at-load" type="submit" disabled={busy || (online && !meta)}>
          {busy
            ? "Loading…"
            : tool === "picks" || tool === "catalog"
              ? "Search / browse"
              : "Run analysis"}
        </button>
      </form>
      {busy && <p role="status">Loading {TOOLS.find(([key]) => key === tool)?.[1]}…</p>}
      {error && (
        <p className="at-danger" role="alert">
          {error}
        </p>
      )}
      {result && (
        <section className="at-results" aria-label="Analysis result">
          <p className={`at-${result.state === "ready" ? "success" : "warning"}`} role="status">
            {result.state === "ready"
              ? "Loaded"
              : result.state === "partial"
                ? "Partial data — review missing inputs"
                : result.state === "empty"
                  ? "No returned data for this selection"
                  : "Required source unavailable"}{" "}
            · {caption}
          </p>
          {!!result.errors.length && (
            <details>
              <summary>Source diagnostics ({result.errors.length})</summary>
              <ul>
                {result.errors.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </details>
          )}
          {tool === "predictor" && <PredictorResult result={result} />}
          {tool === "consistency" && result.roster_players != null && (
            <p>
              {result.ranked_players} ranked of {result.roster_players} roster players. Excluded:{" "}
              {Object.entries(result.excluded ?? {})
                .map(([k, n]) => `${k.replaceAll("_", " ")}: ${n}`)
                .join("; ")}
              .
            </p>
          )}
          {tool === "defense" && result.league_means && (
            <>
              <h3>League context</h3>
              <ResultTable
                columns={[
                  ["stat", "Statistic"],
                  ["mean", "Team mean", "percent"],
                  ["count", "Available teams"],
                ]}
                rows={Object.entries(result.league_means).map(([key, mean]) => ({
                  stat: contextLabel(key),
                  mean,
                  count: result.league_counts?.[key] ?? 0,
                }))}
              />
            </>
          )}
          {tool === "slate" && (
            <>
              <p>
                Schedule:{" "}
                {result.games
                  ?.map(
                    (g) =>
                      `${g.away_team.abbreviation} @ ${g.home_team.abbreviation} (${g.status})`,
                  )
                  .join(" · ") || "No games returned"}
              </p>
              {result.qualified_players != null && (
                <p>
                  {result.qualified_players} qualified · {result.evaluated_players} evaluated ·{" "}
                  {result.missing_players} missing player samples · {result.insufficient_players}{" "}
                  with fewer than 5 returned games.
                </p>
              )}
            </>
          )}
          {result.rows && COLUMNS[tool] && (
            <>
              {result.rows.length ? (
                <ResultTable rows={result.rows} columns={COLUMNS[tool]} />
              ) : (
                <p>
                  {tool === "slate" && result.evaluated_players === 0
                    ? "No qualifying player samples could be evaluated."
                    : tool === "slate" && result.state === "ready"
                      ? "No evaluated players met the absolute 3-point difference filter."
                      : "No ranking rows available for this selection."}
                </p>
              )}
            </>
          )}
          {tool === "picks" && (
            <>
              {result.files && (
                <>
                  <p>{result.files.length} matching files</p>
                  <ul className="at-files">
                    {result.files.map((f) => (
                      <li key={f.filename}>
                        <button type="button" onClick={() => void load(f.filename)}>
                          {f.filename}
                        </button>
                        <p>{f.preview}</p>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {result.content != null && (
                <article>
                  <h3>{result.filename}</h3>
                  <pre className="at-note">{result.content}</pre>
                  <button type="button" onClick={() => void load()}>
                    Back to matching files
                  </button>
                </article>
              )}
            </>
          )}
          {tool === "catalog" && (
            <>
              <p>
                Installed nba_api {result.version} · {result.endpoints?.length ?? 0} matching
                endpoints · metadata only
              </p>
              {result.endpoints?.map((endpoint) => (
                <details key={endpoint.name}>
                  <summary>
                    {endpoint.name} · {endpoint.category}
                  </summary>
                  <h3>Constructor parameters / installed defaults</h3>
                  <ResultTable
                    columns={[
                      ["parameter", "Parameter"],
                      ["default", "Default"],
                    ]}
                    rows={Object.entries(endpoint.parameters).map(([parameter, value]) => ({
                      parameter,
                      default: value,
                    }))}
                  />
                  {Object.entries(endpoint.datasets).map(([name, columns]) => (
                    <details key={name}>
                      <summary>
                        {name} ({columns.length} columns)
                      </summary>
                      <pre className="at-note">{columns.join("\n")}</pre>
                    </details>
                  ))}
                </details>
              ))}
            </>
          )}
          <details className="at-freshness">
            <summary>Freshness and source status</summary>
            <p>
              Result assembled {result.fetched_at}. Successful NBA resources cached up to 15
              minutes; schedule up to 2 minutes. This is retrieval time, not a guarantee the
              provider has updated its statistics.
            </p>
            <ul>
              {Object.entries(result.resources).map(([name, resource]) => (
                <li key={name}>
                  {name}: {resource.state} · retrieved {resource.fetched_at}
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}
    </section>
  );
}
