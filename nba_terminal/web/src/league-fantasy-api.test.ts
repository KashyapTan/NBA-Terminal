import { afterEach, expect, it, vi } from "vitest";
import { leagueFantasyApi } from "./league-fantasy-api";
afterEach(() => vi.unstubAllGlobals());
it("sends private access only in a guarded same-origin POST body", async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ connected: true }) });
  vi.stubGlobal("fetch", fetcher);
  await leagueFantasyApi.connect({
    league_id: 1,
    season_id: 2027,
    swid: "test-only-swid",
    espn_s2: "test-only-s2",
  });
  const [url, options] = fetcher.mock.calls[0];
  expect(url).toBe("/api/fantasy/espn/connect");
  expect(url).not.toContain("test-only");
  expect(options).toMatchObject({
    credentials: "same-origin",
    cache: "no-store",
    method: "POST",
    headers: { "X-Fantasy-Request": "1", "Content-Type": "application/json" },
  });
  expect(JSON.parse(options.body).espn_s2).toBe("test-only-s2");
});
it("does not expose backend or proxy error bodies", async () => {
  const json = vi.fn();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, json }));
  await expect(leagueFantasyApi.status()).rejects.toThrow("League request failed");
  expect(json).not.toHaveBeenCalled();
});
it("uses documented team, disconnect and snapshot routes", async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ connected: false }) });
  vi.stubGlobal("fetch", fetcher);
  await leagueFantasyApi.selectTeam(3);
  await leagueFantasyApi.disconnect();
  await leagueFantasyApi.snapshot({ refresh: true, compareTeamId: 4 });
  expect(fetcher.mock.calls[0]).toEqual([
    "/api/fantasy/espn/team",
    expect.objectContaining({ method: "PUT", body: '{"team_id":3}' }),
  ]);
  expect(fetcher.mock.calls[1][1].method).toBe("DELETE");
  expect(fetcher.mock.calls[2][0]).toBe(
    "/api/fantasy/espn/snapshot?refresh=true&compare_team_id=4",
  );
});

it("posts scoped plan preferences to the authenticated production route", async () => {
  const { requestWaiverPlan } = await import("./league-fantasy-api");
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ status: "incomplete", actions: [] }) });
  vi.stubGlobal("fetch", fetcher);
  const preferences = {
    user_confirmed_counts: false,
    user_confirmed_eligibility: false,
    candidate_ids: [],
    droppable_ids: [],
    max_stream_slots: 1,
    weekly_add_limit: null,
    used_adds: null,
    available_adds: null,
  };
  await requestWaiverPlan(preferences);
  expect(fetcher.mock.calls[0]).toEqual([
    "/api/fantasy/espn/plan",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      body: JSON.stringify(preferences),
      headers: { "X-Fantasy-Request": "1", "Content-Type": "application/json" },
    }),
  ]);
});
