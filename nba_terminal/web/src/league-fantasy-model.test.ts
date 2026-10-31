import { describe, expect, it } from "vitest";
import { categoryValue, compareCategory, eligibleCandidates } from "./league-fantasy-model";
import { testSnapshot } from "./league-fantasy.test-fixtures";
describe("league comparisons", () => {
  it("weights percentages by attempts and keeps empty samples unknown", () => {
    expect(categoryValue({ fgm: 3, fga: 10, fg_pct: 0.9 }, "fg_pct")).toBe(0.3);
    expect(categoryValue({ ftm: 0, fta: 0, ft_pct: 1 }, "ft_pct")).toBeNull();
    expect(categoryValue({ fg_pct: 0.4 }, "fg_pct")).toBe(0.4);
    expect(categoryValue(null, "pts")).toBeNull();
  });
  it("reverses turnovers, preserves ties and excludes unknown wins", () => {
    expect(compareCategory(5, 6, "to")).toBe("winning");
    expect(compareCategory(5, 6, "pts")).toBe("losing");
    expect(compareCategory(0.3, 0.1 + 0.2, "fg_pct")).toBe("tied");
    expect(compareCategory(null, 1, "pts")).toBe("unknown");
  });
  it("excludes all rostered, claim-only, duplicate and ineligible candidates", () => {
    const snapshot = testSnapshot();
    snapshot.free_agents.push(snapshot.free_agents[0]);
    expect(eligibleCandidates(snapshot).map((player) => player.id)).toEqual(["free"]);
  });
});
