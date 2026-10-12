import { describe, expect, it } from "vitest";
import { groupGamesByDate } from "./game-groups";
import type { Game } from "./model";

const team = { id: 1, abbreviation: "BOS", name: "Boston Celtics", nickname: "Celtics" };
const game = (game_id: string, date: string): Game => ({
  game_id,
  date,
  status: "Final",
  phase: "Regular Season",
  home_team: team,
  away_team: team,
  home_score: 110,
  away_score: 105,
});

describe("groupGamesByDate", () => {
  it("groups every game and orders upcoming dates chronologically", () => {
    const grouped = groupGamesByDate(
      [game("b", "2025-11-03"), game("a", "2025-11-02"), game("c", "2025-11-02")],
      "ascending",
    );
    expect(grouped.map(({ date, games }) => [date, games.map(({ game_id }) => game_id)])).toEqual([
      ["2025-11-02", ["a", "c"]],
      ["2025-11-03", ["b"]],
    ]);
  });

  it("orders historical date groups newest first", () => {
    const grouped = groupGamesByDate(
      [game("b", "2025-11-03"), game("a", "2025-11-02")],
      "descending",
    );
    expect(grouped.map(({ date }) => date)).toEqual(["2025-11-03", "2025-11-02"]);
  });
});
