import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import {
  LeagueConnection,
  Matchups,
  WaiverWire,
  useLeagueFantasy,
  type LeagueFantasyState,
} from "./LeagueFantasy";
import type { LeagueFantasyApi } from "./league-fantasy-api";
import { testSnapshot } from "./league-fantasy.test-fixtures";
import type { WaiverPlan } from "./league-fantasy-model";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function state(overrides: Partial<LeagueFantasyState> = {}): LeagueFantasyState {
  return {
    status: { connected: false },
    snapshot: null,
    loading: false,
    error: null,
    connect: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  };
}
it("shows actual opponent, nine categories, 13 comparison teams and hypothetical ties", async () => {
  const user = userEvent.setup();
  const refresh = vi.fn();
  render(<Matchups snapshot={testSnapshot()} onRefresh={refresh} />);
  expect(
    screen.getByRole("heading", { name: "Current opponent: Test opponent" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("2 wins, 0 losses, 7 ties")).toBeInTheDocument();
  expect(screen.getAllByRole("option")).toHaveLength(13);
  expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(10);
  expect(screen.getByText("Test player rostered")).toBeInTheDocument();
  await user.selectOptions(screen.getByRole("combobox"), "3");
  expect(screen.getByLabelText("0 wins, 0 losses, 9 ties")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Refresh league" }));
  expect(refresh).toHaveBeenCalledOnce();
});
it("does not turn absent totals into zeroes or inject fixtures into empty states", () => {
  const snapshot = testSnapshot();
  snapshot.teams[1].totals = null;
  const view = render(<Matchups snapshot={snapshot} />);
  expect(screen.getByText("9 categories unavailable")).toBeInTheDocument();
  view.rerender(
    <>
      <Matchups snapshot={null} />
      <WaiverWire snapshot={null} />
    </>,
  );
  expect(screen.queryByText("Test-only league")).not.toBeInTheDocument();
});
it("clears private cookies immediately after submit and never persists them", async () => {
  const user = userEvent.setup();
  const connect = vi.fn().mockResolvedValue(undefined);
  const storage = vi.spyOn(Storage.prototype, "setItem");
  render(<LeagueConnection state={state({ connect })} />);
  await user.click(screen.getByText("Manual or public league fallback"));
  expect(screen.getByLabelText("Manual league ID")).toHaveValue(604550749);
  expect(screen.getByLabelText("Manual season ending year")).toHaveValue(2027);
  await user.clear(screen.getByLabelText("Manual league ID"));
  await user.type(screen.getByLabelText("Manual league ID"), "123");
  await user.clear(screen.getByLabelText("Manual season ending year"));
  await user.type(screen.getByLabelText("Manual season ending year"), "2027");
  await user.click(screen.getByLabelText("Private league"));
  await user.type(screen.getByLabelText("SWID"), "test-cookie");
  await user.type(screen.getByLabelText("espn_s2"), "test-cookie2");
  await user.click(screen.getByRole("button", { name: "Connect manually" }));
  expect(connect).toHaveBeenCalledOnce();
  expect(screen.getByLabelText("SWID")).toHaveValue("");
  expect(screen.getByLabelText("espn_s2")).toHaveValue("");
  expect(storage).not.toHaveBeenCalled();
  expect(connect.mock.calls[0][0]).toEqual({ league_id: 123, season_id: 2027 });
});
it("shows public ownership caveat, team selection, errors and disconnect", async () => {
  const user = userEvent.setup();
  const selectTeam = vi.fn();
  const disconnect = vi.fn();
  render(
    <LeagueConnection
      state={state({
        status: {
          connected: true,
          auth_mode: "public",
          teams: [{ id: 1, name: "Test user", selectable: true, ownership_verified: false }],
        },
        error: "Connection failed",
        selectTeam,
        disconnect,
      })}
    />,
  );
  expect(screen.getByText(/Team ownership unverified/)).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Connection failed");
  await user.selectOptions(screen.getByLabelText("Your ESPN team"), "1");
  expect(selectTeam).toHaveBeenCalledWith(1);
  await user.click(screen.getByRole("button", { name: "Disconnect ESPN" }));
  expect(disconnect).toHaveBeenCalledOnce();
});
const readyPlan: WaiverPlan = {
  status: "ready",
  reasons: [],
  remaining_adds: 5,
  baseline: { totals: { pts: 100 }, games: 2, minutes: 40, probability_five_wins: 0.3 },
  projected: { totals: { pts: 115 }, games: 3, minutes: 65, probability_five_wins: 0.4 },
  actions: [
    {
      date: "2026-11-01",
      add_id: "free",
      drop_id: "rostered",
      stream_slot: 1,
      gains: { pts: 15, to: 2 },
      probability_gain: 0.1,
    },
  ],
  assumptions: ["Independent category model"],
  limitations: ["Uncalibrated"],
  data_gaps: [],
};
it("automatically analyzes and preserves availability across harmless refresh", async () => {
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  const snapshot = testSnapshot();
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  expect(onPlan.mock.calls[0][0]).not.toHaveProperty("candidate_ids");
  await userEvent.click(screen.getByText("Edit availability & roster protection"));
  await userEvent.click(
    screen.getByRole("button", { name: "Test player rostered availability: Available" }),
  );
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  expect(onPlan.mock.calls[1][0].player_overrides).toEqual({ rostered: { injured: true } });
  view.rerender(
    <WaiverWire snapshot={{ ...snapshot, fetched_at: "2026-10-31T13:00:00Z" }} onPlan={onPlan} />,
  );
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(3));
  expect(onPlan.mock.calls[2][0].player_overrides.rostered.injured).toBe(true);
  view.rerender(<WaiverWire snapshot={{ ...snapshot, selected_team_id: 2 }} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(4));
  expect(onPlan.mock.calls[3][0]).not.toHaveProperty("player_overrides");
});
it("explains unavailable optimizer instead of inventing probabilities", () => {
  render(<WaiverWire snapshot={testSnapshot()} />);
  expect(screen.getByText(/Optimizer integration is unavailable/)).toBeInTheDocument();
  expect(screen.queryByText(/30.0%/)).not.toBeInTheDocument();
});
it("does not restore a late snapshot after disconnect", async () => {
  let resolveSnapshot!: (value: ReturnType<typeof testSnapshot>) => void;
  const api: LeagueFantasyApi = {
    status: vi.fn().mockResolvedValue({ connected: true, team_id: 1 }),
    snapshot: vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSnapshot = resolve;
        }),
    ),
    connect: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn().mockResolvedValue({ connected: false }),
  };
  function Harness() {
    const data = useLeagueFantasy(api);
    return (
      <>
        <button type="button" onClick={() => void data.disconnect()}>
          Disconnect
        </button>
        <p>{data.snapshot?.league.name ?? "Empty"}</p>
        <p>{String(data.status.connected)}</p>
      </>
    );
  }
  render(<Harness />);
  await waitFor(() => expect(api.snapshot).toHaveBeenCalledOnce());
  await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
  await waitFor(() => expect(screen.getByText("false")).toBeInTheDocument());
  resolveSnapshot(testSnapshot());
  await waitFor(() => expect(screen.getByText("Empty")).toBeInTheDocument());
});

it("ignores late analysis after a protection edit", async () => {
  const resolvers: ((plan: WaiverPlan) => void)[] = [];
  const onPlan = vi
    .fn()
    .mockImplementation(() => new Promise<WaiverPlan>((resolve) => resolvers.push(resolve)));
  render(<WaiverWire snapshot={testSnapshot()} onPlan={onPlan} />);
  await userEvent.click(screen.getByText("Edit availability & roster protection"));
  await userEvent.click(screen.getByRole("button", { name: "Protect Test player rostered" }));
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  resolvers[1]({ ...readyPlan, reasons: ["Newest analysis"] });
  await screen.findAllByText("Newest analysis");
  resolvers[0]({ ...readyPlan, reasons: ["Stale analysis"] });
  await waitFor(() => expect(screen.queryByText("Stale analysis")).not.toBeInTheDocument());
  expect(onPlan.mock.calls[1][0].player_overrides).toEqual({ rostered: { protected: true } });
});
it("renders every beneficial alternative separately from sequential plan and respects legal protection", async () => {
  const snapshot = testSnapshot();
  snapshot.teams[0].roster[0].undroppable = true;
  const recommendation = {
    add_id: "free",
    drop_id: "rostered",
    date: "2026-11-01",
    probability_gain: 0.05,
    gains: { pts: 15 },
    games_gain: 1,
    minutes_gain: 25,
    season_cost: 0,
    net_score: 1,
    target_categories: ["pts"],
    rationale: "A net scoring upgrade.",
  };
  const onPlan = vi.fn().mockResolvedValue({
    ...readyPlan,
    recommendations: Array.from({ length: 9 }, (_, i) => ({
      ...recommendation,
      add_id: `free${i}`,
    })),
    strategy: {
      pts: {
        classification: "swing",
        explanation: "Scoring is close.",
        projected_margin: -3,
        historical_margin: 2,
        target_priority: 1,
      },
    },
  });
  render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await screen.findByText("Focus on PTS");
  expect(
    within(screen.getByRole("region", { name: "Ranked pickup alternatives" })).getAllByRole(
      "listitem",
    ),
  ).toHaveLength(9);
  expect(
    screen.getByRole("heading", { name: "Best explored add/drop sequence" }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByText("Edit availability & roster protection"));
  expect(screen.getByRole("button", { name: "Protect Test player rostered" })).toBeDisabled();
  expect(screen.getByText(/Prior-week gap/)).toBeInTheDocument();
});

it("uses normalized health, displays actual pre-plan budget and computes net shooting impact", async () => {
  const snapshot = testSnapshot();
  snapshot.teams[0].remaining_adds = 2;
  snapshot.teams[0].roster[0].injured = true;
  snapshot.teams[0].roster[0].health_status = "available";
  const onPlan = vi.fn().mockResolvedValue({
    ...readyPlan,
    remaining_adds: 1,
    recommendations: [
      {
        add_id: "free",
        drop_id: "rostered",
        date: "2026-11-01",
        probability_gain: 0.02,
        gains: { fgm: 2 },
        games_gain: 0,
        minutes_gain: 5,
        season_cost: 0,
        net_score: 1,
        target_categories: ["fg_pct"],
        category_impacts: {
          fg_pct: {
            before: 0.48,
            after: 0.49,
            margin_before: -0.005,
            margin_after: 0.005,
            estimate_gain: 0.1,
            flips_projection: true,
          },
        },
        rationale: "Improves shooting after the dropped player.",
      },
    ],
  });
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await screen.findByText("+1.00 pp net total");
  expect(view.container.querySelector(".waiver-budget b")).toHaveTextContent("2");
  await userEvent.click(screen.getByText("Edit availability & roster protection"));
  expect(
    screen.getByRole("button", { name: "Test player rostered availability: Available" }),
  ).toBeInTheDocument();
});

it("shows total arithmetic, selected five and paginates genuine alternatives without a seven cap", async () => {
  const snapshot = testSnapshot();
  snapshot.teams[0].roster[0].draft_round = 1;
  const recommendation = {
    add_id: "free",
    drop_id: "rostered",
    date: "2026-11-01",
    probability_gain: null,
    gains: { pts: 8 },
    games_gain: 0,
    minutes_gain: 0,
    season_cost: 2,
    net_score: 1,
    target_categories: ["pts"],
    rationale: "A reachable scoring deficit.",
    calculation: {
      pts: {
        add_rate: 12,
        add_starts: 4,
        drop_rate: 10,
        drop_starts: 4,
        added_total: 48,
        lost_total: 40,
        lineup_other_net: 0,
        net_total: 8,
      },
    },
  };
  const onPlan = vi.fn().mockResolvedValue({
    ...readyPlan,
    selected_categories: ["pts", "reb", "ast", "stl", "to"],
    safe_categories: ["reb"],
    improvement_categories: ["pts", "ast", "stl", "to"],
    recommendations: Array.from({ length: 25 }, (_, i) => ({
      ...recommendation,
      add_id: `free${i}`,
      drop_id: i === 24 ? "other" : "rostered",
    })),
  });
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await screen.findByText("25 beneficial alternatives");
  expect(view.container.querySelectorAll(".pickup-list > li")).toHaveLength(12);
  expect(screen.getByText(/Modeled cushions: REB/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Show more alternatives/ }));
  expect(view.container.querySelectorAll(".pickup-list > li")).toHaveLength(24);
  await userEvent.selectOptions(screen.getByLabelText("Review by roster drop"), "other");
  expect(view.container.querySelectorAll(".pickup-list > li")).toHaveLength(1);
  await userEvent.selectOptions(screen.getByLabelText("Review by roster drop"), "rostered");
  const detail = view.container.querySelector(".pickup-details")!;
  await userEvent.click(
    within(detail as HTMLElement).getByText("Remaining matchup arithmetic & tradeoffs"),
  );
  expect(
    within(detail as HTMLElement).getByRole("row", {
      name: /PTS.*12 × 4 starts.*10 × 4 lost starts.*\+8/,
    }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByText("Edit availability & roster protection"));
  expect(screen.getByRole("button", { name: "Protect Test player rostered" })).toBeEnabled();
  await userEvent.click(screen.getByText("Edit selected five categories"));
  await userEvent.click(screen.getByLabelText("REB", { selector: "input" }));
  expect(screen.getByRole("button", { name: "Recalculate selected five" })).toBeDisabled();
  await userEvent.click(screen.getByLabelText("BLK", { selector: "input" }));
  await userEvent.click(screen.getByRole("button", { name: "Recalculate selected five" }));
  await waitFor(() =>
    expect(onPlan.mock.lastCall?.[0].selected_categories).toEqual([
      "pts",
      "ast",
      "stl",
      "to",
      "blk",
    ]),
  );
});

it("discloses incomplete bounds and reads final weighted percentage calculation fields", async () => {
  const onPlan = vi.fn().mockResolvedValue({
    ...readyPlan,
    search: {
      evaluations: 5000,
      evaluation_limit_reached: true,
      alternatives_complete: false,
      legal_drop_ids: ["rostered", "other"],
      evaluated_drop_ids: ["rostered"],
      candidate_pool: 80,
      candidate_limit: 80,
      evaluation_limit: 5000,
    },
    recommendations: [
      {
        add_id: "free",
        drop_id: "rostered",
        date: "2026-11-01",
        probability_gain: null,
        gains: {},
        games_gain: 0,
        minutes_gain: 0,
        season_cost: 0,
        net_score: 1,
        target_categories: ["fg_pct"],
        rationale: "Weighted gain.",
        calculation: {
          fg_pct: {
            add_rate: 0.6,
            drop_rate: 0.4,
            add_starts: 2,
            drop_starts: 2,
            added_total: null,
            lost_total: null,
            lineup_other_net: null,
            net_total: 0.01,
            weighted: {
              before_makes: 40,
              before_attempts: 100,
              after_makes: 41,
              after_attempts: 100,
            },
          },
        },
      },
    ],
  });
  render(<WaiverWire snapshot={testSnapshot()} onPlan={onPlan} />);
  await screen.findByText(/Search incomplete: some beneficial alternatives may be omitted/);
  expect(screen.getByText(/1 of 2 legal roster drops evaluated/)).toHaveTextContent(
    "80 candidates",
  );
  await userEvent.click(screen.getByText("Remaining matchup arithmetic & tradeoffs"));
  expect(
    screen.getByRole("row", { name: /FG%.*40 \/ 100.*41 \/ 100.*\+1.00 pp/ }),
  ).toBeInTheDocument();
});

it.each([1, 2])(
  "shows one ordered plan of %i moves while alternatives stay secondary",
  async (count) => {
    const move = {
      add_id: "free",
      drop_id: "rostered",
      date: "2026-11-01",
      probability_gain: null,
      gains: { pts: 8 },
      games_gain: 0,
      minutes_gain: 0,
      season_cost: 0,
      net_score: 0.02,
      target_categories: ["pts"],
      rationale: "Full-roster improvement.",
      remaining_adds: 1,
      cumulative_focus_score: 64,
    };
    const onPlan = vi.fn().mockResolvedValue({
      ...readyPlan,
      recommended_plan: {
        moves: Array.from({ length: count }, (_, i) => ({
          ...move,
          add_id: i ? "second" : "free",
          drop_id: i ? "free" : "rostered",
          remaining_adds: count - i - 1,
        })),
        score_before: 0.6,
        score_after: 0.64,
        focus_score_after: 0.64,
        season_cost: 0,
        net_score_gain: 0.04,
        arithmetic: { categories: {}, primitives: {} },
      },
      recommendations: Array.from({ length: 7 }, () => move),
    });
    render(<WaiverWire snapshot={testSnapshot()} onPlan={onPlan} />);
    const primary = screen.getByRole("region", { name: "Recommended ordered plan" });
    await waitFor(() => expect(within(primary).getAllByRole("listitem")).toHaveLength(count));
    expect(within(primary).getByText(/60.0 → 64.0/)).toHaveTextContent(
      "heuristic, not win probability",
    );
    expect(within(primary).getAllByRole("table")).toHaveLength(count + 1);
    expect(
      screen.getByText(/Optional competing single-move alternatives/).closest("details"),
    ).not.toHaveAttribute("open");
  },
);

it("reruns core override independently of immutable locks", async () => {
  const snapshot = testSnapshot();
  snapshot.teams[0].roster[0].undroppable = true;
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  await userEvent.click(screen.getByLabelText("Allow core-player drops for this analysis"));
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  expect(onPlan.mock.lastCall?.[0].allow_core_drops).toBe(true);
  expect(
    screen.getByRole("button", { name: "Protect Test player rostered", hidden: true }),
  ).toBeDisabled();
});

it("shows current lead becoming a projected loss and clears incomplete cushion labels", async () => {
  const snapshot = testSnapshot();
  snapshot.projection_metadata = {
    actuals: { complete: false, reason: "Historical active lineup missing" },
  };
  const onPlan = vi.fn().mockResolvedValue({
    ...readyPlan,
    selected_categories: ["pts", "reb", "ast", "stl", "to"],
    safe_categories: ["reb"],
    strategy: {
      reb: {
        classification: "favored",
        safe_win: true,
        explanation: "Stale confidence",
        current_user: 132,
        current_opponent: 117,
        projected_user: 140,
        projected_opponent: 157,
        projected_margin: -17,
      },
    },
  });
  const { container } = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await screen.findByText("You: 132 + 8 remaining =", { exact: false });
  expect(screen.getByText("Opponent: 117 + 40 remaining =", { exact: false })).toHaveTextContent(
    "157",
  );
  expect(screen.getByText(/Modeled cushions: None established/)).toBeInTheDocument();
  expect(container.querySelector(".strategy-favored")).toBeNull();
  expect(screen.getByText(/Outlook unverified:/)).toBeInTheDocument();
});
