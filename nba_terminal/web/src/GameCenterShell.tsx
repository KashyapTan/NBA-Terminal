import type { ComponentType } from "react";
import {
  Link,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import type { Meta } from "./model";

// Structural interface from the PLAYER handoff; implementation arrives by exact commit.
export type PlayerBrowserContentProps = {
  season: string;
  phase: string;
  playerId?: number;
  onPlayerSelect?: (id: number) => void;
};

const phases = ["Regular Season", "Pre Season", "Playoffs", "All Star", "Play In", "NBA Cup Final"];

export function GameCenterShell({ players = false }: { players?: boolean }) {
  const location = useLocation();
  const [search] = useSearchParams();
  const context = new URLSearchParams();
  for (const key of ["season", "phase"]) {
    const value = search.get(key);
    if (value) context.set(key, value);
  }
  const suffix = context.size ? `?${context}` : "";
  const onPlayers = location.pathname.startsWith("/players");
  return (
    <>
      <nav className="game-center-sections" aria-label="Game Center sections">
        <Link to={`/${suffix}`} aria-current={!onPlayers ? "page" : undefined}>
          Games
        </Link>
        {players && (
          <Link to={`/players${suffix}`} aria-current={onPlayers ? "page" : undefined}>
            Players
          </Link>
        )}
      </nav>
      <Outlet />
    </>
  );
}

export function PlayersWorkspace({
  meta,
  Browser,
}: {
  meta: Meta;
  Browser: ComponentType<PlayerBrowserContentProps>;
}) {
  const { playerId: rawPlayerId } = useParams();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const requestedSeason = search.get("season");
  const season =
    requestedSeason && /^\d{4}-\d{2}$/.test(requestedSeason)
      ? requestedSeason
      : meta.current_season;
  const requestedPhase = search.get("phase");
  const phase =
    requestedPhase && phases.includes(requestedPhase) ? requestedPhase : "Regular Season";
  const playerId =
    rawPlayerId && /^[1-9]\d*$/.test(rawPlayerId) && Number.isSafeInteger(Number(rawPlayerId))
      ? Number(rawPlayerId)
      : undefined;
  const invalidPlayer = Boolean(rawPlayerId && playerId === undefined);

  function setContext(key: string, value: string) {
    const next = new URLSearchParams(search);
    next.set(key, value);
    setSearch(next);
  }
  function selectPlayer(id: number) {
    const next = new URLSearchParams(search);
    next.set("season", season);
    next.set("phase", phase);
    navigate(`/players/${id}?${next}`);
  }

  return (
    <>
      <section className="page-heading">
        <div>
          <div className="eyebrow">NBA · GAME CENTER</div>
          <h1>Players</h1>
          <p>Search players and explore their season profile independently of a game.</p>
        </div>
        <div className="game-center-filters">
          <label className="season-select-label">
            SEASON
            <select
              aria-label="Player season"
              value={season}
              onChange={(event) => setContext("season", event.target.value)}
            >
              {!meta.seasons.includes(season) && <option value={season}>{season}</option>}
              {meta.seasons.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="season-select-label">
            PHASE
            <select
              aria-label="Player phase"
              value={phase}
              onChange={(event) => setContext("phase", event.target.value)}
            >
              {phases.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>
      {invalidPlayer ? (
        <p role="alert">
          Invalid player ID.{" "}
          <Link
            to={`/players?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(phase)}`}
          >
            Search players
          </Link>
        </p>
      ) : (
        <Browser season={season} phase={phase} playerId={playerId} onPlayerSelect={selectPlayer} />
      )}
    </>
  );
}
