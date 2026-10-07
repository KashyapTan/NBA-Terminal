import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link, Route, Routes, useLocation, useParams, useSearchParams } from "react-router-dom";
import { getGame, getGames, getMeta, getPlayerAnalysis, getUpcoming } from "./api";
import type {
  BoxScore,
  Game,
  GamesResponse,
  Meta,
  PlayerAnalysis,
  PlayerLine,
  UpcomingResponse,
} from "./model";

type MetaState = { meta: Meta | null; error: string | null };
const MetaContext = createContext<MetaState>({ meta: null, error: null });

export function MetaProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<MetaState>({ meta: null, error: null });
  useEffect(() => {
    let active = true;
    getMeta()
      .then((meta) => {
        if (active) setState({ meta, error: null });
      })
      .catch((error: Error) => {
        if (active) setState({ meta: null, error: error.message });
      });
    return () => {
      active = false;
    };
  }, []);
  return <MetaContext.Provider value={state}>{children}</MetaContext.Provider>;
}

function useMeta() {
  return useContext(MetaContext);
}

export function LoadingState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" />
      <div>
        <b>{title}</b>
        <p>{detail}</p>
      </div>
    </div>
  );
}

export function ErrorState({
  title,
  detail,
  retry,
}: {
  title: string;
  detail: string;
  retry?: () => void;
}) {
  return (
    <section className="state-card error-state" role="alert">
      <span className="state-icon">!</span>
      <h2>{title}</h2>
      <p>{detail}</p>
      {retry && (
        <button type="button" className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
    </section>
  );
}

function EmptyState({
  icon,
  title,
  detail,
  warning = false,
}: {
  icon: string;
  title: string;
  detail: string;
  warning?: boolean;
}) {
  return (
    <div className={`empty-inline${warning ? " warning" : ""}`}>
      <span className="empty-icon">{icon}</span>
      <span>
        <b>{title}</b>
        <small>{detail}</small>
      </span>
    </div>
  );
}

function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const label = location.pathname.includes("/player/")
    ? "Player Game Analysis"
    : location.pathname.startsWith("/game/")
      ? "Game Box Score"
      : "Game Center";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="NBA Terminal home">
          <span className="brand-mark">N</span>
          <span>
            NBA <b>TERMINAL</b>
          </span>
        </Link>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          <Link className="nav-item active" to="/" aria-current="page">
            <span className="nav-icon">▦</span> Game Center
          </Link>
        </nav>
        <div className="sidebar-foot">
          <span className="pulse" />
          NBA Stats connection
          <br />
          <small>Live source · cached reads</small>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="crumb">
            <span>NBA TERMINAL</span>
            <i>/</i>
            <b>{label}</b>
          </div>
          <div className="season-chip">
            <span className="pulse" />
            <span>NBA Stats</span>
          </div>
        </header>
        <div className="view" aria-live="polite">
          {children}
        </div>
        <footer>Data from NBA Stats · Schedule and historical coverage can vary by season</footer>
      </main>
    </div>
  );
}

function TeamBadge({
  team,
  large = false,
}: {
  team: Game["home_team"] | PlayerLine["team"];
  large?: boolean;
}) {
  return (
    <span className={`team-badge${large ? " large" : ""}`}>{team?.abbreviation || "NBA"}</span>
  );
}

function GameCard({ game, upcoming, season }: { game: Game; upcoming?: boolean; season: string }) {
  const dateText = new Date(`${game.date}T12:00:00`).toLocaleDateString(undefined, {
    weekday: upcoming ? "short" : undefined,
    month: "short",
    day: "numeric",
  });
  const phase = game.phase;
  return (
    <Link
      className={`game-card${upcoming ? " upcoming-card" : ""}`}
      to={`/game/${encodeURIComponent(game.game_id)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(game.phase)}`}
      aria-label={`Open ${game.away_team.name} at ${game.home_team.name}`}
    >
      <span className="game-meta">
        <span>{dateText}</span>
        <span className="phase-tag">{phase}</span>
      </span>
      <span className="matchup">
        <span className="team-side">
          <TeamBadge team={game.away_team} />
          <span className="team-name">{game.away_team.name}</span>
          {!upcoming && <b className="score">{format(game.away_score)}</b>}
        </span>
        <span className="team-side">
          <TeamBadge team={game.home_team} />
          <span className="team-name">{game.home_team.name}</span>
          {!upcoming && <b className="score">{format(game.home_score)}</b>}
        </span>
      </span>
      <span className="game-status">
        <i className={`status-dot ${upcoming ? "scheduled" : "final"}`} />
        {upcoming ? `${game.status}${game.start_time ? ` · ${game.start_time}` : ""}` : game.status}
        <span className="arrow">↗</span>
      </span>
    </Link>
  );
}

function Dashboard() {
  const { meta } = useMeta();
  const [search, setSearch] = useSearchParams();
  const requestedSeason = search.get("season");
  const season =
    requestedSeason && meta?.seasons.includes(requestedSeason)
      ? requestedSeason
      : meta?.current_season || "";
  const [upcoming, setUpcoming] = useState<UpcomingResponse | null>(null);
  const [upcomingError, setUpcomingError] = useState<string | null>(null);
  const [result, setResult] = useState<GamesResponse | null>(null);
  const [gamesError, setGamesError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setUpcoming(null);
    setUpcomingError(null);
    setResult(null);
    setGamesError(null);
    Promise.allSettled([getUpcoming(), getGames(season)]).then(([next, games]) => {
      if (!active) return;
      if (next.status === "fulfilled") setUpcoming(next.value);
      else
        setUpcomingError(
          next.reason instanceof Error ? next.reason.message : "Schedule request failed.",
        );
      if (games.status === "fulfilled") setResult(games.value);
      else
        setGamesError(
          games.reason instanceof Error ? games.reason.message : "Game history request failed.",
        );
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [season, attempt]);

  if (!meta) return <LoadingState title="Game Center" detail="Loading season options" />;
  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">NBA · GAME CENTER</div>
          <h1>
            Every game, <em>in focus.</em>
          </h1>
          <p>Schedules, final scores and box scores from NBA Stats.</p>
        </div>
        <label className="season-select-label">
          SEASON
          <select
            aria-label="Season"
            value={season}
            onChange={(event) =>
              setSearch(event.target.value ? { season: event.target.value } : {})
            }
          >
            {meta.seasons.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">UP NEXT</div>
            <h2>Next two days</h2>
          </div>
          <span className="section-note">
            {upcoming?.games.length ? `${upcoming.games.length} scheduled` : "Today + tomorrow"}
          </span>
        </div>
        {loading ? (
          <LoadingState title="Upcoming games" detail="Checking today's and tomorrow's schedule" />
        ) : upcomingError ? (
          <EmptyState icon="!" title="Schedule unavailable" detail={upcomingError} warning />
        ) : upcoming?.games.length ? (
          <div className="games-grid">
            {upcoming.games.map((game) => (
              <GameCard key={game.game_id} game={game} upcoming season={season} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon="◷"
            title="No games scheduled in this two-day window"
            detail="The schedule can change as the league updates its feed."
          />
        )}
      </section>
      <section className="section-block feed-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">RECENT RESULTS</div>
            <h2>{season} season</h2>
          </div>
          <span className="phase-legend">
            <i />
            Preseason <i />
            Regular season <i />
            Playoffs
          </span>
        </div>
        {loading ? (
          <LoadingState title="Recent results" detail="Loading completed games" />
        ) : gamesError ? (
          <ErrorState
            title="Game history unavailable"
            detail={gamesError}
            retry={() => setAttempt((value) => value + 1)}
          />
        ) : result && !result.supported ? (
          <EmptyState
            icon="i"
            title="History is not available in this view"
            detail={`NBA Stats game feeds are supported here from ${meta.supported_from} onward.`}
            warning
          />
        ) : result?.games.length ? (
          <div className="games-grid">
            {result.games.map((game) => (
              <GameCard key={game.game_id} game={game} season={season} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon="◌"
            title="No completed games returned"
            detail="This season phase may not have started, or the source has no rows yet."
          />
        )}
      </section>
    </>
  );
}

const statColumns = [
  "min",
  "pts",
  "reb",
  "ast",
  "stl",
  "blk",
  "tov",
  "fgm",
  "fga",
  "fg3m",
  "fg3a",
  "ftm",
  "fta",
  "plus_minus",
] as const;
function format(value: unknown): string | number {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(1);
  return value as string | number;
}

function GameDetails() {
  const { gameId = "" } = useParams();
  const { meta } = useMeta();
  const [search] = useSearchParams();
  const season = search.get("season") || meta?.current_season || "";
  const phase = search.get("phase") || "Game";
  const [box, setBox] = useState<BoxScore | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getGame(gameId)
      .then((data) => {
        if (active) setBox(data);
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [gameId, attempt]);
  if (loading)
    return <LoadingState title="Game box score" detail="Loading team and player lines" />;
  if (error)
    return (
      <>
        <BackLink season={season} />
        <ErrorState
          title="Box score unavailable"
          detail={error}
          retry={() => setAttempt((value) => value + 1)}
        />
      </>
    );
  const boxTeams = box?.teams || [];
  const teamNames = boxTeams
    .map((item) => item.team?.name)
    .filter((name): name is string => Boolean(name));
  const players = [...(box?.players || [])].sort(
    (a, b) => (Number(b.pts) || 0) - (Number(a.pts) || 0),
  );
  return (
    <>
      <BackLink season={season} phase={phase} />
      <section className="detail-heading">
        <div>
          <div className="eyebrow">GAME BOX SCORE · {gameId}</div>
          <h1>{teamNames.join(" at ") || `Game ${gameId}`}</h1>
          <p>Player stats for this matchup. Select any player for their game analysis.</p>
        </div>
      </section>
      <section className="section-block score-summary">
        {boxTeams.length ? (
          boxTeams.map((team, index) => (
            <div className="score-team" key={team.team?.id ?? index}>
              <TeamBadge team={team.team} large />
              <b>{team.team?.name || "Team"}</b>
              <strong>{format(team.pts)}</strong>
            </div>
          ))
        ) : (
          <span className="section-note">Team score not provided</span>
        )}
        <span className="vs">FINAL</span>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">PLAYER LINES</div>
            <h2>Box score</h2>
          </div>
          <span className="section-note">{players.length} players</span>
        </div>
        {players.length ? (
          <div className="table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>PLAYER</th>
                  {statColumns.map((key) => (
                    <th key={key}>{key.toUpperCase().replace("PLUS_MINUS", "+/-")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {players.map((player) => (
                  <tr key={player.player_id}>
                    <td>
                      <Link
                        className="player-link"
                        to={`/game/${encodeURIComponent(gameId)}/player/${encodeURIComponent(player.player_id)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(phase)}`}
                      >
                        {player.player_name || "Player"}
                      </Link>
                      <small>
                        {player.team?.abbreviation || ""}
                        {player.starter ? " · Starter" : ""}
                      </small>
                    </td>
                    {statColumns.map((key) => (
                      <td key={key}>{format(player[key])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon="◌"
            title="Box score not available"
            detail="NBA Stats returned no player rows for this game."
          />
        )}
      </section>
    </>
  );
}

function BackLink({ season, phase }: { season: string; phase?: string }) {
  return (
    <div className="back-row">
      <Link to={`/?season=${encodeURIComponent(season)}`}>← All games</Link>
      {phase && <span className="phase-tag">{phase}</span>}
    </div>
  );
}

const keyStats = [
  ["min", "Minutes"],
  ["pts", "Points"],
  ["reb", "Rebounds"],
  ["ast", "Assists"],
  ["stl", "Steals"],
  ["blk", "Blocks"],
  ["tov", "Turnovers"],
  ["fgm", "Field goals"],
  ["fg3m", "3-pointers"],
  ["ftm", "Free throws"],
  ["oreb", "Off. rebounds"],
  ["dreb", "Def. rebounds"],
  ["pf", "Fouls"],
  ["plus_minus", "+ / −"],
] as const;

function ShotChart({ analysis }: { analysis: PlayerAnalysis }) {
  if (analysis.shot_chart_state !== "available" || !analysis.shots.length) {
    const failed = analysis.shot_chart_state === "error";
    return (
      <div className="chart-unavailable">
        <span className="empty-icon">⌖</span>
        <b>{failed ? "Shot chart could not be loaded" : "Shot chart unavailable"}</b>
        <p>
          {failed
            ? "The box score loaded, but NBA Stats did not return shot chart data. Retry later; no locations are estimated."
            : "NBA Stats did not provide shot coordinates for this player and game. No locations are estimated."}
        </p>
      </div>
    );
  }
  const points = analysis.shots.map((shot, index) => {
    const x = Math.max(6, Math.min(494, 250 + shot.x));
    const y = Math.max(8, Math.min(462, 454 - shot.y));
    const description = shot.description || (shot.made ? "Made" : "Missed");
    return (
      <circle
        key={`${index}-${shot.x}-${shot.y}`}
        cx={x}
        cy={y}
        r="6.5"
        className={`shot ${shot.made ? "made" : "missed"}`}
      >
        <title>
          {description}
          {shot.distance == null ? "" : ` · ${shot.distance} ft`}
        </title>
      </circle>
    );
  });
  return (
    <div className="court-wrap">
      <svg
        className="court"
        viewBox="0 0 500 470"
        role="img"
        aria-label="NBA shot locations plotted on a half-court"
      >
        <rect x="8" y="8" width="484" height="454" rx="2" className="court-outline" />
        <path
          d="M 170 8 V 190 A 80 80 0 0 0 330 190 V 8 M 180 8 V 145 H 320 V 8 M 220 8 V 52 A 30 30 0 0 0 280 52 V 8"
          className="court-line"
        />
        <circle cx="250" cy="50" r="7" className="hoop" />
        <path d="M 8 230 A 242 242 0 0 0 492 230" className="court-line three-line" />
        {points}
      </svg>
      <div className="chart-legend">
        <span>
          <i className="made-dot" />
          Made
        </span>
        <span>
          <i className="missed-dot" />
          Missed
        </span>
        <b>{analysis.shots.length} attempts</b>
      </div>
    </div>
  );
}

function PlayerDetails() {
  const { gameId = "", playerId = "" } = useParams();
  const { meta } = useMeta();
  const [search] = useSearchParams();
  const season = search.get("season") || meta?.current_season || "";
  const phase = search.get("phase") || "Regular Season";
  const [analysis, setAnalysis] = useState<PlayerAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getPlayerAnalysis(gameId, playerId, season, phase)
      .then((data) => {
        if (active) setAnalysis(data);
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [gameId, playerId, season, phase, attempt]);
  if (loading)
    return (
      <LoadingState
        title="Player game analysis"
        detail="Loading game-specific stats and shot locations"
      />
    );
  if (error || !analysis)
    return (
      <>
        <BackLink season={season} phase={phase} />
        <ErrorState
          title="Player analysis unavailable"
          detail={error || "No player analysis was returned."}
          retry={() => setAttempt((value) => value + 1)}
        />
      </>
    );
  const player = analysis.player;
  return (
    <>
      <div className="back-row">
        <Link
          to={`/game/${encodeURIComponent(gameId)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(phase)}`}
        >
          ← Game box score
        </Link>
        <span className="phase-tag">GAME {gameId}</span>
      </div>
      <section className="detail-heading player-heading">
        <div className="player-avatar">
          {player.player_name
            .split(" ")
            .map((part) => part[0])
            .slice(0, 2)
            .join("")}
        </div>
        <div>
          <div className="eyebrow">PLAYER GAME ANALYSIS</div>
          <h1>{player.player_name}</h1>
          <p>
            {player.team?.name || "Team not provided"} · {season} season
          </p>
        </div>
        <span className="team-badge large player-team">{player.team?.abbreviation || "NBA"}</span>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">BOX SCORE</div>
            <h2>Game stats</h2>
          </div>
          <span className="section-note">Game-specific NBA Stats line</span>
        </div>
        <div className="metrics-grid">
          {keyStats.map(([key, title]) => (
            <div className="metric" key={key}>
              <span>{title}</span>
              <b>{format(player[key])}</b>
            </div>
          ))}
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">SHOT LOCATIONS</div>
            <h2>Shot chart</h2>
          </div>
          <span className="section-note">Real NBA Stats coordinates</span>
        </div>
        <ShotChart analysis={analysis} />
      </section>
    </>
  );
}

export function AppRoutes() {
  const { meta, error } = useMeta();
  if (error)
    return (
      <AppShell>
        <ErrorState title="NBA Terminal could not start" detail={error} />
      </AppShell>
    );
  if (!meta)
    return (
      <AppShell>
        <LoadingState title="NBA Terminal" detail="Preparing the current season view" />
      </AppShell>
    );
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/game/:gameId" element={<GameDetails />} />
        <Route path="/game/:gameId/player/:playerId" element={<PlayerDetails />} />
        <Route
          path="*"
          element={
            <ErrorState title="Page not found" detail="This NBA Terminal page does not exist." />
          }
        />
      </Routes>
    </AppShell>
  );
}

export function App() {
  return (
    <MetaProvider>
      <AppRoutes />
    </MetaProvider>
  );
}
