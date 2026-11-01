import { useEffect, useState } from "react";
import { GameLogTable, StatDistribution, StatTrend } from "./PlayerAnalysis";
import {
  getPlayerProfile,
  searchPlayers,
  type PlayerProfile,
  type PlayerSearchResult,
} from "./player-browser-api";
import {
  PlayerSampleExplorer,
  PlayerSeasonMeasures,
  PlayerShootingBreakdowns,
} from "./PlayerProfileDetails";
import "./player-analysis.css";

// Content component: the shell owns tabs, season/phase selection, and URL state.
export interface PlayerBrowserProps {
  season: string;
  phase: string;
  playerId?: number;
  onPlayerSelect?: (playerId: number) => void;
}
const ADVANCED: Array<[string, string, boolean?]> = [
  ["OFF_RATING", "Offensive rating"],
  ["DEF_RATING", "Defensive rating"],
  ["NET_RATING", "Net rating"],
  ["USG_PCT", "Usage", true],
  ["AST_PCT", "Assist share", true],
  ["AST_TO", "Assists / turnover"],
  ["AST_RATIO", "Assists / 100 plays"],
  ["TM_TOV_PCT", "Turnover share", true],
  ["OREB_PCT", "Offensive rebound share", true],
  ["DREB_PCT", "Defensive rebound share", true],
  ["REB_PCT", "Rebound share", true],
  ["TS_PCT", "True shooting", true],
  ["EFG_PCT", "Effective FG", true],
  ["PACE", "Pace / 48 min"],
  ["POSS", "Possessions"],
  ["PIE", "PIE", true],
];
function value(input: unknown, percent = false) {
  if (input == null || input === "" || !Number.isFinite(Number(input))) return "—";
  return percent ? (Number(input) * 100).toFixed(1) + "%" : Number(input).toFixed(1);
}
export function PlayerBrowser({ season, phase, playerId, onPlayerSelect }: PlayerBrowserProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [selectedId, setSelectedId] = useState(playerId);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [searchError, setSearchError] = useState("");
  const [searchLoading, setSearchLoading] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setSelectedId(playerId);
  }, [playerId]);
  useEffect(() => {
    if (selectedId && !query.trim()) {
      setResults([]);
      setSearchLoading(false);
      setSearchError("");
      return;
    }
    const controller = new AbortController();
    setSearchLoading(true);
    const timer = setTimeout(() => {
      setSearchError("");
      searchPlayers(query, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted) setResults(data.players);
        })
        .catch((err) => {
          if (!controller.signal.aborted) setSearchError(String(err.message));
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearchLoading(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, selectedId]);
  useEffect(() => {
    if (!selectedId) {
      setProfile(null);
      setError("");
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setProfile(null);
    setError("");
    setLoading(true);
    getPlayerProfile(selectedId, season, phase, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setProfile(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(String(err.message));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [selectedId, season, phase, attempt]);
  return (
    <div className="player-analysis player-browser">
      <section className="player-analysis__section" aria-label="Player search">
        <label htmlFor="player-search">Search NBA players</label>
        <input
          id="player-search"
          type="search"
          value={query}
          placeholder="Name, e.g. Nikola Jokić"
          onChange={(e) => setQuery(e.target.value)}
        />
        {searchError && <p role="alert">{searchError}</p>}
        <ul className="player-browser__results" aria-label="Search results">
          {results.map((player) => (
            <li key={player.player_id}>
              <button
                type="button"
                aria-pressed={selectedId === player.player_id}
                onClick={() => {
                  setSelectedId(player.player_id);
                  onPlayerSelect?.(player.player_id);
                }}
              >
                {player.name} <small>{player.active ? "Active" : "Historical"}</small>
              </button>
            </li>
          ))}
        </ul>
        {searchLoading && <p role="status">Searching player directory…</p>}
        {!results.length && !searchError && !searchLoading && (!selectedId || query.trim()) && (
          <p role="status">No matching players in the bundled directory.</p>
        )}
        <small>
          Directory is bundled with nba_api; newly signed players may require a package update.
        </small>
      </section>
      {loading && <p role="status">Loading player season analysis…</p>}
      {error && <p role="alert">{error}</p>}
      {(error || profile?.advanced_state === "error" || profile?.history.state === "error") && (
        <button type="button" onClick={() => setAttempt((v) => v + 1)}>
          Retry player profile
        </button>
      )}
      {profile && (
        <PlayerProfileView
          key={`${profile.player_id}:${profile.season}:${profile.phase}`}
          profile={profile}
        />
      )}
    </div>
  );
}
export function PlayerProfileView({ profile }: { profile: PlayerProfile }) {
  const history = profile.history;
  return (
    <article className="player-analysis">
      <header>
        <h2>{profile.player_name}</h2>
        <p>
          {profile.season} · {profile.phase} · {history.games_played} logged games
        </p>
      </header>
      <section className="player-analysis__section">
        <h3>Season efficiency, usage &amp; impact</h3>
        <p className="player-analysis__formula">
          {profile.advanced_source} · GP {value(profile.advanced.GP)} · MPG{" "}
          {value(profile.advanced.MIN)}. Ratings are points per 100 possessions; pace is possessions
          per 48 minutes. These describe the on-court sample, not causal player impact.
        </p>
        {profile.advanced_state !== "available" ? (
          <p role={profile.advanced_state === "error" ? "alert" : "status"}>
            {profile.advanced_state === "error" ? "Request failed: " : "Unavailable: "}
            {profile.advanced_note}
          </p>
        ) : (
          <div className="player-analysis__advanced-grid">
            {ADVANCED.map(([key, label, percent]) => (
              <div
                key={key}
                className={`player-analysis__advanced-cell${key === "NET_RATING" && profile.advanced[key] != null ? (Number(profile.advanced[key]) > 0 ? " metric-positive" : Number(profile.advanced[key]) < 0 ? " metric-negative" : "") : ""}`}
              >
                <span>{label}</span>
                <strong>{value(profile.advanced[key], percent)}</strong>
              </div>
            ))}
          </div>
        )}
        <details>
          <summary>Metric definitions and sample limits</summary>
          <p>
            Usage is the share of team plays used while on court; assist and rebound shares use
            available team opportunities. PIE is the share of recorded game events. Net rating is
            offensive minus defensive rating. Percentages are displayed on a 0–100 scale. Season
            advanced totals are NBA supplied; unavailable fields stay blank. Regular season and
            playoffs are separate samples; historical endpoint coverage varies.
          </p>
        </details>
      </section>
      <section className="player-analysis__section">
        <h3>Shooting from season game totals</h3>
        <div className="player-analysis__advanced-grid">
          {[
            ["efg_pct", "eFG%"],
            ["ts_pct", "TS%"],
            ["fg3a_rate", "3P attempt rate"],
            ["fta_rate", "Free throw rate"],
          ].map(([key, label]) => (
            <div key={key} className="player-analysis__advanced-cell">
              <span>{label}</span>
              <strong>{value(profile.shooting[key]?.value, true)}</strong>
              <small>n = {profile.shooting[key]?.games ?? 0} complete games</small>
            </div>
          ))}
        </div>
        <p className="player-analysis__formula">
          Ratios of totals: eFG = (FGM + 0.5 × 3PM) / FGA; TS = PTS / [2 × (FGA + 0.44 × FTA)]; 3PAr
          = 3PA / FGA; FTr = FTA / FGA. Each metric uses only games with all required inputs. Zero
          denominator = unavailable. TS uses the conventional 0.44 free throw estimate.
        </p>
      </section>
      <PlayerSeasonMeasures profile={profile} />
      <PlayerShootingBreakdowns profile={profile} />
      <PlayerSampleExplorer profile={profile} />
      <section className="player-analysis__section">
        <h3>Season sample and consistency</h3>
        {history.state !== "available" ? (
          <p role={history.state === "error" ? "alert" : "status"}>{history.note}</p>
        ) : (
          <>
            <div className="player-analysis__visuals">
              <StatTrend rows={history.games} statLabel="Points" statKey="pts" />
              <StatDistribution rows={history.games} statLabel="Points" statKey="pts" />
            </div>
            <div className="player-analysis__table-wrap">
              <table className="player-analysis__table player-analysis__consistency-table">
                <thead>
                  <tr>
                    <th>Stat</th>
                    <th>Season</th>
                    <th>Last 5</th>
                    <th>Last 10</th>
                    <th>Last 20</th>
                    <th>Sample SD</th>
                    <th>CV</th>
                    <th>Valid games</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(history.summary).map(([key, row]) => (
                    <tr key={key}>
                      <th>{row.label}</th>
                      <td>{value(row.mean, /PCT|RATE/.test(key))}</td>
                      {[
                        [row.last_5, row.last_5_games],
                        [row.last_10, row.last_10_games],
                        [row.last_20, row.last_20_games],
                      ].map(([mean, games], i) => (
                        <td key={i}>
                          {value(mean, /PCT|RATE/.test(key))} <small>n={games ?? "—"}</small>
                        </td>
                      ))}
                      <td>{value(row.std, /PCT|RATE/.test(key))}</td>
                      <td>{value(row.consistency_cv, true)}</td>
                      <td>{row.games}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="player-analysis__formula">
              CV = sample SD (ddof=1) / mean for positive means; legacy convention reports 0 for
              nonpositive means. One valid game has SD 0. Recent windows use newest non-null values
              and show their sample counts. Percentage rows above are per-game means; shooting
              totals are shown separately.
            </p>
            <h3>
              Season game log · {profile.season} · {profile.phase}
            </h3>
            <GameLogTable
              rows={history.games}
              season={profile.season}
              phase={profile.phase}
              playerId={profile.player_id}
            />
          </>
        )}
      </section>
    </article>
  );
}
