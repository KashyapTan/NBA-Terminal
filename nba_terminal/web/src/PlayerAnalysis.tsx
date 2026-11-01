import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { PlayerAnalysis as PlayerAnalysisData, PlayerGameLogRow, PlayerLine } from "./model";
import type { GameAnalysisExtras } from "./player-browser-api";
import { ShotChart } from "./ShotChart";
import "./player-analysis.css";

const GAME_STATS: Array<[keyof PlayerLine, string]> = [
  ["min", "Minutes"],
  ["pts", "Points"],
  ["reb", "Rebounds"],
  ["ast", "Assists"],
  ["stl", "Steals"],
  ["blk", "Blocks"],
  ["tov", "Turnovers"],
  ["fgm", "Field goals made"],
  ["fga", "Field goal attempts"],
  ["fg3m", "3-pointers made"],
  ["fg3a", "3-point attempts"],
  ["ftm", "Free throws made"],
  ["fta", "Free throw attempts"],
  ["oreb", "Offensive rebounds"],
  ["dreb", "Defensive rebounds"],
  ["pf", "Fouls"],
  ["plus_minus", "+ / −"],
];

const ADVANCED_STATS: Array<[string, string, boolean?]> = [
  ["ts_pct", "True shooting %", true],
  ["efg_pct", "Effective FG %", true],
  ["usg_pct", "Usage %", true],
  ["off_rating", "Offensive rating"],
  ["def_rating", "Defensive rating"],
  ["net_rating", "Net rating"],
  ["ast_pct", "Assist %", true],
  ["ast_to", "Assist / turnover"],
  ["ast_ratio", "Assist ratio"],
  ["oreb_pct", "Offensive reb. %", true],
  ["dreb_pct", "Defensive reb. %", true],
  ["reb_pct", "Rebound %", true],
  ["tov_ratio", "Turnovers / 100 plays"],
  ["pace", "Pace"],
  ["poss", "Possessions"],
  ["pie", "Player impact %", true],
];

const STAT_OPTIONS: Array<{ key: keyof PlayerGameLogRow; label: string; defaultLine: number }> = [
  { key: "pts", label: "Points", defaultLine: 20 },
  { key: "reb", label: "Rebounds", defaultLine: 6 },
  { key: "ast", label: "Assists", defaultLine: 5 },
  { key: "pra", label: "Points + rebounds + assists", defaultLine: 30 },
  { key: "pr", label: "Points + rebounds", defaultLine: 25 },
  { key: "pa", label: "Points + assists", defaultLine: 25 },
  { key: "ra", label: "Rebounds + assists", defaultLine: 12 },
  { key: "stl", label: "Steals", defaultLine: 1 },
  { key: "blk", label: "Blocks", defaultLine: 1 },
  { key: "fg3m", label: "Three-pointers made", defaultLine: 2 },
  { key: "stocks", label: "Steals + blocks", defaultLine: 2 },
];

const LOG_COLUMNS: Array<[keyof PlayerGameLogRow, string, boolean?]> = [
  ["game_date", "Date"],
  ["matchup", "Matchup"],
  ["wl", "W/L"],
  ["min", "MIN"],
  ["pts", "PTS"],
  ["reb", "REB"],
  ["ast", "AST"],
  ["pra", "PRA"],
  ["stl", "STL"],
  ["blk", "BLK"],
  ["tov", "TOV"],
  ["fgm", "FGM"],
  ["fga", "FGA"],
  ["fg_pct", "FG%", true],
  ["fg3m", "3PM"],
  ["fg3a", "3PA"],
  ["fg3_pct", "3P%", true],
  ["ft_pct", "FT%", true],
  ["efg_pct", "eFG%", true],
  ["ts_pct", "TS%", true],
  ["fg3a_rate", "3PAr", true],
  ["fta_rate", "FTr", true],
  ["pts_per_fga", "PTS/FGA"],
  ["plus_minus", "+/−"],
];

function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value: unknown, decimals = 1) {
  const parsed = numberValue(value);
  if (parsed === null) return "—";
  return Number.isInteger(parsed) ? String(parsed) : parsed.toFixed(decimals);
}

function formatPercent(value: unknown) {
  const parsed = numberValue(value);
  return parsed === null ? "—" : (parsed * 100).toFixed(1) + "%";
}

function formatMinutes(value: unknown) {
  if (typeof value === "string" && value.includes(":")) return value;
  const parsed = numberValue(value);
  if (parsed === null) return "—";
  const totalSeconds = Math.round(parsed * 60);
  return Math.floor(totalSeconds / 60) + ":" + String(totalSeconds % 60).padStart(2, "0");
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Game date unavailable";
  const parsed = new Date(value + "T12:00:00");
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

function metricValue(key: keyof PlayerGameLogRow, row: PlayerGameLogRow) {
  return numberValue(row[key]);
}

function gameStatValue(key: keyof PlayerGameLogRow, player: PlayerLine) {
  const direct = numberValue(player[key]);
  if (direct !== null) return direct;
  const parts: Partial<Record<keyof PlayerGameLogRow, Array<keyof PlayerLine>>> = {
    pra: ["pts", "reb", "ast"],
    pr: ["pts", "reb"],
    pa: ["pts", "ast"],
    ra: ["reb", "ast"],
    stocks: ["stl", "blk"],
  };
  const fields = parts[key];
  if (!fields) return null;
  const values = fields.map((field) => numberValue(player[field]));
  return values.every((value): value is number => value !== null)
    ? values.reduce((sum, value) => sum + value, 0)
    : null;
}

function average(rows: PlayerGameLogRow[], key: keyof PlayerGameLogRow) {
  const values = rows
    .map((row) => metricValue(key, row))
    .filter((value): value is number => value !== null);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function countValues(rows: PlayerGameLogRow[], key: keyof PlayerGameLogRow) {
  return rows.filter((row) => metricValue(key, row) !== null).length;
}

function AvailabilityNote({
  title,
  note,
  error = false,
}: {
  title: string;
  note: string;
  error?: boolean;
}) {
  return (
    <div
      className={"player-analysis__notice" + (error ? " is-error" : "")}
      role={error ? "alert" : "status"}
    >
      <span className="player-analysis__notice-mark" aria-hidden="true">
        {error ? "!" : "i"}
      </span>
      <span>
        <strong>{title}</strong>
        {note}
      </span>
    </div>
  );
}

export function StatTrend({
  rows,
  statLabel,
  statKey,
}: {
  rows: PlayerGameLogRow[];
  statLabel: string;
  statKey: keyof PlayerGameLogRow;
}) {
  const points = rows
    .slice(0, 10)
    .reverse()
    .map((row) => ({ row, value: metricValue(statKey, row) }))
    .filter((item): item is { row: PlayerGameLogRow; value: number } => item.value !== null);
  if (!points.length) {
    return (
      <p className="player-analysis__formula">
        Trend unavailable: this stat has no game-log values.
      </p>
    );
  }
  const values = points.map((item) => item.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const coords = values.map((value, index) => ({
    x: points.length === 1 ? 160 : 12 + (index * 296) / (points.length - 1),
    y: 82 - ((value - min) / span) * 62,
  }));
  const polyline = coords.map((point) => point.x + "," + point.y).join(" ");
  const averageValue = values.reduce((sum, value) => sum + value, 0) / values.length;
  const averageY = 82 - ((averageValue - min) / span) * 62;
  const firstDate = points[0]?.row.game_date || "Older game";
  const lastDate = points[points.length - 1]?.row.game_date || "Recent game";
  return (
    <div className="player-analysis__trend">
      <div className="player-analysis__trend-label">
        <span>{statLabel} · recent games</span>
        <b>Avg {formatNumber(averageValue)}</b>
      </div>
      <svg
        viewBox="0 0 320 100"
        role="img"
        aria-label={statLabel + " trend over " + points.length + " recent games"}
        preserveAspectRatio="xMidYMid meet"
      >
        <line className="player-analysis__trend-grid" x1="8" x2="312" y1={averageY} y2={averageY} />
        <polyline className="player-analysis__trend-line" points={polyline} />
        {coords.map((point, index) => (
          <circle
            className="player-analysis__trend-point"
            cx={point.x}
            cy={point.y}
            r="3"
            key={index}
          >
            <title>
              {formatDate(points[index]?.row.game_date)}: {formatNumber(points[index]?.value)}
            </title>
          </circle>
        ))}
      </svg>
      <div className="player-analysis__trend-dates">
        <span>{formatDate(firstDate)}</span>
        <span>{formatDate(lastDate)}</span>
      </div>
    </div>
  );
}

export function StatDistribution({
  rows,
  statLabel,
  statKey,
}: {
  rows: PlayerGameLogRow[];
  statLabel: string;
  statKey: keyof PlayerGameLogRow;
}) {
  const values = rows
    .map((row) => metricValue(statKey, row))
    .filter((value): value is number => value !== null);
  if (values.length < 2) {
    return (
      <div className="player-analysis__distribution">
        <div className="player-analysis__trend-label">
          <span>{statLabel} · game distribution</span>
          <b>n = {values.length}</b>
        </div>
        <p className="player-analysis__formula">
          Distribution unavailable: at least two valid game values are needed.
        </p>
      </div>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  const binCount = range === 0 ? 1 : Math.min(6, Math.max(2, Math.ceil(Math.sqrt(values.length))));
  const binWidth = range === 0 ? 1 : range / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => {
    const start = min + index * binWidth;
    const end = index === binCount - 1 ? max : min + (index + 1) * binWidth;
    const count = values.filter((value) =>
      index === binCount - 1 ? value >= start && value <= end : value >= start && value < end,
    ).length;
    return { start, end, count };
  });
  const maxCount = Math.max(...bins.map((bin) => bin.count));
  const barWidth = 260 / binCount;

  return (
    <div className="player-analysis__distribution">
      <div className="player-analysis__trend-label">
        <span>{statLabel} · sample game distribution</span>
        <b>n = {values.length}</b>
      </div>
      <svg
        viewBox="0 0 320 110"
        role="img"
        aria-label={statLabel + " distribution across " + values.length + " games"}
        preserveAspectRatio="xMidYMid meet"
      >
        <line className="player-analysis__distribution-axis" x1="24" x2="296" y1="78" y2="78" />
        {bins.map((bin, index) => {
          const height = (bin.count / maxCount) * 58;
          const x = 30 + index * barWidth;
          const label =
            range === 0 ? formatNumber(min) : formatNumber(bin.start) + "–" + formatNumber(bin.end);
          return (
            <g key={label + ":" + index}>
              <rect
                className="player-analysis__distribution-bar"
                x={x}
                y={78 - height}
                width={Math.max(8, barWidth - 7)}
                height={height}
                rx="3"
              >
                <title>
                  {label}: {bin.count} games
                </title>
              </rect>
              <text className="player-analysis__distribution-label" x={x + barWidth / 2} y="98">
                {label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function GameLogTable({
  rows,
  season,
  phase,
  playerId,
}: {
  rows: PlayerGameLogRow[];
  season: string;
  phase: string;
  playerId?: number;
}) {
  return (
    <div
      className="player-analysis__table-wrap"
      role="region"
      aria-label="Season game log"
      tabIndex={0}
    >
      <table className="player-analysis__table">
        <thead>
          <tr>
            {LOG_COLUMNS.map(([, label]) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={(row.game_id || "game") + ":" + index}>
              {LOG_COLUMNS.map(([key, , percent]) => {
                const value =
                  key === "game_date"
                    ? row.game_date || "—"
                    : key === "matchup"
                      ? row.matchup || "—"
                      : key === "wl"
                        ? row.wl || "—"
                        : key === "min"
                          ? formatMinutes(row.min)
                          : percent
                            ? formatPercent(row[key])
                            : formatNumber(row[key], 2);
                return (
                  <td key={key}>
                    {key === "game_date" && row.game_id ? (
                      <Link
                        to={
                          "/game/" +
                          encodeURIComponent(String(row.game_id).padStart(10, "0")) +
                          "?" +
                          new URLSearchParams({
                            season,
                            phase,
                            ...(playerId ? { player: String(playerId) } : {}),
                          }).toString()
                        }
                        aria-label={
                          "Open box score " +
                          row.game_date +
                          " " +
                          (row.matchup || "") +
                          " · " +
                          season +
                          " · " +
                          phase
                        }
                      >
                        {value}
                      </Link>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GameContext({ analysis }: { analysis: PlayerAnalysisData }) {
  const context = analysis.game_context;
  const team = context.team || analysis.player.team;
  const opponent = context.opponent;
  const matchup =
    context.matchup ||
    (team?.abbreviation && opponent?.abbreviation
      ? team.abbreviation + (context.result === "W" ? " beat " : " vs. ") + opponent.abbreviation
      : "Matchup detail unavailable");
  const hasScore = context.team_score != null && context.opponent_score != null;
  return (
    <div className="player-analysis__context">
      <b>{formatDate(context.game_date)}</b>
      <span>{matchup}</span>
      {hasScore && (
        <span className="is-final">
          {team?.abbreviation || "Team"} {formatNumber(context.team_score, 0)} —{" "}
          {opponent?.abbreviation || "Opponent"} {formatNumber(context.opponent_score, 0)}
        </span>
      )}
      {context.result && <span className="player-analysis__result">{context.result}</span>}
      <span>
        GAME {analysis.game_id} · {context.phase || "Phase unavailable"}
      </span>
    </div>
  );
}

export function PlayerAnalysisView({
  analysis,
  season,
  phase,
}: {
  analysis: PlayerAnalysisData;
  season: string;
  phase: string;
}) {
  const player = analysis.player;
  const derivedShooting = (analysis as PlayerAnalysisData & GameAnalysisExtras)
    .derived_game_shooting;
  const playerName = player.player_name || "Player";
  const history = analysis.history;
  const [statKey, setStatKey] = useState<keyof PlayerGameLogRow>("pts");
  const [line, setLine] = useState(20);
  const [sampleSize, setSampleSize] = useState("10");
  const selectedStat = STAT_OPTIONS.find((stat) => stat.key === statKey) || STAT_OPTIONS[0];
  const seasonRows = history.state === "available" ? history.games : [];
  const opponentRows = history.state === "available" ? history.opponent_games : [];
  const sampleRows = useMemo(
    () => (sampleSize === "season" ? seasonRows : seasonRows.slice(0, Number(sampleSize))),
    [seasonRows, sampleSize],
  );
  const hitValues = sampleRows
    .map((row) => metricValue(statKey, row))
    .filter((value): value is number => value !== null);
  const hitCount = hitValues.filter((value) => value >= line).length;
  const hitRate = hitValues.length ? (hitCount / hitValues.length) * 100 : null;
  const seasonAverage = average(seasonRows, statKey);
  const opponentAverage = average(opponentRows, statKey);
  const seasonStatCount = countValues(seasonRows, statKey);
  const opponentStatCount = countValues(opponentRows, statKey);
  const gameValue = gameStatValue(statKey, player);
  const statLabel = selectedStat.label;
  const initials = playerName
    .split(" ")
    .map((word) => word.charAt(0))
    .slice(0, 2)
    .join("");

  return (
    <div className="player-analysis">
      <div>
        <div className="player-analysis__back-row">
          <Link
            to={
              "/game/" +
              encodeURIComponent(analysis.game_id) +
              "?season=" +
              encodeURIComponent(season) +
              "&phase=" +
              encodeURIComponent(phase)
            }
          >
            ← Game box score
          </Link>
          <span>{phase}</span>
        </div>
        <section className="player-analysis__heading">
          <div className="player-analysis__avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="player-analysis__heading-copy">
            <div className="player-analysis__eyebrow">PLAYER GAME ANALYSIS</div>
            <h1>{playerName}</h1>
            <p>
              {player.team?.name || "Team unavailable"} · {season} season
            </p>
          </div>
          <span className="player-analysis__team">{player.team?.abbreviation || "NBA"}</span>
        </section>
      </div>

      <GameContext analysis={analysis} />

      <section className="player-analysis__section">
        <div className="player-analysis__section-heading">
          <div>
            <div className="player-analysis__section-kicker">BOX SCORE</div>
            <h2>Selected game stats</h2>
          </div>
          <p>Single game · {analysis.game_id}</p>
        </div>
        <div className="player-analysis__table-wrap">
          <table
            className="player-analysis__table player-analysis__game-line"
            aria-label="Selected game stats"
          >
            <thead>
              <tr>
                {GAME_STATS.map(([key, label]) => (
                  <th key={key}>{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {GAME_STATS.map(([key]) => (
                  <td key={key}>
                    {key === "min" ? formatMinutes(player[key]) : formatNumber(player[key])}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="player-analysis__section">
        <div className="player-analysis__section-heading">
          <div>
            <div className="player-analysis__section-kicker">ADVANCED BOX SCORE</div>
            <h2>Game-level efficiency &amp; impact</h2>
          </div>
          <p>BoxScoreAdvancedV3 · this game only</p>
        </div>
        {analysis.advanced_stats_state === "available" ? (
          <div className="player-analysis__panel player-analysis__advanced">
            <div className="player-analysis__advanced-grid">
              {ADVANCED_STATS.map(([key, label, percent]) => {
                const value = analysis.advanced_stats[key];
                return value == null ? null : (
                  <div className="player-analysis__advanced-cell" key={key}>
                    <span>{label}</span>
                    <strong>{percent ? formatPercent(value) : formatNumber(value)}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <AvailabilityNote
            title={
              analysis.advanced_stats_state === "error"
                ? "Advanced stats request failed"
                : "Advanced stats unavailable"
            }
            note={analysis.advanced_stats_note}
            error={analysis.advanced_stats_state === "error"}
          />
        )}
      </section>

      {derivedShooting && (
        <section className="player-analysis__section" aria-label="Derived selected game shooting">
          <h3>Selected game shooting rates</h3>
          <p className="player-analysis__formula">
            Derived from the traditional box score, independently of advanced endpoint availability.
          </p>
          <div className="player-analysis__advanced-grid">
            {[
              ["efg_pct", "eFG%"],
              ["ts_pct", "TS%"],
              ["fg3a_rate", "3P attempt rate"],
              ["fta_rate", "Free throw rate"],
            ].map(([key, label]) => (
              <div className="player-analysis__advanced-cell" key={key}>
                <span>{label}</span>
                <strong>{formatPercent(derivedShooting[key]?.value)}</strong>
              </div>
            ))}
          </div>
        </section>
      )}
      <p className="player-analysis__formula">
        Ratings: points per 100 possessions while on court; net = offensive − defensive rating.
        Pace: possessions per 48 minutes. Usage: share of team plays used while on court. PIE: share
        of recorded game events, not a causal impact estimate. Assist and turnover ratios are per
        100 plays; percentages are shown on a 0–100 scale. Missing metrics stay blank. Derived log
        rates: eFG = (FGM + 0.5 × 3PM) / FGA; TS = PTS / [2 × (FGA + 0.44 × FTA)]; 3PAr = 3PA / FGA;
        FTr = FTA / FGA. Zero denominators are unavailable.
      </p>
      <section className="player-analysis__section">
        <div className="player-analysis__section-heading">
          <div>
            <div className="player-analysis__section-kicker">SHOT LOCATIONS</div>
            <h2>Shot chart</h2>
          </div>
          <p>Selected game · real coordinates only</p>
        </div>
        <ShotChart analysis={analysis} />
      </section>

      <section className="player-analysis__section">
        <div className="player-analysis__section-heading">
          <div>
            <div className="player-analysis__section-kicker">SEASON GAME LOG</div>
            <h2>Historical sample &amp; opponent comparison</h2>
          </div>
          <p>
            {history.state === "available"
              ? history.games_played + " games in " + history.season
              : history.season + " · " + history.state}
          </p>
        </div>
        {history.state !== "available" ? (
          <AvailabilityNote
            title={
              history.state === "error"
                ? "Season game logs could not be loaded"
                : "Season game logs unavailable"
            }
            note={history.note}
            error={history.state === "error"}
          />
        ) : (
          <div className="player-analysis__history">
            <div className="player-analysis__history-top">
              <div className="player-analysis__history-controls">
                <label>
                  Stat
                  <select
                    value={statKey}
                    aria-label="Historical stat"
                    onChange={(event) => {
                      const next = STAT_OPTIONS.find((item) => item.key === event.target.value);
                      if (next) {
                        setStatKey(next.key);
                        setLine(next.defaultLine);
                      }
                    }}
                  >
                    {STAT_OPTIONS.map((item) => (
                      <option value={item.key} key={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Line
                  <input
                    aria-label="Stat line"
                    type="number"
                    min="0"
                    step="0.5"
                    value={line}
                    onChange={(event) => setLine(Number(event.target.value))}
                  />
                </label>
                <label>
                  Sample
                  <select
                    aria-label="Historical sample size"
                    value={sampleSize}
                    onChange={(event) => setSampleSize(event.target.value)}
                  >
                    <option value="5">Last 5</option>
                    <option value="10">Last 10</option>
                    <option value="15">Last 15</option>
                    <option value="20">Last 20</option>
                    <option value="season">Season</option>
                  </select>
                </label>
              </div>
              <div className="player-analysis__hit-rate" role="status" aria-live="polite">
                <strong>{hitRate == null ? "—" : hitRate.toFixed(0) + "%"}</strong>
                <span>
                  {statLabel} {line}+ hit rate
                  <br />
                  {hitCount} / {hitValues.length} available games · at or above line
                </span>
              </div>
            </div>

            <div className="player-analysis__comparison" aria-label={statLabel + " comparison"}>
              <div className="player-analysis__comparison-card">
                <span>Selected game · {statLabel}</span>
                <strong>{formatNumber(gameValue)}</strong>
                <small>
                  {seasonAverage == null || gameValue == null
                    ? "Season comparison unavailable"
                    : (gameValue - seasonAverage >= 0 ? "+" : "") +
                      formatNumber(gameValue - seasonAverage) +
                      " vs season average"}
                </small>
              </div>
              <div className="player-analysis__comparison-card">
                <span>
                  {history.season} average · {statLabel}
                </span>
                <strong>{formatNumber(seasonAverage)}</strong>
                <small>n = {seasonStatCount} games</small>
              </div>
              <div className="player-analysis__comparison-card">
                <span>
                  {history.opponent || "Opponent"} average · {statLabel}
                </span>
                <strong>{formatNumber(opponentAverage)}</strong>
                <small>
                  {opponentAverage == null
                    ? "No opponent sample returned"
                    : "n = " +
                      opponentStatCount +
                      " games" +
                      (seasonAverage == null
                        ? ""
                        : " · " +
                          (opponentAverage - seasonAverage >= 0 ? "+" : "") +
                          formatNumber(opponentAverage - seasonAverage) +
                          " vs season")}
                </small>
              </div>
            </div>

            <div className="player-analysis__visuals">
              <StatTrend rows={seasonRows} statLabel={statLabel} statKey={statKey} />
              <StatDistribution rows={seasonRows} statLabel={statLabel} statKey={statKey} />
            </div>

            <div className="player-analysis__subsection-heading">
              <div>
                <div className="player-analysis__section-kicker">ORIGINAL CONSISTENCY METRIC</div>
                <h3>Coefficient of variation</h3>
              </div>
              <p>Lower CV means less variation relative to the player’s average.</p>
            </div>
            <p className="player-analysis__formula">
              CV = sample standard deviation ÷ mean when mean &gt; 0, otherwise 0. Sample SD uses
              ddof=1. L5/L10/L20 averages use the newest valid game values for this season and
              phase; each window shows its non-null sample count.
            </p>
            <div
              className="player-analysis__table-wrap player-analysis__consistency-wrap"
              role="region"
              aria-label="Season consistency by stat"
              tabIndex={0}
            >
              <table className="player-analysis__table player-analysis__consistency-table">
                <thead>
                  <tr>
                    <th>STAT</th>
                    <th>SEASON AVG</th>
                    <th>L5 AVG</th>
                    <th>L10 AVG</th>
                    <th>L20 AVG</th>
                    <th>SAMPLE SD</th>
                    <th>CV</th>
                    <th>GAMES</th>
                  </tr>
                </thead>
                <tbody>
                  {["PTS", "REB", "AST", "STL", "BLK", "FG3M", "PRA"].map((key) => {
                    const item = history.summary[key];
                    const recent = [
                      { mean: item?.last_5, games: item?.last_5_games },
                      { mean: item?.last_10, games: item?.last_10_games },
                      { mean: item?.last_20, games: item?.last_20_games },
                    ];
                    return (
                      <tr key={key}>
                        <td>{item?.label || key}</td>
                        <td>{formatNumber(item?.mean)}</td>
                        {recent.map((window, index) => (
                          <td className="player-analysis__window-cell" key={index}>
                            <strong>{formatNumber(window.mean)}</strong>
                            <small>n = {window.games ?? "—"}</small>
                          </td>
                        ))}
                        <td>{formatNumber(item?.std)}</td>
                        <td>{formatPercent(item?.consistency_cv)}</td>
                        <td>{item?.games ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="player-analysis__subsection-heading">
              <div>
                <div className="player-analysis__section-kicker">PER-GAME RESULTS</div>
                <h3>Season game log</h3>
              </div>
              <p>Traditional box score plus derived shooting efficiency.</p>
            </div>
            <GameLogTable
              rows={seasonRows}
              season={season}
              phase={phase}
              playerId={player.player_id}
            />

            {opponentRows.length > 0 && (
              <details className="player-analysis__opponent-details">
                <summary>
                  {history.opponent} game log · {opponentRows.length} games
                </summary>
                <GameLogTable
                  rows={opponentRows}
                  season={season}
                  phase={phase}
                  playerId={player.player_id}
                />
              </details>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
