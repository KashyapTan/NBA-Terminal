import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { WaiverArithmetic } from "./WaiverArithmetic";
import { LEAGUE_CATEGORIES, type PickupRecommendation } from "./league-fantasy-model";
afterEach(cleanup);
export function arithmeticMove(): PickupRecommendation {
  const move: PickupRecommendation = {
    add_id: "free",
    drop_id: "rostered",
    date: "2026-11-01",
    probability_gain: null,
    gains: {},
    games_gain: 0,
    minutes_gain: 0,
    season_cost: 0,
    net_score: 0.02,
    target_categories: ["ast"],
    rationale: "Assists improve with a points and rebounds tradeoff.",
    calculation: {},
    category_impacts: {},
  };
  for (const { key } of LEAGUE_CATEGORIES) {
    const rate = key === "pts" ? 0 : key === "reb" ? 8 : key === "ast" ? 12 : 1;
    const lost = key === "pts" ? 30 : key === "reb" ? 10 : key === "to" ? 3 : 1;
    const before = 200;
    const net = rate * 4 - lost * 4;
    move.calculation![key] = {
      add_rate: rate,
      drop_rate: lost,
      add_starts: 4,
      drop_starts: 4,
      added_total: rate * 4,
      lost_total: lost * 4,
      lineup_other_net: 0,
      net_total: net,
    };
    move.category_impacts![key] = {
      before,
      after: before + net,
      margin_before: 10,
      margin_after: 10 + net,
      estimate_gain: 0,
      flips_projection: false,
    };
  }
  move.calculation!.fg_pct = {
    add_rate: 0.4,
    drop_rate: 0.5,
    add_starts: 4,
    drop_starts: 4,
    added_total: null,
    lost_total: null,
    lineup_other_net: null,
    net_total: -0.0125,
    weighted: {
      before_makes: 150,
      before_attempts: 320,
      after_makes: 146,
      after_attempts: 320,
      add_makes_rate: 4,
      add_attempts_rate: 10,
      drop_makes_rate: 5,
      drop_attempts_rate: 10,
    },
  };
  move.category_impacts!.fg_pct = {
    before: 150 / 320,
    after: 146 / 320,
    margin_before: 0,
    margin_after: -0.0125,
    estimate_gain: 0,
    flips_projection: false,
  };
  return move;
}
it("shows all nine full-team rows with nonzero drop loss and harmful points/REB tradeoff", () => {
  render(<WaiverArithmetic move={arithmeticMove()} />);
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(10);
  const rebounds = screen.getByRole("row", { name: /REB/ });
  expect(rebounds).toHaveTextContent("8 × 4 starts= 32");
  expect(rebounds).toHaveTextContent("10 × 4 lost starts= 40");
  expect(rebounds.querySelector(".league-losing")).toHaveTextContent("-8");
  expect(
    screen.getByRole("row", { name: /PTS/ }).querySelector(".league-losing"),
  ).toHaveTextContent("-120");
  expect(
    screen.getByRole("row", { name: /TO/ }).querySelector(".league-winning"),
  ).toHaveTextContent("-8");
  expect(screen.getByRole("row", { name: /FG%/ })).toHaveTextContent("150 / 320");
  expect(screen.getByRole("row", { name: /FG%/ })).toHaveTextContent("146 / 320");
  expect(screen.getByRole("row", { name: /FG%/ })).toHaveTextContent("-1.25 pp");
  expect(table.closest("details")).toBeNull();
});
it("distinguishes genuine zero lost starts from missing loss inputs", () => {
  const move = arithmeticMove();
  Object.assign(move.calculation!.reb!, { drop_starts: 0, lost_total: 0, net_total: 32 });
  move.category_impacts!.reb!.after = 232;
  const view = render(<WaiverArithmetic move={move} />);
  expect(screen.getByRole("row", { name: /REB/ })).toHaveTextContent("10 × 0 lost starts= 0");
  expect(screen.getByRole("row", { name: /REB/ })).toHaveTextContent("+32");
  delete move.calculation!.reb;
  delete move.category_impacts!.reb;
  view.rerender(<WaiverArithmetic move={move} />);
  expect(screen.getByRole("row", { name: /REB/ })).toHaveTextContent("? × ? lost starts= ?");
  expect(screen.getByRole("row", { name: /REB/ })).not.toHaveTextContent("+32");
});
