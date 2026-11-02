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
  snapshot.fetched_at = config.evidence_snapshot_at;
  snapshot.period.start_date = config.matchup_start_date;
  snapshot.teams[0].name = config.team_name;
  snapshot.teams[0].season_acquisitions = 21;
  vi.spyOn(Date, "now").mockReturnValue(Date.parse(config.confirmed_at) + 1000);
  return snapshot;
}
it("automatically binds today's explicit zero once, preserving evidence over harmless refresh", () => {
  const snapshot = current();
  const declaration = declaredUsage(snapshot)!;
  expect(declaration.used).toBe(0);
  expect(declaration.season_id).toBe(2027);
  expect(declaration.team_id).toBe(snapshot.selected_team_id);
  expect(declaration.roster_ids).toEqual(snapshot.teams[0].roster.map((p) => p.id).sort());
  snapshot.fetched_at = "2026-11-02T17:03:00Z";
  expect(declaredUsage(snapshot)).toEqual(declaration);
  expect(declaredUsage(snapshot)?.confirmed_at).toBe(config.confirmed_at);
});
it("never seeds zero for an unseen snapshot, another team/week/season, expiry or failed storage", () => {
  let snapshot = current();
  snapshot.fetched_at = "2026-11-02T17:04:00Z";
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot = current();
  snapshot.league.season_id++;
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot = current();
  snapshot.period.start_date = "2026-11-09";
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot = current();
  snapshot.selected_team_id = 2;
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot = current();
  vi.mocked(Date.now).mockReturnValue(Date.parse(config.expires_at));
  expect(declaredUsage(snapshot)).toBeUndefined();
  snapshot = current();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  expect(declaredUsage(snapshot)).toBeUndefined();
});
it("binds manual current zero to season/team/matchup with immutable confirmation and expiry", () => {
  const snapshot = current();
  const declaration = bindUsage(snapshot, 0, config.confirmed_at);
  expect(declaration.used).toBe(0);
  expect(declaration.season_acquisitions).toBe(21);
  expect(declaration.expires_at).toBe("2026-11-02T18:02:22.264Z");
});
