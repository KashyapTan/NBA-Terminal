import { describe, expect, it } from "vitest";
import type { FantasyPlayer } from "./model";
import {
  DEFAULT_WEIGHTS,
  attemptSample,
  fantasyPoints,
  formatStat,
  rankProfile,
  sortedRankings,
  statValue,
} from "./fantasy-model";

const player = (overrides: Partial<FantasyPlayer> = {}): FantasyPlayer => ({
  player_id: 1,
  player_name: "A Player",
  team_id: 1,
  team_abbreviation: "AAA",
  team_name: "Alpha",
  games: 10,
  minutes_total: 300,
  points: 250,
  rebounds: 80,
  assists: 60,
  steals: 12,
  blocks: 8,
  turnovers: 30,
  threes_made: 40,
  three_attempts: 100,
  field_goals_made: 90,
  field_goal_attempts: 200,
  free_throws_made: 30,
  free_throw_attempts: 40,
  ...overrides,
});

describe("Fantasy stat calculations", () => {
  it("derives per-game values from season totals and keeps totals available", () => {
    const row = player();
    expect(statValue(row, "points", "perGame")).toBe(25);
    expect(statValue(row, "points", "totals")).toBe(250);
    expect(statValue(row, "turnovers", "perGame")).toBe(3);
    expect(statValue(player({ games: 0 }), "points", "perGame")).toBeNull();
    expect(statValue(player({ points: null }), "points", "totals")).toBeNull();
  });

  it("derives FG%, FT%, and 3P% from makes and attempts, with no invented zero rate", () => {
    const row = player();
    expect(statValue(row, "field_goal_percentage", "perGame")).toBe(0.45);
    expect(statValue(row, "free_throw_percentage", "totals")).toBe(0.75);
    expect(statValue(row, "three_point_percentage", "totals")).toBe(0.4);
    expect(statValue(player({ three_attempts: 0 }), "three_point_percentage", "totals")).toBeNull();
    expect(
      statValue(player({ field_goals_made: null }), "field_goal_percentage", "totals"),
    ).toBeNull();
    expect(attemptSample(row, "field_goal_percentage")).toBe(200);
    expect(attemptSample(row, "free_throw_percentage")).toBe(40);
    expect(attemptSample(row, "three_point_percentage")).toBe(100);
    expect(formatStat(0.45, "field_goal_percentage")).toBe("45.0%");
    expect(formatStat(null, "three_point_percentage")).toBe("—");
  });

  it("uses signed, configurable weights in the selected counting-stat view", () => {
    const row = player();
    const weights = {
      ...DEFAULT_WEIGHTS,
      points: 1,
      rebounds: 2,
      assists: 0,
      steals: 0,
      blocks: 0,
      turnovers: -1,
      threes_made: 0,
    };
    expect(fantasyPoints(row, "perGame", weights)).toBe(25 + 16 - 3);
    expect(fantasyPoints(row, "totals", weights)).toBe(250 + 160 - 30);
    expect(fantasyPoints(player({ turnovers: null }), "perGame", weights)).toBeNull();
    expect(fantasyPoints(row, "perGame", { ...weights, turnovers: 0 })).toBe(41);
  });

  it("ranks categories by production and turnovers from fewest to most", () => {
    const lowTurnovers = player({
      player_id: 2,
      player_name: "B Player",
      points: 100,
      turnovers: 10,
    });
    const highPoints = player({
      player_id: 3,
      player_name: "C Player",
      points: 400,
      turnovers: 50,
    });
    expect(
      sortedRankings([player(), lowTurnovers, highPoints], "points", "totals", DEFAULT_WEIGHTS).map(
        (item) => item.player_id,
      ),
    ).toEqual([3, 1, 2]);
    expect(
      sortedRankings(
        [player(), lowTurnovers, highPoints],
        "turnovers",
        "totals",
        DEFAULT_WEIGHTS,
      ).map((item) => item.player_id),
    ).toEqual([2, 1, 3]);
    expect(sortedRankings([player({ points: null })], "points", "totals", DEFAULT_WEIGHTS)).toEqual(
      [],
    );
  });

  it("summarizes strongest and weakest standard-category rank context", () => {
    const row = player();
    const other = player({
      player_id: 2,
      player_name: "B Player",
      points: 400,
      rebounds: 100,
      assists: 100,
      steals: 8,
      blocks: 20,
      turnovers: 10,
      threes_made: 60,
      field_goals_made: 120,
      field_goal_attempts: 200,
      free_throws_made: 35,
      free_throw_attempts: 40,
    });
    const profile = rankProfile(row, [row, other], "totals", DEFAULT_WEIGHTS);
    expect(profile).toEqual({ strongest: "STL #1", weakest: "PTS #2" });
    expect(rankProfile(player({ player_id: 99 }), [other], "perGame", DEFAULT_WEIGHTS)).toBeNull();
  });
});
