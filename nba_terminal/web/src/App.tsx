import {
  createContext,
  useContext,
  useEffect,
  useId,
  useState,
  type ReactNode,
  type ComponentType,
} from "react";
import { Link, Route, Routes, useLocation, useParams, useSearchParams } from "react-router-dom";
import { getGame, getGames, getMeta, getPlayerAnalysis, getUpcoming } from "./api";
import { groupGamesByDate } from "./game-groups";
import FantasyPage from "./FantasyPage";
import {
  AnalyticsWorkspace,
  type AnalyticsToolsContentProps,
  GameCenterShell,
  PlayersWorkspace,
  type PlayerBrowserContentProps,
} from "./GameCenterShell";
import { LeagueDashboardSummary, Matchups, useLeagueFantasy, WaiverWire } from "./LeagueFantasy";
import { requestWaiverPlan } from "./league-fantasy-api";
import type {
  BoxScore,
  Game,
  GamesResponse,
  Meta,
  PlayerAnalysis,
  PlayerLine,
  UpcomingResponse,
} from "./model";
import { PlayerAnalysisView } from "./PlayerAnalysis";

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

const SIDEBAR_PREFERENCE_KEY = "nba-terminal.sidebar-collapsed";

function AppShell({ children }: { children: ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(SIDEBAR_PREFERENCE_KEY) === "true";
    } catch {
      return false;
    }
  });
  function toggleSidebar() {
    const next = !sidebarCollapsed;
    setSidebarCollapsed(next);
    try {
      window.localStorage.setItem(SIDEBAR_PREFERENCE_KEY, String(next));
    } catch {
      // Navigation remains usable when storage is blocked or full.
    }
  }
  const location = useLocation();
  const isFantasy = location.pathname.startsWith("/fantasy");
  const label = location.pathname.includes("/player/")
    ? "Player Game Analysis"
    : location.pathname.startsWith("/game/")
      ? "Game Box Score"
      : isFantasy
        ? "Fantasy"
        : "Game Center";
  return (
    <div
      className={`app-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}${isFantasy ? " fantasy-shell" : ""}${
        location.pathname.includes("/player/") ? " player-analysis-shell" : ""
      }`}
    >
      <aside className="sidebar">
        <button
          type="button"
          className="brand"
          onClick={toggleSidebar}
          aria-expanded={!sidebarCollapsed}
          aria-controls="workspace-navigation"
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="brand-mark" aria-hidden="true">
            N
          </span>
          <span className="brand-name">
            NBA <b>TERMINAL</b>
          </span>
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav id="workspace-navigation" aria-label="Workspace">
          <Link
            className={`nav-item${!isFantasy ? " active" : ""}`}
            to="/"
            aria-label="Game Center"
            title="Game Center"
            aria-current={!isFantasy ? "page" : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              ▦
            </span>
            <span className="nav-text">Game Center</span>
          </Link>
          <Link
            className={`nav-item${isFantasy ? " active" : ""}`}
            to="/fantasy"
            aria-label="Fantasy"
            title="Fantasy"
            aria-current={isFantasy ? "page" : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              ✳
            </span>
            <span className="nav-text">Fantasy</span>
          </Link>
        </nav>
        <div className="sidebar-foot">
          NBA Stats source
          <br />
          <small>Cached reads · errors shown</small>
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
            <span>NBA Stats</span>
          </div>
        </header>
        <div className="view" aria-live="polite">
          {children}
        </div>
        <footer>Data from NBA Stats · Source errors and missing data are shown</footer>
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
  const [failedLogo, setFailedLogo] = useState<string | null>(null);
  return (
    <span className={`team-badge${large ? " large" : ""}`}>
      {team?.logo_url && failedLogo !== team.logo_url ? (
        <img
          src={team.logo_url}
          alt={`${team.name} logo`}
          loading="lazy"
          onError={() => setFailedLogo(team.logo_url || null)}
        />
      ) : (
        <span title={team?.name || "Team unavailable"}>{team?.abbreviation || "NBA"}</span>
      )}
    </span>
  );
}

function GameCard({ game, season }: { game: Game; season: string }) {
  const status =
    game.status_id ??
    (/final/i.test(game.status)
      ? 3
      : /scheduled|\b(?:ET|EST|EDT)\b/i.test(game.status)
        ? 1
        : /progress|Q\d|quarter|half/i.test(game.status)
          ? 2
          : 0);
  const hasScore = status === 2 || status === 3;
  const state =
    status === 2 ? "live" : status === 3 ? "final" : status === 1 ? "scheduled" : "unknown";
  const descriptionId = useId();
  return (
    <Link
      className={`game-card game-card--${state}`}
      to={`/game/${encodeURIComponent(game.game_id)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(game.phase)}`}
      aria-label={`Open ${game.away_team.name} at ${game.home_team.name}`}
      aria-describedby={descriptionId}
    >
      <span className="matchup">
        {[
          { team: game.away_team, score: game.away_score, side: "Away" },
          { team: game.home_team, score: game.home_score, side: "Home" },
        ].map(({ team, score, side }) => (
          <span className="team-side" key={side}>
            <TeamBadge team={team} />
            <span className="team-name">
              {team.name}
              <small>{side}</small>
            </span>
            <b className="score">{hasScore ? format(score) : "—"}</b>
          </span>
        ))}
      </span>
      <span className="game-info" id={descriptionId}>
        <span className="game-status">
          <i className={`status-dot ${state}`} />
          {game.status}
        </span>
        {status === 1 &&
          (game.start_time ? (
            <time dateTime={game.start_time}>{formatStartTime(game.start_time)}</time>
          ) : (
            <span className="time-unavailable">Time TBD</span>
          ))}
        <span className="phase-tag">{game.phase}</span>
      </span>
      <span className="arrow" aria-hidden="true">
        ↗
      </span>
    </Link>
  );
}

function formatStartTime(value: string): string {
  const timestamp = new Date(value);
  if (!Number.isNaN(timestamp.valueOf())) {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(timestamp);
  }
  return value;
}

function formatGroupDate(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12);
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function GameDateGroups({
  games,
  season,
  direction,
  days,
}: {
  games: Game[];
  season: string;
  direction: "ascending" | "descending";
  days?: string[];
}) {
  const groups = groupGamesByDate(games, direction);
  const dateGroups = days?.length
    ? days.map((date) => ({ date, games: games.filter((game) => game.date === date) }))
    : groups;
  return (
    <div className="date-groups">
      {dateGroups.map(({ date, games: dateGames }) => (
        <section className="date-group" key={date} aria-labelledby={`games-${date}-${direction}`}>
          <div className="date-heading">
            <h3 id={`games-${date}-${direction}`}>{formatGroupDate(date)}</h3>
            <span>
              {dateGames.length} {dateGames.length === 1 ? "game" : "games"}
            </span>
          </div>
          {!dateGames.length && <p className="schedule-empty">No games scheduled.</p>}
          <div className="games-grid">
            {dateGames.map((game) => (
              <GameCard key={game.game_id} game={game} season={season} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Dashboard() {
  const { meta } = useMeta();
  const [search, setSearch] = useSearchParams();
  const requestedSeason = search.get("season");
  const season =
    requestedSeason && /^\d{4}-\d{2}$/.test(requestedSeason)
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
            {!meta.seasons.includes(season) && (
              <option value={season}>{season} · unsupported history</option>
            )}
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
            <h2>Today + next two days</h2>
          </div>
          <span className="section-note">
            {upcoming?.games.length
              ? `${upcoming.games.length} ${upcoming.games.length === 1 ? "game" : "games"} · dates in Eastern Time`
              : "Dates in Eastern Time"}
          </span>
        </div>
        {loading ? (
          <LoadingState title="Upcoming games" detail="Checking today and the next two dates" />
        ) : upcomingError ? (
          <ErrorState
            title="Schedule unavailable"
            detail={upcomingError}
            retry={() => setAttempt((value) => value + 1)}
          />
        ) : upcoming?.games.length ? (
          <GameDateGroups
            games={upcoming.games}
            season={meta.current_season}
            direction="ascending"
            days={upcoming.days}
          />
        ) : (
          <EmptyState
            icon="◷"
            title="No games scheduled in this three-day window"
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
          <span className="phase-legend" aria-label="Included phases">
            <span>Preseason</span>
            <span>Regular</span>
            <span>All-Star</span>
            <span>Play-In</span>
            <span>Playoffs</span>
            <span>NBA Cup final</span>
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
          <GameDateGroups games={result.games} season={season} direction="descending" />
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
    getGame(gameId, season)
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
  }, [gameId, season, attempt]);
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
  const awayTeamLine = boxTeams.find((item) => item.team?.id === box?.away_team?.id);
  const homeTeamLine = boxTeams.find((item) => item.team?.id === box?.home_team?.id);
  const hasMatchupOrder = Boolean(awayTeamLine && homeTeamLine);
  const displayedTeams = hasMatchupOrder ? [awayTeamLine, homeTeamLine] : boxTeams.slice(0, 2);
  const teamNames = hasMatchupOrder
    ? [box?.away_team?.name, box?.home_team?.name]
    : boxTeams.map((item) => item.team?.name);
  const titleTeams = teamNames.filter((name): name is string => Boolean(name));
  const players = [...(box?.players || [])].sort(
    (a, b) => (Number(b.pts) || 0) - (Number(a.pts) || 0),
  );
  return (
    <>
      <BackLink season={season} phase={phase} />
      <section className="detail-heading">
        <div>
          <div className="eyebrow">GAME BOX SCORE · {gameId}</div>
          <h1>{titleTeams.join(" at ") || `Game ${gameId}`}</h1>
          <p>Player stats for this matchup. Select any player for their game analysis.</p>
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <div className="eyebrow">PLAYER LINES BY TEAM</div>
            <h2>Team box scores</h2>
          </div>
          <span className="section-note">{players.length} players</span>
        </div>
        {displayedTeams.length ? (
          <>
            {!hasMatchupOrder && (
              <p className="boxscore-order-note" role="status">
                The source did not identify home and away for this game. Teams are shown in source
                order.
              </p>
            )}
            <div className="team-boxscore-grid">
              {displayedTeams.map((teamLine, index) => {
                if (!teamLine) return null;
                const teamPlayers = players.filter(
                  (player) => player.team_id === teamLine.team?.id,
                );
                const side = hasMatchupOrder
                  ? index === 0
                    ? "Away · left"
                    : "Home · right"
                  : `Team ${index + 1}`;
                return (
                  <section className="team-boxscore" key={teamLine.team?.id ?? index}>
                    <div className="team-boxscore-heading">
                      <TeamBadge team={teamLine.team} large />
                      <div>
                        <b className="team-boxscore-title">{teamLine.team?.name || "Team"}</b>
                        <span className="team-boxscore-side">
                          {side} · {teamPlayers.length} players
                        </span>
                      </div>
                      <strong className="team-boxscore-points">{format(teamLine.pts)}</strong>
                    </div>
                    {teamPlayers.length ? (
                      <div
                        className="table-scroll"
                        role="region"
                        aria-label={`${teamLine.team?.name || side} player box score`}
                        tabIndex={0}
                      >
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th scope="col">PLAYER</th>
                              {statColumns.map((key) => (
                                <th key={key} scope="col">
                                  {key.toUpperCase().replace("PLUS_MINUS", "+/-")}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {teamPlayers.map((player) => (
                              <tr key={player.player_id}>
                                <td>
                                  <Link
                                    className="player-link"
                                    to={`/game/${encodeURIComponent(gameId)}/player/${encodeURIComponent(player.player_id)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(phase)}`}
                                  >
                                    {player.player_name || "Player"}
                                  </Link>
                                  <small>{player.starter ? "Starter" : ""}</small>
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
                        title="Player lines unavailable"
                        detail="NBA Stats returned no player rows for this team."
                      />
                    )}
                  </section>
                );
              })}
            </div>
          </>
        ) : players.length ? (
          <div className="table-wrap">
            <table className="stats-table">
              <thead>
                <tr>
                  <th scope="col">PLAYER</th>
                  {statColumns.map((key) => (
                    <th key={key} scope="col">
                      {key.toUpperCase().replace("PLUS_MINUS", "+/-")}
                    </th>
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
        detail="Loading the game line, advanced metrics, and season sample"
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
  return <PlayerAnalysisView analysis={analysis} season={season} phase={phase} />;
}

function FantasyWorkspace({ meta }: { meta: Meta }) {
  const league = useLeagueFantasy();
  return (
    <FantasyPage
      meta={meta}
      league={{
        dashboard: <LeagueDashboardSummary state={league} />,
        matchups: (
          <Matchups
            snapshot={league.snapshot}
            loading={league.loading}
            error={league.error}
            onRefresh={() => void league.refresh()}
          />
        ),
        waiver: (
          <WaiverWire
            snapshot={league.snapshot}
            onPlan={requestWaiverPlan}
            loading={league.loading}
            error={league.error}
            onRefresh={() => void league.refresh()}
          />
        ),
      }}
    />
  );
}

export function AppRoutes({
  playerBrowser: PlayerBrowser,
  analyticsTools: AnalyticsTools,
}: {
  playerBrowser?: ComponentType<PlayerBrowserContentProps>;
  analyticsTools?: ComponentType<AnalyticsToolsContentProps>;
} = {}) {
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
        <Route path="/fantasy" element={<FantasyWorkspace meta={meta} />} />
        <Route
          element={
            <GameCenterShell players={Boolean(PlayerBrowser)} tools={Boolean(AnalyticsTools)} />
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/game/:gameId" element={<GameDetails />} />
          <Route path="/game/:gameId/player/:playerId" element={<PlayerDetails />} />
          {AnalyticsTools && (
            <Route path="/tools/:tool?" element={<AnalyticsWorkspace Tools={AnalyticsTools} />} />
          )}
          {PlayerBrowser && (
            <Route
              path="/players/:playerId?"
              element={<PlayersWorkspace meta={meta} Browser={PlayerBrowser} />}
            />
          )}
        </Route>
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
