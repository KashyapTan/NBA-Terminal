import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, MetaProvider } from "./App";

const team = (id: number, abbreviation: string, name: string) => ({
  id,
  abbreviation,
  name,
  nickname: name.split(" ").at(-1) || name,
});
const away = team(1, "CLE", "Cleveland Cavaliers");
const home = team(2, "BOS", "Boston Celtics");
const game = {
  game_id: "0022400001",
  date: "2025-11-02",
  status: "Final",
  phase: "Regular Season",
  home_team: home,
  away_team: away,
  home_score: 112,
  away_score: 106,
};
const meta = {
  current_season: "2025-26",
  seasons: ["2025-26", "2024-25", "1995-96"],
  supported_from: "1996-97",
};
const line = {
  player_id: 7,
  player_name: "Jayson Tatum",
  team_id: 2,
  team: home,
  starter: 1,
  min: "36:11",
  pts: 28,
  reb: 9,
  ast: 5,
  stl: 1,
  blk: 0,
  tov: 3,
  fgm: 9,
  fga: 18,
  fg3m: 4,
  fg3a: 9,
  ftm: 6,
  fta: 7,
  oreb: 1,
  dreb: 8,
  pf: 2,
  plus_minus: 11,
};
const box = {
  game_id: game.game_id,
  away_team: away,
  home_team: home,
  teams: [
    { team: away, pts: 106 },
    { team: home, pts: 112 },
  ],
  players: [line],
};
const historyGames = [
  {
    game_id: "0022400001",
    game_date: "2025-11-02",
    matchup: "BOS vs. CLE",
    wl: "W",
    min: 36.2,
    pts: 28,
    reb: 9,
    ast: 5,
    stl: 1,
    blk: 0,
    tov: 3,
    fgm: 9,
    fga: 18,
    fg_pct: 0.5,
    fg3m: 4,
    fg3a: 9,
    fg3_pct: 0.444,
    ft_pct: 0.857,
    pra: 42,
    plus_minus: 11,
    ts_pct: 0.67,
  },
  {
    game_id: "0022400002",
    game_date: "2025-10-30",
    matchup: "BOS @ CLE",
    wl: "L",
    min: 33.5,
    pts: 20,
    reb: 6,
    ast: 4,
    stl: 0,
    blk: 1,
    tov: 2,
    fgm: 7,
    fga: 16,
    fg_pct: 0.438,
    fg3m: 2,
    fg3a: 7,
    fg3_pct: 0.286,
    ft_pct: 1,
    pra: 30,
    plus_minus: -4,
    ts_pct: 0.55,
  },
  {
    game_id: "0022400003",
    game_date: "2025-10-28",
    matchup: "BOS vs. NYK",
    wl: "W",
    min: 35,
    pts: 15,
    reb: 4,
    ast: 6,
    stl: 2,
    blk: 0,
    tov: 1,
    fgm: 6,
    fga: 14,
    fg_pct: 0.429,
    fg3m: 1,
    fg3a: 5,
    fg3_pct: 0.2,
    ft_pct: 1,
    pra: 25,
    plus_minus: 8,
    ts_pct: 0.5,
  },
];
const analysis = {
  game_id: game.game_id,
  player: line,
  stats: line,
  shots: [
    {
      x: 10,
      y: 80,
      made: true,
      description: "Jump Shot",
      shot_type: "3PT Field Goal",
      period: 1,
      distance: 12,
      minutes_remaining: 3,
      seconds_remaining: null,
    },
    {
      x: -30,
      y: 110,
      made: false,
      description: "Layup Shot",
      shot_type: "2PT Field Goal",
      period: 2,
      distance: 8,
    },
  ],
  shot_chart_state: "available",
  advanced_stats: {
    off_rating: 119.2,
    def_rating: 108.4,
    net_rating: 10.8,
    ts_pct: 0.64,
    efg_pct: 0.61,
    usg_pct: 0.29,
    pie: 0.18,
  },
  advanced_stats_state: "available",
  advanced_stats_note: "",
  history: {
    state: "available",
    note: "",
    season: "2025-26",
    phase: "Regular Season",
    opponent: "CLE",
    games_played: historyGames.length,
    opponent_games_played: 2,
    summary: {
      PTS: {
        label: "PTS",
        mean: 21,
        std: 6.56,
        consistency_cv: 0.312,
        games: 3,
        last_5: 21,
        last_5_games: 3,
        last_10: 21,
        last_10_games: 3,
        last_20: 21,
        last_20_games: 3,
      },
      REB: {
        label: "REB",
        mean: 6.33,
        std: 2.52,
        consistency_cv: 0.398,
        games: 3,
        last_5: 6.33,
        last_5_games: 3,
        last_10: 6.33,
        last_10_games: 3,
        last_20: 6.33,
        last_20_games: 3,
      },
      AST: {
        label: "AST",
        mean: 5,
        std: 1,
        consistency_cv: 0.2,
        games: 3,
        last_5: 5,
        last_5_games: 3,
        last_10: 5,
        last_10_games: 3,
        last_20: 5,
        last_20_games: 3,
      },
    },
    games: historyGames,
    opponent_games: historyGames.slice(0, 2),
  },
  history_state: "available",
  game_context: {
    game_id: game.game_id,
    team: home,
    opponent: away,
    team_score: 112,
    opponent_score: 106,
    season: "2025-26",
    phase: "Regular Season",
    game_date: "2025-11-02",
    matchup: "BOS vs. CLE",
    result: "W",
    opponent_abbreviation: "CLE",
  },
};

function mount(path = "/", responder?: (url: string) => unknown) {
  const fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const url = String(input);
    const payload = responder ? responder(url) : defaultPayload(url);
    if (payload instanceof Error) throw payload;
    return { ok: true, status: 200, json: async () => payload };
  });
  vi.stubGlobal("fetch", fetch);
  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <MetaProvider>
        <AppRoutes />
      </MetaProvider>
    </MemoryRouter>,
  );
  return { ...result, fetch };
}

function defaultPayload(url: string): unknown {
  if (url === "/api/meta") return meta;
  if (url === "/api/upcoming") return { days: ["2025-11-02", "2025-11-03"], games: [] };
  if (url.startsWith("/api/games?"))
    return {
      season: "2025-26",
      supported: true,
      games: [game],
      phases: ["Pre Season", "Regular Season", "Playoffs"],
    };
  if (url.startsWith(`/api/games/${game.game_id}?season=`)) return box;
  if (url.startsWith(`/api/games/${game.game_id}/players/`)) return analysis;
  throw new Error(`Unexpected API path: ${url}`);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NBA Terminal screens", () => {
  it("loads the dashboard, filters the season, then opens a game and player analysis", async () => {
    const user = userEvent.setup();
    const { fetch } = mount();
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("No games scheduled in this two-day window"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "2025-26 season" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sunday, November 2, 2025" })).toBeInTheDocument();
    expect(screen.getByText("Boston Celtics")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Season" }), "2024-25");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/games?season=2024-25"));
    await screen.findByRole("heading", { name: "2024-25 season" });

    await user.click(
      screen.getByRole("link", { name: /Open Cleveland Cavaliers at Boston Celtics/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Cleveland Cavaliers at Boston Celtics" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Away · left|Home · right/).map((node) => node.textContent)).toEqual(
      ["Away · left · 0 players", "Home · right · 1 players"],
    );
    const table = within(
      screen.getByRole("region", { name: "Boston Celtics player box score" }),
    ).getByRole("table");
    expect(within(table).getByRole("link", { name: "Jayson Tatum" })).toBeInTheDocument();
    await user.click(within(table).getByRole("link", { name: "Jayson Tatum" }));
    expect(await screen.findByRole("heading", { name: "Jayson Tatum" })).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /NBA half court with plotted shot locations/ }),
    ).toBeInTheDocument();
    expect(document.querySelectorAll(".shot-chart__mark.is-made")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: "Points distribution across 3 games" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Coefficient of variation")).toBeInTheDocument();
    const consistency = document.querySelector(".player-analysis__consistency-table");
    expect(consistency?.textContent).toContain("L5 AVG");
    expect(consistency?.textContent).toContain("n = 3");
    expect(
      document.querySelector(".player-analysis__comparison-card:last-child small")?.textContent,
    ).toContain("n = 2 games");
  });

  it("shows upcoming matchups, empty history, and the unsupported-history state", async () => {
    const user = userEvent.setup();
    mount("/?season=1995-96", (url) => {
      if (url === "/api/meta") return meta;
      if (url === "/api/upcoming")
        return {
          days: ["2025-11-02", "2025-11-03"],
          games: [
            {
              ...game,
              game_id: "scheduled",
              status: "Scheduled",
              start_time: "7:00 PM ET",
              phase: "Pre Season",
            },
          ],
        };
      return url.endsWith("1995-96")
        ? { season: "1995-96", supported: false, games: [], phases: [] }
        : { season: "2024-25", supported: true, games: [], phases: [] };
    });
    expect(await screen.findByText("Cleveland Cavaliers")).toBeInTheDocument();
    expect(screen.getByText("7:00 PM ET")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sunday, November 2, 2025" })).toBeInTheDocument();
    expect(screen.getByText("History is not available in this view")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Season" }), "2024-25");
    expect(await screen.findByText("No completed games returned")).toBeInTheDocument();
  });

  it("keeps schedule and game-feed errors separate, with a retry action", async () => {
    const user = userEvent.setup();
    let gameCalls = 0;
    mount("/", (url) => {
      if (url === "/api/meta") return meta;
      if (url === "/api/upcoming") throw new Error("schedule down");
      if (url.startsWith("/api/games?")) {
        gameCalls += 1;
        if (gameCalls === 1) throw new Error("history down");
        return { season: "2025-26", supported: true, games: [], phases: [] };
      }
      return defaultPayload(url);
    });
    expect(await screen.findByText("Schedule unavailable")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("alert")
        .map((alert) => alert.textContent)
        .join(" "),
    ).toContain("history down");
    await user.click(screen.getAllByRole("button", { name: "Try again" })[0]);
    expect(await screen.findByText("No completed games returned")).toBeInTheDocument();
  });

  it("shows loading and a clear application-level metadata failure", async () => {
    let release: (value: unknown) => void = () => undefined;
    const promise = new Promise((resolve) => {
      release = resolve;
    });
    mount("/", (url) => (url === "/api/meta" ? promise : defaultPayload(url)));
    expect(screen.getByRole("status")).toHaveTextContent("Preparing the current season view");
    release(meta);
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    cleanup();
    mount("/", (url) => (url === "/api/meta" ? new Error("metadata down") : defaultPayload(url)));
    expect(await screen.findByRole("alert")).toHaveTextContent("metadata down");
  });

  it("handles box-score failures, empty player rows, player failures, and unavailable charts", async () => {
    const user = userEvent.setup();
    mount(`/game/${game.game_id}?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}?season=`))
        return { ...box, players: [], teams: [] };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Box score not available")).toBeInTheDocument();

    cleanup();
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`))
        return { ...analysis, shots: [], shot_chart_state: "unavailable" };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Shot chart unavailable")).toBeInTheDocument();
    expect(screen.getByText(/No locations are estimated/)).toBeInTheDocument();

    cleanup();
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`)) throw new Error("analysis down");
      return defaultPayload(url);
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("analysis down");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("analysis down");
  });

  it("retries a failed box score and orders recovered player lines by points", async () => {
    const user = userEvent.setup();
    let requests = 0;
    mount(`/game/${game.game_id}?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url === `/api/games/${game.game_id}`) {
        requests += 1;
        if (requests === 1) throw new Error("cached box score unavailable");
        return {
          ...box,
          players: [{ ...line, player_id: 8, player_name: "Jaylen Brown", pts: 18 }, line],
        };
      }
      return defaultPayload(url);
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("cached box score unavailable");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    const players = await screen.findByRole("table");
    expect(
      within(players)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Jayson Tatum", "Jaylen Brown"]);
    expect(requests).toBe(2);
  });

  it("configures historical lines and samples and filters real shot markers", async () => {
    const user = userEvent.setup();
    mount("/game/" + game.game_id + "/player/7?season=2025-26");
    expect(
      await screen.findByRole("heading", { name: "Historical sample & opponent comparison" }),
    ).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
    expect(document.querySelector(".player-analysis__hit-rate")?.textContent).toContain(
      "2 / 3 available games · at or above line",
    );

    const lineInput = screen.getByRole("spinbutton", { name: "Stat line" });
    await user.clear(lineInput);
    await user.type(lineInput, "30");
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(document.querySelector(".player-analysis__hit-rate")?.textContent).toContain(
      "0 / 3 available games",
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Historical stat" }), "reb");
    expect(screen.getByRole("spinbutton", { name: "Stat line" })).toHaveValue(6);
    expect(document.querySelector(".player-analysis__hit-rate")?.textContent).toContain(
      "2 / 3 available games",
    );
    expect(screen.getByText("7.5")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Shot period" }), "2");
    expect(screen.getAllByRole("button", { name: /Missed two-point/ })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Makes" }));
    expect(document.querySelector(".shot-chart__totals strong")?.textContent).toContain(
      "0 / 2 shots",
    );
    expect(screen.queryAllByRole("button", { name: /shot,/ })).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Perspective" }));
    expect(screen.getByRole("button", { name: "Perspective" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await user.click(screen.getByRole("button", { name: "Reset chart" }));
    expect(screen.getByRole("combobox", { name: "Shot period" })).toHaveValue("all");
    expect(screen.getByRole("button", { name: "Perspective" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(document.querySelector(".shot-chart__totals strong")?.textContent).toContain(
      "2 / 2 shots",
    );
  });

  it("shows missing composite history honestly and keeps the accessible perspective controls usable", async () => {
    const user = userEvent.setup();
    const addEventListener = vi.fn();
    const removeEventListener = vi.fn();
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({
        matches: true,
        addEventListener,
        removeEventListener,
      })),
    );
    mount("/game/" + game.game_id + "/player/7?season=2025-26");
    await screen.findByRole("heading", { name: "Where the attempts came from" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Historical stat" }), "pa");
    expect(screen.getByText("33")).toBeInTheDocument();
    expect(
      screen.getByText("Trend unavailable: this stat has no game-log values."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Distribution unavailable: at least two valid game values are needed."),
    ).toBeInTheDocument();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Historical sample size" }),
      "10",
    );
    expect(document.querySelector(".player-analysis__hit-rate")?.textContent).toContain(
      "0 / 0 available games",
    );

    expect(screen.getByRole("button", { name: "Perspective" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
    await user.click(screen.getByRole("button", { name: "Perspective" }));
    expect(screen.getByText(/Reduced motion is enabled/)).toBeInTheDocument();
    const rotation = screen.getByRole("slider", { name: "Court rotation" });
    const tilt = screen.getByRole("slider", { name: "Court tilt" });
    fireEvent.change(rotation, { target: { value: "17" } });
    fireEvent.change(tilt, { target: { value: "52" } });
    expect(screen.getByText("17°")).toBeInTheDocument();
    expect(screen.getByText("52°")).toBeInTheDocument();

    const make = screen.getByRole("button", { name: /Made three-point shot/ });
    fireEvent.pointerEnter(make);
    expect(document.querySelector(".shot-chart__tooltip")).toHaveTextContent("Made · 3PT");
    expect(document.querySelector(".shot-chart__tooltip")).toHaveTextContent("Q1 · 3:00");
    fireEvent.pointerLeave(make);
    fireEvent.focus(make);
    fireEvent.click(make);
    fireEvent.keyDown(make, { key: "Enter" });
    fireEvent.keyDown(make, { key: " " });
    fireEvent.blur(make);
    const miss = screen.getByRole("button", { name: /Missed two-point shot/ });
    fireEvent.pointerEnter(miss);
    expect(document.querySelector(".shot-chart__tooltip")).toHaveTextContent("Missed · 2PT");
    await user.click(screen.getByRole("button", { name: "Misses" }));
    expect(screen.getByRole("button", { name: /Missed two-point shot/ })).toBeInTheDocument();
    fireEvent.focus(screen.getByRole("button", { name: /Missed two-point shot/ }));
    expect(document.querySelector(".shot-chart__mark.is-active")).toBeInTheDocument();
    cleanup();
    expect(removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("labels missing advanced metrics and game logs as unavailable", async () => {
    mount("/game/" + game.game_id + "/player/7?season=2025-26", (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith("/api/games/" + game.game_id + "/players/")) {
        return {
          ...analysis,
          advanced_stats: {},
          advanced_stats_state: "unavailable",
          advanced_stats_note: "Advanced stats are not available for this game.",
          history: {
            ...analysis.history,
            state: "unavailable",
            note: "NBA Stats returned no season game-log rows for this player.",
            games: [],
            opponent_games: [],
            summary: {},
          },
          history_state: "unavailable",
        };
      }
      return defaultPayload(url);
    });
    expect(await screen.findByText("Advanced stats unavailable")).toBeInTheDocument();
    expect(screen.getByText("Season game logs unavailable")).toBeInTheDocument();
    expect(screen.getByText("Selected game stats")).toBeInTheDocument();
  });

  it("shows a chart-service failure distinctly and renders unknown routes", async () => {
    mount(`/game/${game.game_id}/player/7?season=2025-26`, (url) => {
      if (url === "/api/meta") return meta;
      if (url.startsWith(`/api/games/${game.game_id}/players/`))
        return { ...analysis, shots: [], shot_chart_state: "error" };
      return defaultPayload(url);
    });
    expect(await screen.findByText("Shot chart could not be loaded")).toBeInTheDocument();
    cleanup();
    mount("/unknown");
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
