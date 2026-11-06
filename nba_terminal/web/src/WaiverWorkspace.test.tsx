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
  expect(container.querySelectorAll(".ww-forecast-table tbody tr")).toHaveLength(9);
  expect(container.querySelector(".ww-plan")?.nextElementSibling).toHaveClass("ww-forecast");
  expect(container.querySelector(".ww-forecast")?.nextElementSibling).toHaveClass("ww-daily");
  expect(container.querySelector(".ww-daily")?.nextElementSibling).toHaveClass("ww-analysis");
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
it("distinguishes source scheduled games from constrained usable starts, including zero and unknown", () => {
  const props = fixture();
  const { container } = render(
    <WaiverWorkspace
      {...props}
      moves={[{ ...props.moves[0], add_starts: 2, drop_starts: 0 }, props.moves[1]]}
      scheduleCounts={[{ addRemainingGames: 4, dropRemainingGames: 3 }]}
    />,
  );
  const rows = container.querySelectorAll(".ww-schedule");
  expect(rows[0]).toHaveTextContent("ADD 4 games left · 2 usable starts");
  expect(rows[0]).toHaveTextContent("DROP 3 games left · 0 usable starts");
  expect(rows[1]).toHaveTextContent("ADD ? games left · 3 usable starts");
  expect(rows[1]).toHaveTextContent("DROP ? games left · ? usable starts");
  expect(
    screen.getByRole("button", { name: "Games and usable starts for move 1" }),
  ).toHaveAccessibleDescription(/slot limits/);
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

it("shows final realized tenure instead of full-horizon prefix add/drop/net", () => {
  const props = fixture();
  props.moves[0].realized = {
    dates: ["2026-11-03"],
    until: "2026-11-04",
    starts: 1,
    primitives: {
      pts: 4,
      reb: 2,
      ast: 3,
      stl: 1,
      blk: 0,
      threes: 1,
      to: 2,
      fgm: 1,
      fga: 3,
      ftm: 1,
      fta: 2,
    },
  };
  props.moves[0].drop_starts = 99; // Prefix-only future retention must not return in the final-plan row.
  props.sequenceImpact = {
    arithmetic: props.moves[0].arithmetic!,
    added_starts: [],
    lost_starts: [],
  };
  props.moves[0].direct_comparison = {
    acquisitions: 1,
    extra_acquisitions: 1,
    focus_score: 0.5,
    season_cost: 0,
    incremental_focus_gain: 0.02,
    actions: [{ date: "2026-11-04", drop_id: "d", add_id: "b" }],
    arithmetic: props.moves[0].arithmetic!.categories,
  };
  props.moves[0].chain_reason = "1 extra acquisition vs direct: +2 selected-five heuristic points.";
  const { container } = render(<WaiverWorkspace {...props} />);
  const first = container.querySelector(".ww-move")!;
  expect(first).toHaveTextContent("Final plan: 1 usable starts · 2026-11-03 · drop on 2026-11-04");
  expect(first).toHaveTextContent("extra acquisition");
  expect(first).toHaveTextContent("ADD ? games left · 1 usable starts");
  expect(first).toHaveTextContent("DROP ? games left · 0 usable starts");
  expect(first).not.toHaveTextContent("99 usable starts");
  expect(first).toHaveTextContent("Produced 1/3");
  expect(first).not.toHaveTextContent("Add 20Drop 10Net +7Gain");
  expect(container.querySelector(".ww-analysis")).not.toHaveAttribute("open");
});

it("keeps sequence get, lost/displaced production and harmful net visible with analysis closed", () => {
  const props = fixture();
  const arithmetic = structuredClone(props.moves[0].arithmetic!);
  arithmetic.categories.pts = { ...arithmetic.categories.pts, add: 3, drop: 7, net: -4 };
  arithmetic.categories.to = { ...arithmetic.categories.to, add: 5, drop: 1, net: 4 };
  arithmetic.categories.fg_pct = {
    ...arithmetic.categories.fg_pct,
    net: -0.01,
    makes: { before: 10, add: 1, drop: 2, spillover: 0, after: 9, net: -1 },
    attempts: { before: 20, add: 4, drop: 2, spillover: 0, after: 22, net: 2 },
  };
  props.sequenceImpact = {
    arithmetic,
    added_starts: [{ date: "2026-11-03", player_id: "a", name: "Alex Guard" }],
    lost_starts: [{ date: "2026-11-03", player_id: "d", name: "Displaced starter" }],
  };
  const { container } = render(<WaiverWorkspace {...props} />);
  const summary = screen.getByRole("region", { name: "Final plan get lose and net" });
  expect(summary).toBeVisible();
  expect(summary).toHaveTextContent("including displaced starts");
  expect(summary.querySelector('[data-category="pts"]')).toHaveTextContent(
    "Get 3Lose 7Net -4 Loss",
  );
  expect(summary.querySelector('[data-category="to"] .ww-loss')).toHaveTextContent("Net +4 Loss");
  expect(summary.querySelector('[data-category="fg_pct"]')).toHaveTextContent(
    "Get 1/4Lose 2/2Net -1.00 pp Loss",
  );
  expect(container.querySelector(".ww-analysis")).not.toHaveAttribute("open");
});
