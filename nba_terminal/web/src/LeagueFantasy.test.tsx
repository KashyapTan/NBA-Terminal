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
  expect(
    screen.getByText("Current matchup: 2 winning · 7 tied · 0 losing · 0 unknown"),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("option")).toHaveLength(13);
  expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(10);
  expect(screen.getByText("Test player rostered")).toBeInTheDocument();
  await user.selectOptions(screen.getByRole("combobox"), "3");
  expect(
    screen.getByText("Hypothetical comparison: 0 winning · 9 tied · 0 losing · 0 unknown"),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Refresh league" }));
  expect(refresh).toHaveBeenCalledOnce();
});
it("does not turn absent totals into zeroes or inject fixtures into empty states", () => {
  const snapshot = testSnapshot();
  snapshot.teams[1].totals = null;
  const view = render(<Matchups snapshot={snapshot} />);
  expect(screen.getByText(/0 winning · 0 tied · 0 losing · 9 unknown/)).toBeInTheDocument();
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
  await user.type(screen.getByLabelText("League ID"), "123");
  await user.type(screen.getByLabelText("Season ending year"), "2027");
  await user.click(screen.getByLabelText("Private league"));
  await user.type(screen.getByLabelText("SWID"), "test-cookie");
  await user.type(screen.getByLabelText("espn_s2"), "test-cookie2");
  await user.click(screen.getByRole("button", { name: "Connect ESPN" }));
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
it("requires scoped confirmations, shows recommendations and invalidates on edit or refresh", async () => {
  const user = userEvent.setup();
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  const snapshot = testSnapshot();
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  expect(
    screen.queryByRole("button", { name: "Shortlist Test player waivers" }),
  ).not.toBeInTheDocument();
  const calculate = screen.getByRole("button", { name: "Calculate recommendation" });
  expect(calculate).toBeDisabled();
  await user.type(screen.getByLabelText("Verified weekly cap"), "7");
  await user.type(screen.getByLabelText("Verified adds used"), "1");
  await user.type(screen.getByLabelText("Verified adds remaining"), "6");
  await user.click(screen.getByLabelText(/I verified these weekly counts/));
  await user.click(screen.getByLabelText(/Test player rostered · Reported unlocked/));
  await user.click(screen.getByRole("button", { name: "Shortlist Test player free" }));
  await user.click(screen.getByLabelText(/I verified the shortlisted players/));
  await user.click(calculate);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  expect(onPlan.mock.calls[0][0]).toMatchObject({
    candidate_ids: ["free"],
    droppable_ids: ["rostered"],
    user_confirmed_counts: true,
    user_confirmed_eligibility: true,
    context: { league_id: 1, team_id: 1, matchup_period_id: 1 },
  });
  expect(screen.getByText(/baseline 30.0% → recommended 40.0%/)).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Maximum stream slots"));
  expect(screen.queryByRole("region", { name: "Waiver recommendation" })).not.toBeInTheDocument();
  view.rerender(
    <WaiverWire snapshot={{ ...snapshot, fetched_at: "2026-10-31T13:00:00Z" }} onPlan={onPlan} />,
  );
  expect(screen.getByLabelText(/I verified these weekly counts/)).not.toBeChecked();
  expect(screen.getByLabelText("Verified weekly cap")).toHaveValue(null);
});
it("explains unavailable optimizer instead of inventing probabilities", () => {
  render(<WaiverWire snapshot={testSnapshot()} />);
  expect(screen.getByText(/Optimizer integration is unavailable/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Calculate recommendation" })).toBeDisabled();
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

it("rejects inconsistent weekly confirmations and clears eligibility after changing drops", async () => {
  const user = userEvent.setup();
  const onPlan = vi.fn();
  const snapshot = testSnapshot();
  snapshot.teams[0].roster[0].locked = null;
  render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await user.type(screen.getByLabelText("Verified weekly cap"), "7");
  await user.type(screen.getByLabelText("Verified adds used"), "2");
  await user.type(screen.getByLabelText("Verified adds remaining"), "7");
  await user.click(screen.getByLabelText(/I verified these weekly counts/));
  expect(screen.getByRole("alert")).toHaveTextContent("used plus remaining must not exceed");
  await user.click(screen.getByLabelText(/I verified the shortlisted players/));
  await user.click(screen.getByLabelText(/Lock unknown: I verified this player is unlocked/));
  expect(screen.getByLabelText(/I verified the shortlisted players/)).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Calculate recommendation" })).toBeDisabled();
  expect(onPlan).not.toHaveBeenCalled();
});
