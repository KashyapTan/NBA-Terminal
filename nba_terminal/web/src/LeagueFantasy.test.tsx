import { act, cleanup, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import {
  LeagueConnection,
  type LeagueFantasyState,
  Matchups,
  useLeagueFantasy,
  WaiverWire,
} from "./LeagueFantasy";
import { testSnapshot } from "./league-fantasy.test-fixtures";
import type { LeagueFantasyApi } from "./league-fantasy-api";
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
  await userEvent.click(screen.getByText("Roster settings"));
  await userEvent.click(
    screen.getByRole("button", { name: "Test player rostered availability: Available" }),
  );
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  expect(onPlan.mock.calls[1][0].player_overrides).toEqual({ rostered: { injured: true } });
  view.rerender(
    <WaiverWire snapshot={{ ...snapshot, fetched_at: "2026-10-31T13:00:00Z" }} onPlan={onPlan} />,
  );
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  expect(onPlan.mock.calls[1][0].player_overrides.rostered.injured).toBe(true);
  view.rerender(<WaiverWire snapshot={{ ...snapshot, selected_team_id: 2 }} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(3));
  expect(onPlan.mock.calls[2][0]).not.toHaveProperty("player_overrides");
});
it("explains unavailable optimizer instead of inventing probabilities", () => {
  render(<WaiverWire snapshot={testSnapshot()} />);
  expect(screen.getByText(/Optimizer integration is unavailable/)).toBeInTheDocument();
  expect(screen.queryByText(/30.0%/)).not.toBeInTheDocument();
});

it("scopes the authorized cap fallback to the user's league and never supplies historical usage", async () => {
  const snapshot = testSnapshot();
  snapshot.league.id = 604550749;
  snapshot.league.season_id = 2027;
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  expect(onPlan.mock.calls[0][0].matchup_add_limit_fallback).toBe(7);
  expect(onPlan.mock.calls[0][0]).not.toHaveProperty("used_adds");
  expect(onPlan.mock.calls[0][0]).not.toHaveProperty("available_adds");
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
  await userEvent.click(screen.getByText("Roster settings"));
  await userEvent.click(screen.getByRole("button", { name: "Protect Test player rostered" }));
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  resolvers[1]({ ...readyPlan, reasons: ["Newest analysis"] });
  await screen.findAllByText("Newest analysis");
  resolvers[0]({ ...readyPlan, reasons: ["Stale analysis"] });
  await waitFor(() => expect(screen.queryByText("Stale analysis")).not.toBeInTheDocument());
  expect(onPlan.mock.calls[1][0].player_overrides).toEqual({ rostered: { protected: true } });
});
it("reruns core override independently of immutable locks", async () => {
  const snapshot = testSnapshot();
  snapshot.teams[0].roster[0].undroppable = true;
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  await userEvent.click(screen.getByText("Roster settings"));
  await userEvent.click(screen.getByLabelText("Allow core-player drops"));
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
  expect(onPlan.mock.lastCall?.[0].allow_core_drops).toBe(true);
  expect(
    screen.getByRole("button", { name: "Protect Test player rostered", hidden: true }),
  ).toBeDisabled();
});

it("revokes an old manual budget confirmation when new league data arrives", async () => {
  const snapshot = testSnapshot();
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  await userEvent.click(screen.getByText("Full analysis & data"));
  await userEvent.click(screen.getByText("Advanced inputs & data notes", { exact: true }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Use my verified matchup counts" }));
  await waitFor(() => expect(onPlan.mock.calls.at(-1)?.[0].user_confirmed_counts).toBe(true));
  expect(onPlan.mock.calls.at(-1)?.[0].counts_snapshot_at).toBe(snapshot.fetched_at);
  view.rerender(
    <WaiverWire snapshot={{ ...snapshot, fetched_at: "2026-11-01T13:00:00Z" }} onPlan={onPlan} />,
  );
  await waitFor(() => expect(onPlan.mock.calls.at(-1)?.[0].user_confirmed_counts).toBe(false));
  expect(
    screen.getByRole("checkbox", { name: "Use my verified matchup counts" }),
  ).not.toBeChecked();
});

it("withholds stale recommendations after refresh failure and recovers on fresh data", async () => {
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  const snapshot = testSnapshot();
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  view.rerender(<WaiverWire snapshot={snapshot} onPlan={onPlan} error="ESPN refresh failed" />);
  await screen.findByText("Showing saved plan · refresh needed");
  expect(onPlan).toHaveBeenCalledOnce();
  expect(screen.queryByText("Newest analysis")).not.toBeInTheDocument();
  view.rerender(
    <WaiverWire
      snapshot={{ ...snapshot, fetched_at: "2026-11-02T17:10:00Z", data_gaps: ["Changed fact"] }}
      onPlan={onPlan}
    />,
  );
  await waitFor(() => expect(onPlan).toHaveBeenCalledTimes(2));
});

it("keeps a scoped explicit zero confirmation across a same-matchup refresh without changing evidence time", async () => {
  const snapshot = testSnapshot();
  const onPlan = vi.fn().mockResolvedValue(readyPlan);
  const view = render(<WaiverWire snapshot={snapshot} onPlan={onPlan} />);
  await waitFor(() => expect(onPlan).toHaveBeenCalledOnce());
  await userEvent.click(screen.getByText("Full analysis & data"));
  await userEvent.click(screen.getByText("Advanced inputs & data notes", { exact: true }));
  await userEvent.type(screen.getByLabelText("Matchup acquisitions used", { exact: true }), "0");
  await userEvent.click(screen.getByRole("checkbox", { name: "Use my verified matchup counts" }));
  await waitFor(() => expect(onPlan.mock.lastCall?.[0].usage_declaration?.used).toBe(0));
  const evidence = onPlan.mock.lastCall?.[0].usage_declaration;
  view.rerender(
    <WaiverWire
      snapshot={{ ...snapshot, fetched_at: "2026-11-02T17:20:00Z", data_gaps: ["New source fact"] }}
      onPlan={onPlan}
    />,
  );
  await waitFor(() =>
    expect(onPlan.mock.lastCall?.[0].context.fetched_at).toBe("2026-11-02T17:20:00Z"),
  );
  expect(onPlan.mock.lastCall?.[0].usage_declaration).toEqual(evidence);
  expect(onPlan.mock.lastCall?.[0].context.season_id).toBe(snapshot.league.season_id);
  expect(screen.getByRole("checkbox", { name: "Use my verified matchup counts" })).toBeChecked();
});

it("status polling does not cancel a slow snapshot and definitive disconnection invalidates context", async () => {
  let resolveSnapshot!: (snapshot: ReturnType<typeof testSnapshot>) => void;
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
    disconnect: vi.fn(),
  };
  const { result } = renderHook(() => useLeagueFantasy(api));
  await waitFor(() => expect(api.snapshot).toHaveBeenCalledOnce());
  act(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  await waitFor(() => expect(api.status).toHaveBeenCalledTimes(2));
  expect(api.snapshot).toHaveBeenCalledOnce();
  const snapshot = testSnapshot();
  await act(async () => resolveSnapshot(snapshot));
  expect(result.current.snapshot).toEqual(snapshot);
  vi.mocked(api.status).mockResolvedValue({ connected: false });
  act(() => window.dispatchEvent(new Event("nba-espn-bridge")));
  await waitFor(() => expect(result.current.status.connected).toBe(false));
  expect(result.current.snapshot).toBeNull();
  expect(result.current.lifecycle.state).toBe("reconnect-needed");
});
