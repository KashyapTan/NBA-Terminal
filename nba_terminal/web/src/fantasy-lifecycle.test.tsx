import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { snapshotIdentity, useWaiverPlan } from "./fantasy-lifecycle";
import { FantasyApiError } from "./league-fantasy-api";
import type { PlannerPreferences, WaiverPlan } from "./league-fantasy-model";
import { testSnapshot } from "./league-fantasy.test-fixtures";
import { useLeagueFantasy } from "./use-league-session";
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
const plan = {
  status: "ready",
  reasons: ["Last good"],
  actions: [],
  data_gaps: [],
} as unknown as WaiverPlan;
const flush = async () => {
  await act(async () => {
    await Promise.resolve();
  });
};
it("ignores nested observation timestamps but reacts to facts, source status, dates and starts", () => {
  const original = testSnapshot();
  original.projection_metadata = { rates: { complete: true, as_of: "2026-11-02T12:00:00Z" } };
  Object.assign(original.projection_metadata.rates, {
    evaluated_at: "2026-11-02T12:00:00Z",
    fetched_at: "2026-11-02T12:00:00Z",
  });
  const next = structuredClone(original);
  Object.assign(next.projection_metadata!.rates, {
    evaluated_at: "2026-11-02T12:01:00Z",
    fetched_at: "2026-11-02T12:02:00Z",
  });
  next.fetched_at = "2026-11-02T12:01:00Z";
  next.projection_metadata!.rates.as_of = "2026-11-02T12:02:00Z";
  expect(snapshotIdentity(next)).toBe(snapshotIdentity(original));
  next.projection_metadata!.rates.complete = false;
  expect(snapshotIdentity(next)).not.toBe(snapshotIdentity(original));
  next.projection_metadata!.rates.complete = true;
  next.period.remaining_dates = [];
  expect(snapshotIdentity(next)).not.toBe(snapshotIdentity(original));
  next.period.remaining_dates = original.period.remaining_dates;
  next.teams[0].roster[0].schedule![0].started = true;
  expect(snapshotIdentity(next)).not.toBe(snapshotIdentity(original));
  next.teams[0].roster[0].schedule![0].started = false;
  Object.assign(next.projection_metadata!.rates, { expires_at: "2026-11-02T12:05:00Z" });
  expect(snapshotIdentity(next)).not.toBe(snapshotIdentity(original));
});
it("retains last good read-only through slow refresh, retries and late preference results", async () => {
  vi.useFakeTimers();
  const snapshot = testSnapshot();
  const requests: ((p: WaiverPlan) => void)[] = [];
  const onPlan = vi
    .fn()
    .mockResolvedValueOnce(plan)
    .mockRejectedValueOnce(new FantasyApiError(503, "busy"))
    .mockImplementation(() => new Promise<WaiverPlan>((resolve) => requests.push(resolve)));
  const { result, rerender } = renderHook(
    ({ prefs, loading }) => useWaiverPlan(snapshot, prefs, onPlan, 0, false, loading),
    { initialProps: { prefs: {} as PlannerPreferences, loading: false } },
  );
  await flush();
  rerender({ prefs: {}, loading: true });
  expect(result.current.plan).toBe(plan);
  expect(result.current.lifecycle.readOnly).toBe(true);
  expect(onPlan).toHaveBeenCalledTimes(1);
  rerender({ prefs: { max_stream_slots: 2 }, loading: false });
  await flush();
  expect(result.current.plan).toBe(plan);
  expect(result.current.lifecycle.state).toBe("stale");
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  rerender({ prefs: { max_stream_slots: 3 }, loading: false });
  await flush();
  await act(async () => requests[1]({ ...plan, reasons: ["Newest"] }));
  await act(async () => requests[0]({ ...plan, reasons: ["Late"] }));
  expect(result.current.plan?.reasons).toEqual(["Newest"]);
  expect(result.current.lifecycle.readOnly).toBe(false);
});
it("coalesces sustained polls/focus/visibility, recovers transient errors, and revokes 401", async () => {
  vi.useFakeTimers();
  const snapshot = testSnapshot();
  const api = {
    status: vi.fn().mockResolvedValue({ connected: true, team_id: 1, context_id: "same" }),
    snapshot: vi.fn().mockResolvedValue(snapshot),
    connect: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn(),
  };
  const { result } = renderHook(() => useLeagueFantasy(api));
  await flush();
  for (let i = 0; i < 4; i++) {
    api.status.mockResolvedValue({
      connected: true,
      team_id: 1,
      context_id: "same",
      expires_at: String(i),
    });
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("nba-espn-bridge"));
    });
    await act(async () => vi.advanceTimersByTimeAsync(60000));
  }
  expect(api.snapshot).toHaveBeenCalledTimes(5);
  expect(api.status).toHaveBeenCalledTimes(9);
  api.snapshot.mockRejectedValueOnce(new FantasyApiError(429, "rate_limited"));
  await act(async () => result.current.refresh());
  expect(result.current.snapshot).toBe(snapshot);
  expect(result.current.lifecycle.state).toBe("stale");
  await act(async () => vi.advanceTimersByTimeAsync(60000));
  expect(result.current.lifecycle.state).toBe("connected");
  api.snapshot.mockRejectedValueOnce(new FantasyApiError(401, "access_denied"));
  await act(async () => result.current.refresh());
  expect(result.current.snapshot).toBeNull();
  expect(result.current.lifecycle.state).toBe("reconnect-needed");
});
it("bounds transient plan retry count and preserves result until definitive rejection", async () => {
  vi.useFakeTimers();
  const onPlan = vi
    .fn()
    .mockResolvedValueOnce(plan)
    .mockRejectedValue(new FantasyApiError(504, "upstream_timeout"));
  const { result, rerender } = renderHook(
    ({ attempt }) => useWaiverPlan(testSnapshot(), {}, onPlan, attempt, false, false),
    { initialProps: { attempt: 0 } },
  );
  await flush();
  rerender({ attempt: 1 });
  await flush();
  await act(async () => vi.advanceTimersByTimeAsync(30000));
  expect(onPlan).toHaveBeenCalledTimes(4);
  expect(result.current.plan).toBe(plan);
  expect(result.current.busy).toBe(false);
  onPlan.mockRejectedValue(new FantasyApiError(401, "access_denied"));
  rerender({ attempt: 2 });
  await flush();
  expect(result.current.plan).toBeNull();
  expect(result.current.lifecycle.state).toBe("reconnect-needed");
});
it("immutable declaration expiry reevaluates once without renewing evidence", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-02T17:00:00Z"));
  const prefs = { usage_declaration: { expires_at: "2026-11-02T17:00:02Z" } } as PlannerPreferences;
  const onPlan = vi.fn().mockResolvedValue(plan);
  renderHook(() => useWaiverPlan(testSnapshot(), prefs, onPlan, 0, false, false));
  await flush();
  await act(async () => vi.advanceTimersByTimeAsync(3000));
  expect(onPlan).toHaveBeenCalledTimes(2);
  expect(onPlan.mock.lastCall?.[0].usage_declaration?.expires_at).toBe("2026-11-02T17:00:02Z");
});
it("serializes rapid team writes and skips a superseded queued team", async () => {
  let finish!: (value: { connected: boolean; team_id: number }) => void;
  const api = {
    status: vi.fn().mockResolvedValue({ connected: true, team_id: 1 }),
    snapshot: vi.fn().mockResolvedValue(testSnapshot()),
    connect: vi.fn(),
    disconnect: vi.fn(),
    selectTeam: vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValue({ connected: true, team_id: 4 }),
  };
  const { result } = renderHook(() => useLeagueFantasy(api));
  await flush();
  let first!: Promise<void>, last!: Promise<void>;
  await act(async () => {
    first = result.current.selectTeam(2);
  });
  await act(async () => {
    void result.current.selectTeam(3);
    last = result.current.selectTeam(4);
  });
  expect(api.selectTeam).toHaveBeenCalledTimes(1);
  await act(async () => {
    finish({ connected: true, team_id: 2 });
    await first;
    await last;
  });
  expect(api.selectTeam.mock.calls).toEqual([[2], [4]]);
  expect(result.current.status.team_id).toBe(4);
});

it("fresh-to-cached transport reuse is semantic equality; stale is a source change", () => {
  const original = testSnapshot();
  original.free_agents[0].rate_provenance = { status: "fresh" } as never;
  const next = structuredClone(original);
  next.free_agents[0].rate_provenance = { status: "cached" } as never;
  expect(snapshotIdentity(next)).toBe(snapshotIdentity(original));
  next.free_agents[0].rate_provenance = { status: "stale" } as never;
  expect(snapshotIdentity(next)).not.toBe(snapshotIdentity(original));
});
it("status polling cannot clear the pending-source read-only state", async () => {
  let finish!: (snapshot: ReturnType<typeof testSnapshot>) => void;
  const api = {
    status: vi.fn().mockResolvedValue({ connected: true, team_id: 1 }),
    snapshot: vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    ),
    connect: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn(),
  };
  const { result } = renderHook(() => useLeagueFantasy(api));
  await flush();
  expect(result.current.loading).toBe(true);
  await act(async () => result.current.refreshStatus());
  expect(result.current.loading).toBe(true);
  expect(result.current.lifecycle.readOnly).toBe(true);
  await act(async () => finish(testSnapshot()));
  expect(result.current.loading).toBe(false);
});
it("a healthy status read cannot make a failed unknown snapshot current", async () => {
  const api = {
    status: vi.fn().mockResolvedValue({ connected: true, team_id: 1 }),
    snapshot: vi
      .fn()
      .mockResolvedValueOnce(testSnapshot())
      .mockRejectedValueOnce(new TypeError("network")),
    connect: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn(),
  };
  const { result } = renderHook(() => useLeagueFantasy(api));
  await flush();
  await act(async () => result.current.refresh());
  await act(async () => result.current.refreshStatus());
  expect(result.current.snapshot).not.toBeNull();
  expect(result.current.lifecycle.state).toBe("stale");
  expect(result.current.lifecycle.readOnly).toBe(true);
});
