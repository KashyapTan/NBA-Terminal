import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, MetaProvider } from "./App";
import { getGame } from "./api";
import type { AnalyticsToolsContentProps, PlayerBrowserContentProps } from "./GameCenterShell";

vi.mock("./api", () => ({
  getMeta: vi.fn(async () => ({
    current_season: "2026-27",
    seasons: ["2026-27", "2025-26"],
    supported_from: "1996-97",
  })),
  getGames: vi.fn(async () => ({ games: [], supported: true })),
  getUpcoming: vi.fn(async () => ({ games: [], days: [] })),
  getGame: vi.fn(async () => ({ game_id: "0022600123", players: [], teams: [] })),
  getPlayerAnalysis: vi.fn(),
}));
vi.mock("./FantasyPage", () => ({ default: () => <h1>Fantasy workspace</h1> }));

// Contract double tests shell routing only; the real PLAYER implementation is not present yet.
function BrowserContract({ season, phase, playerId, onPlayerSelect }: PlayerBrowserContentProps) {
  return (
    <div>
      <p>
        Profile context: {season} / {phase} / {playerId || "search"}
      </p>
      <button type="button" onClick={() => onPlayerSelect?.(7)}>
        Choose player seven
      </button>
      {playerId && (
        <Link
          to={`/game/0022600123?season=${season}&phase=${encodeURIComponent(phase)}&player=${playerId}`}
        >
          Open actual log game
        </Link>
      )}
    </div>
  );
}
function ToolsContract({ initialTool }: AnalyticsToolsContentProps) {
  return <h1>Tool contract: {initialTool || "default"}</h1>;
}
function HistoryControls() {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <>
      <button type="button" onClick={() => navigate(-1)}>
        Browser back
      </button>
      <output aria-label="Current URL">
        {location.pathname}
        {location.search}
      </output>
    </>
  );
}
function mount(path: string, enablePlayers = true, enableTools = false) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <MetaProvider>
        <AppRoutes
          playerBrowser={enablePlayers ? BrowserContract : undefined}
          analyticsTools={enableTools ? ToolsContract : undefined}
        />
        <HistoryControls />
      </MetaProvider>
    </MemoryRouter>,
  );
}
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Game Center shell contracts", () => {
  it("prepares player selection URLs, phase/season controls and browser back without fetching a game", async () => {
    const user = userEvent.setup();
    mount("/players?season=2025-26&phase=Playoffs");
    expect(
      await screen.findByText("Profile context: 2025-26 / Playoffs / search"),
    ).toBeInTheDocument();
    const sections = screen.getByRole("navigation", { name: "Game Center sections" });
    expect(within(sections).getByRole("link", { name: "Players" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    screen.getByRole("button", { name: "Choose player seven" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByLabelText("Current URL")).toHaveTextContent(
      "/players/7?season=2025-26&phase=Playoffs",
    );
    expect(screen.getByText("Profile context: 2025-26 / Playoffs / 7")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Player season" }), "2026-27");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Player phase" }),
      "Regular Season",
    );
    expect(screen.getByText("Profile context: 2026-27 / Regular Season / 7")).toBeInTheDocument();
    expect(getGame).not.toHaveBeenCalled();
    await user.click(screen.getByRole("link", { name: "Open actual log game" }));
    expect(await screen.findByText("Box score not available")).toBeInTheDocument();
    expect(getGame).toHaveBeenCalledWith("0022600123", "2026-27");
    expect(screen.getByLabelText("Current URL")).toHaveTextContent("player=7");
    await user.click(screen.getByRole("button", { name: "Browser back" }));
    expect(
      await screen.findByText("Profile context: 2026-27 / Regular Season / 7"),
    ).toBeInTheDocument();
    await user.click(within(sections).getByRole("link", { name: /^Games$/ }));
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Current URL")).toHaveTextContent(
      "/?season=2026-27&phase=Regular+Season",
    );
  });

  it("restores independent direct player URLs and handles malformed context honestly", async () => {
    mount("/players/7?season=2025-26&phase=Playoffs");
    expect(await screen.findByText("Profile context: 2025-26 / Playoffs / 7")).toBeInTheDocument();
    cleanup();
    mount("/players/invalid?season=bad&phase=bad");
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid player ID");
    expect(screen.getByRole("link", { name: "Search players" })).toHaveAttribute(
      "href",
      "/players?season=2026-27&phase=Regular%20Season",
    );
    expect(screen.queryByText(/Profile context/)).not.toBeInTheDocument();
  });

  it("prepares direct analytics destinations without claiming unintegrated analyses", async () => {
    mount("/tools/consistency?season=2026-27", true, true);
    expect(
      await screen.findByRole("heading", { name: "Tool contract: consistency" }),
    ).toBeInTheDocument();
    const sections = screen.getByRole("navigation", { name: "Game Center sections" });
    expect(within(sections).getByRole("link", { name: "Analytics Tools" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(sections).getByRole("link", { name: /^Games$/ })).not.toHaveAttribute(
      "aria-current",
    );
    cleanup();
    mount("/tools?tool=picks", true, true);
    expect(
      await screen.findByRole("heading", { name: "Tool contract: picks" }),
    ).toBeInTheDocument();
    cleanup();
    mount("/tools/unknown", true, true);
    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown analytics tool");
    expect(screen.queryByRole("heading", { name: /Tool contract/ })).not.toBeInTheDocument();
  });

  it("keeps unintegrated destinations hidden and preserves direct Fantasy queries", async () => {
    mount("/", false);
    expect(
      await screen.findByRole("heading", { name: "Every game, in focus." }),
    ).toBeInTheDocument();
    const sections = screen.getByRole("navigation", { name: "Game Center sections" });
    expect(within(sections).queryByRole("link", { name: "Players" })).not.toBeInTheDocument();
    expect(
      within(sections).queryByRole("link", { name: "Analytics Tools" }),
    ).not.toBeInTheDocument();
    cleanup();
    mount("/fantasy?fantasyTab=waiver&league=604550749");
    expect(await screen.findByRole("heading", { name: "Fantasy workspace" })).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Game Center sections" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Current URL")).toHaveTextContent(
      "fantasyTab=waiver&league=604550749",
    );
  });
});
