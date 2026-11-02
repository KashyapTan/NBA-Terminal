import { afterEach, expect, it, vi } from "vitest";
import config from "./current-usage-declaration.json";
import { testSnapshot } from "./league-fantasy.test-fixtures";
import { bindUsage, declaredUsage } from "./usage-declaration";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});
function current() {
  const snapshot = testSnapshot();
  snapshot.league.id = config.league_id;
  snapshot.league.season_id = config.season_id;
  // A first post-deploy fetch forty minutes after the user's original statement.
  snapshot.fetched_at = "2026-11-02T17:42:22.264988Z";
  snapshot.period.start_date = config.matchup_start_date;
  snapshot.period.calendar_verified = true;
  snapshot.period.context_verified = true;
  snapshot.teams[0].name = "Kashyap's Team";
  snapshot.teams[0].season_acquisitions = 21;
  snapshot.teams[0].weekly_used_adds = null;
  vi.spyOn(Date, "now").mockReturnValue(Date.parse(snapshot.fetched_at) + 1000);
  return snapshot;
}
it("binds today's current statement to a fresh post-deploy snapshot, preserving original evidence and fixed expiry", () => {
  const snapshot = current();
  expect(snapshot.fetched_at).not.toBe(config.evidence_snapshot_at);
  const declaration = declaredUsage(snapshot)!;
  expect(declaration.used).toBe(0);
  expect(declaration.team_id).toBe(snapshot.selected_team_id);
  expect(declaration.snapshot_at).toBe(snapshot.fetched_at);
  expect(declaration.confirmed_at).toBe(config.confirmed_at);
  expect(declaration.expires_at).toBe(config.expires_at);
  snapshot.fetched_at = "2026-11-02T17:43:00Z";
  expect(declaredUsage(snapshot)).toEqual(declaration);
});
it("rejects wrong team/name/week/season, unverified periods, stale/future snapshot and fixed expiry", () => {
  for (const mutate of [
    (s: ReturnType<typeof current>) => {
      s.teams[0].name = "Kashyap";
    },
    (s: ReturnType<typeof current>) => {
      s.league.season_id++;
    },
    (s: ReturnType<typeof current>) => {
      s.period.start_date = "2026-11-09";
    },
    (s: ReturnType<typeof current>) => {
      s.selected_team_id = 2;
    },
    (s: ReturnType<typeof current>) => {
      s.period.calendar_verified = false;
    },
    (s: ReturnType<typeof current>) => {
      s.period.context_verified = false;
    },
    (s: ReturnType<typeof current>) => {
      s.fetched_at = config.evidence_snapshot_at;
    },
    (s: ReturnType<typeof current>) => {
      s.fetched_at = "2026-11-02T17:50:00Z";
    },
  ]) {
    const snapshot = current();
    mutate(snapshot);
    expect(declaredUsage(snapshot)).toBeUndefined();
  }
  const snapshot = current();
  vi.mocked(Date.now).mockReturnValue(Date.parse(config.expires_at));
  expect(declaredUsage(snapshot)).toBeUndefined();
});
it("permanently consumes the seed after positive API usage, including before first binding", () => {
  const snapshot = current();
  snapshot.teams[0].weekly_used_adds = 2;
  snapshot.teams[0].weekly_usage_complete = true;
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot.teams[0].weekly_used_adds = null;
  expect(declaredUsage(snapshot)).toBeUndefined();
});
it("does not resurrect zero after a later add or changed bound roster/aggregate even if the old evidence returns", () => {
  for (const change of ["positive", "roster", "aggregate"] as const) {
    localStorage.clear();
    const snapshot = current();
    const original = structuredClone(snapshot);
    expect(declaredUsage(snapshot)?.used).toBe(0);
    if (change === "positive") {
      snapshot.teams[0].weekly_used_adds = 1;
      snapshot.teams[0].weekly_usage_complete = true;
    }
    if (change === "roster") snapshot.teams[0].roster.pop();
    if (change === "aggregate") snapshot.teams[0].season_acquisitions = 22;
    expect(declaredUsage(snapshot)).toBeUndefined();
    expect(declaredUsage(original)).toBeUndefined();
  }
});
it("does not bind without durable storage and binds explicit manual zero with immutable evidence", () => {
  const snapshot = current();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  expect(declaredUsage(snapshot)).toBeUndefined();
  const declaration = bindUsage(snapshot, 0, config.confirmed_at);
  expect(declaration.used).toBe(0);
  expect(declaration.season_acquisitions).toBe(21);
  expect(declaration.expires_at).toBe("2026-11-02T18:02:22.264Z");
});

it("matches the actual team label across apostrophe/whitespace typography without accepting a short alias", () => {
  const snapshot = current();
  snapshot.teams[0].name = "  Kashyap’s   Team ";
  expect(declaredUsage(snapshot)?.team_id).toBe(snapshot.selected_team_id);
});

it("consumes a known positive acquisition for the same bound team even while its display name changes", () => {
  const snapshot = current();
  const old = structuredClone(snapshot);
  expect(declaredUsage(snapshot)?.used).toBe(0);
  snapshot.teams[0].name = "Renamed team";
  snapshot.teams[0].weekly_used_adds = 2;
  snapshot.teams[0].weekly_usage_complete = true;
  expect(declaredUsage(snapshot)).toBeUndefined();
  expect(declaredUsage(old)).toBeUndefined();
});
it("consumes the bound declaration on context switch before bootstrap guards return, including return to old context", () => {
  for (const change of ["league", "season", "team", "matchup", "start", "missing-team"] as const) {
    localStorage.clear();
    const snapshot = current();
    const old = structuredClone(snapshot);
    expect(declaredUsage(snapshot)?.used).toBe(0);
    if (change === "league") snapshot.league.id++;
    if (change === "season") snapshot.league.season_id++;
    if (change === "team") snapshot.selected_team_id = 2;
    if (change === "matchup") snapshot.period.matchup_period_id++;
    if (change === "start") snapshot.period.start_date = "2026-11-09";
    if (change === "missing-team")
      snapshot.teams = snapshot.teams.filter((team) => team.id !== snapshot.selected_team_id);
    expect(declaredUsage(snapshot)).toBeUndefined();
    expect(declaredUsage(old)).toBeUndefined();
  }
});
