import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { testPlayer } from "./league-fantasy.test-fixtures";
import { LEAGUE_CATEGORIES, type PickupRecommendation } from "./league-fantasy-model";
import {
  DEFAULT_PICKUP_FILTERS,
  WaiverWorkspace,
  type WaiverWorkspaceProps,
} from "./WaiverWorkspace";

afterEach(cleanup);
function fixture(): WaiverWorkspaceProps {
  const move: PickupRecommendation = {
    add_id: "a",
    drop_id: "d",
    date: "2026-11-03",
    probability_gain: null,
    games_gain: 1,
    minutes_gain: null,
    season_cost: null,
    net_score: null,
    rationale: "Detailed reason kept below.",
    target_categories: ["ast"],
    gains: {},
    add_starts: 3,
    arithmetic: {
      primitives: {},
      categories: Object.fromEntries(
        LEAGUE_CATEGORIES.map(({ key }) => [
          key,
          {
            before: key.endsWith("pct") ? 0.5 : 100,
            after: key.endsWith("pct") ? 0.51 : key === "pts" ? 96 : 107,
            net: key.endsWith("pct") ? 0.01 : key === "pts" ? -4 : 7,
            opponent_before: 110,
            opponent_after: 110,
            lower_is_better: key === "to",
            add: 20,
            drop: 10,
            spillover: key === "pts" ? -14 : -3,
          },
        ]),
      ) as NonNullable<PickupRecommendation["arithmetic"]>["categories"],
    },
  };
  return {
    matchup: "Foxes vs Owls",
    remainingAddsLabel: "3 adds left",
    refreshedLabel: "Updated 12:00",
    updating: false,
    targets: ["ast", "stl", "blk", "threes", "ft_pct"],
    onTargetsChange: vi.fn(),
    filters: { ...DEFAULT_PICKUP_FILTERS },
    onFiltersChange: vi.fn(),
    moves: [move, { ...move, add_id: "b", drop_id: "e", date: "2026-11-04" }],
    players: {
      a: testPlayer("a", { name: "Alex Guard" }),
      d: testPlayer("d", { name: "Drew Center" }),
      b: testPlayer("b", { name: "Blair Wing" }),
      e: testPlayer("e", { name: "Eli Bench" }),
    },
    samples: {
      a: { minutes: 24, games: 4, teamGames: 5 },
      b: { minutes: 21, games: 3, teamGames: 5 },
    },
    stop: "search_limit",
    analysis: <p>Provider diagnostics and exclusions</p>,
  };
}
it("shows ordered compact moves, actual sample, true net and non-target harms with text", () => {
  const { container } = render(<WaiverWorkspace {...fixture()} />);
  const cards = within(screen.getByRole("list")).getAllByRole("listitem");
  expect(cards).toHaveLength(2);
  expect(cards[0]).toHaveTextContent("ADDAlex GuardDROPDrew Center");
  expect(cards[0]).toHaveTextContent("24 MPG · 4 GP / 5 team games");
  expect(cards[0]).toHaveTextContent("2026-11-03");
  expect(cards[0]).toHaveTextContent("3 usable starts");
  expect(cards[0]).toHaveTextContent("Add 20Drop 10Net +7Gain");
  expect(cards[0].querySelector(".ww-loss")).toHaveTextContent("Net -4Loss");
  expect(cards[0]).toHaveTextContent("TO ↓");
  expect(screen.getByText(/Search limit reached/)).toBeInTheDocument();
  expect(container.querySelector(".ww-analysis")).not.toHaveAttribute("open");
  expect(container.querySelector(".ww-analysis")).toHaveTextContent("all nine categories");
  expect(container.querySelectorAll(".ww-target")).toHaveLength(5);
});
it("serializes participation as a fraction and preserves other filters", () => {
  const props = fixture();
  render(<WaiverWorkspace {...props} />);
  fireEvent.click(screen.getByText("Pickup filters"));
  expect(screen.getByLabelText("Min MPG")).toHaveValue(15);
  expect(screen.getByLabelText("Min games")).toHaveValue(2);
  expect(screen.getByLabelText("Participation %")).toHaveValue(50);
  fireEvent.change(screen.getByLabelText("Participation %"), { target: { value: "75" } });
  expect(props.onFiltersChange).toHaveBeenCalledWith({
    min_minutes: 15,
    min_games: 2,
    min_participation: 0.75,
  });
  fireEvent.change(screen.getByLabelText("Min MPG"), { target: { value: "20" } });
  expect(props.onFiltersChange).toHaveBeenCalledWith({
    min_minutes: 20,
    min_games: 2,
    min_participation: 0.5,
  });
});
it("keeps moves during updating and gives a compact recovery action", () => {
  const props = fixture();
  const action = vi.fn();
  const { rerender } = render(<WaiverWorkspace {...props} />);
  fireEvent.click(screen.getByText("Full analysis & data"));
  rerender(
    <WaiverWorkspace
      {...props}
      updating
      status={{ text: "Showing saved result", actionLabel: "Retry", onAction: action }}
    />,
  );
  expect(screen.getByText(/Updating…/)).toBeInTheDocument();
  expect(screen.getByText("Alex Guard")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(action).toHaveBeenCalledOnce();
  expect(screen.getByText("Full analysis & data").parentElement).toHaveAttribute("open");
});
it.each([
  ["budget_exhausted", "No adds left in this plan"],
  ["no_positive_continuation", "No further beneficial move found in this search"],
  ["empty_qualified_pool", "No available pickups meet your filters"],
  ["required_data_missing", "Plan needs updated data"],
] as const)("communicates %s without a global optimality claim", (stop, text) => {
  render(<WaiverWorkspace {...fixture()} moves={[]} stop={stop} />);
  expect(screen.getByText(text)).toBeInTheDocument();
});
it("edits targets with an explicit five-category cap", () => {
  const props = fixture();
  render(<WaiverWorkspace {...props} />);
  expect(screen.getByRole("checkbox", { name: "PTS" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "AST" }));
  expect(props.onTargetsChange).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Apply five" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: "PTS" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply five" }));
  expect(props.onTargetsChange).toHaveBeenCalledWith(["stl", "blk", "threes", "ft_pct", "pts"]);
});
it("never invents qualified sample values", () => {
  render(<WaiverWorkspace {...fixture()} samples={{}} />);
  expect(screen.getAllByText(/Current sample · \? MPG · \? GP \/ \? team games/)).toHaveLength(2);
});
it("provides a concrete reconnect destination for definitive auth errors", () => {
  render(
    <WaiverWorkspace
      {...fixture()}
      moves={[]}
      status={{
        text: "Reconnect ESPN",
        actionLabel: "Reconnect",
        actionHref: "/fantasy?fantasyTab=dashboard",
        onAction: vi.fn(),
      }}
    />,
  );
  expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute(
    "href",
    "/fantasy?fantasyTab=dashboard",
  );
});
