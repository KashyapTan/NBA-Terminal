import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { type Category, LEAGUE_CATEGORIES, type PlanForecast } from "./league-fantasy-model";
import { forecastValue, matchupForecastData, MatchupForecast } from "./MatchupForecast";
import type { WaiverPlan } from "./league-fantasy-model";

afterEach(cleanup);
it("gates partial and newly-started diagnostic totals while keeping a complete unknown-budget baseline", () => {
  const plan = {
    status: "incomplete",
    evaluation_state: "conditional_opportunities",
    baseline: forecast(),
    projection_metadata: {
      schedule_coverage: { complete: true, source: "espn_schedule", fallback: true },
      "actuals:user": { complete: true },
    },
  } as unknown as WaiverPlan;
  expect(matchupForecastData(plan).complete).toBe(true);
  expect(matchupForecastData(plan).sourceLabel).toBe("ESPN schedule · fallback");
  plan.projection_metadata!["newly_started:user"] = { complete: false };
  const { container, rerender } = render(
    <MatchupForecast {...matchupForecastData(plan)} targets={targets} hasMoves={false} />,
  );
  expect(container.querySelector('[data-category="pts"] td:nth-of-type(2)')).toHaveTextContent(
    "——Unknown",
  );
  expect(container.querySelector('[data-category="pts"] td:first-of-type')).toHaveTextContent(
    "4050",
  );
  plan.projection_metadata!["actuals:user"].complete = false;
  rerender(<MatchupForecast {...matchupForecastData(plan)} targets={targets} hasMoves={false} />);
  expect(container.querySelector('[data-category="pts"] td:first-of-type')).toHaveTextContent(
    "—50",
  );
  expect(matchupForecastData(undefined).complete).toBe(false);
  plan.status = "unavailable";
  expect(matchupForecastData(plan).complete).toBe(false);
});
const targets: Category[] = ["pts", "ast", "reb", "fg_pct", "to"];
function forecast(): PlanForecast {
  return {
    basis: "forecast",
    // Stored percentages intentionally disagree: the makes/attempts are authoritative.
    totals: {
      pts: 120,
      ast: 35,
      reb: 80,
      stl: 10,
      blk: 5,
      threes: 12,
      to: 15,
      fgm: 30,
      fga: 60,
      fg_pct: 0.9,
      ftm: 15,
      fta: 20,
    },
    opponent_totals: {
      pts: 110,
      ast: 35,
      reb: 90,
      stl: 8,
      blk: 5,
      threes: 15,
      to: 20,
      fgm: 25,
      fga: 60,
      ftm: 16,
      fta: 20,
    },
    actual_primitives: {
      user: { pts: 40, fgm: 10, fga: 25, ftm: 4, fta: 5, to: 6 },
      opponent: { pts: 50, fgm: 12, fga: 25, ftm: 5, fta: 5, to: 8 },
    },
    games: 8,
    minutes: 240,
    probability_five_wins: null,
  };
}
it("shows all nine current and end-week comparisons, focus and projected W-L-T", () => {
  const { container } = render(
    <MatchupForecast baseline={forecast()} targets={targets} hasMoves={false} />,
  );
  expect(screen.getByRole("table")).toBeVisible();
  expect(container.querySelectorAll("tbody tr")).toHaveLength(9);
  expect(container.querySelectorAll('[data-focus="true"]')).toHaveLength(5);
  expect(screen.getByText("4–3–2 W–L–T")).toBeVisible();
  const pts = within(container.querySelector('[data-category="pts"]')! as HTMLElement);
  expect(pts.getByText("40")).toBeVisible();
  expect(pts.getByText("50")).toBeVisible();
  expect(pts.getByText("120")).toBeVisible();
  expect(pts.getByText("110")).toBeVisible();
  expect(screen.getByText(/No recommended moves/)).toBeVisible();
  expect(container.querySelector('[data-category="to"] .ww-edge-winning')).toHaveTextContent("Win");
  expect(container.querySelector('[data-category="ast"] .ww-edge-tied')).toHaveTextContent("Tie");
  expect(container.querySelector('[data-category="reb"] .ww-edge-losing')).toHaveTextContent(
    "Loss",
  );
});
it("uses whole-plan totals and weighted shooting rather than per-move or stored percent sums", () => {
  const before = forecast();
  const after = {
    ...before,
    totals: { ...before.totals, pts: 130, to: 13, fgm: 35, fga: 80, ftm: 16, fta: 22 },
  };
  const { container } = render(
    <MatchupForecast baseline={before} projected={after} targets={targets} hasMoves />,
  );
  const fg = container.querySelector('[data-category="fg_pct"]')!;
  expect(fg).toHaveTextContent("40.00%48.00%50.00%41.67%Win43.75%-6.25 ppWin");
  expect(fg.querySelector(".ww-loss")).toHaveTextContent("-6.25 pp");
  expect(container.querySelector('[data-category="to"] .ww-gain')).toHaveTextContent("-2");
  expect(container.querySelector('[data-category="pts"] td:last-child')).toHaveTextContent(
    "130+10Win",
  );
  expect(screen.getByRole("columnheader", { name: /After plan/ })).toBeVisible();
});
it("keeps legitimate zero but treats missing, non-finite, unweighted and recorded-only forecasts as unknown", () => {
  expect(forecastValue({ pts: 0 }, "pts")).toBe(0);
  expect(forecastValue({ pts: Number.NaN }, "pts")).toBeNull();
  expect(forecastValue({ fgm: Number.POSITIVE_INFINITY, fga: 20 }, "fg_pct")).toBeNull();
  expect(forecastValue({ ft_pct: 0.8 }, "ft_pct")).toBeNull();
  expect(forecastValue({ ftm: 0, fta: 0 }, "ft_pct")).toBeNull();
  const { container } = render(
    <MatchupForecast
      baseline={{ ...forecast(), basis: "recorded" }}
      targets={targets}
      hasMoves={false}
    />,
  );
  expect(screen.getByText("0–0–0 W–L–T · 9 unknown")).toBeVisible();
  expect(container.querySelector('[data-category="pts"] td:first-of-type')).toHaveTextContent(
    "4050",
  );
  expect(container.querySelector('[data-category="pts"] td:nth-of-type(2)')).toHaveTextContent(
    "——Unknown",
  );
  expect(screen.getByRole("status")).toHaveTextContent("inputs are unavailable");
});
it("preserves complete category rows during partial inputs and saved refresh", () => {
  const baseline = forecast();
  delete baseline.opponent_totals!.pts;
  const { container, rerender } = render(
    <MatchupForecast baseline={baseline} targets={targets} hasMoves={false} />,
  );
  expect(screen.getByText("3–3–2 W–L–T · 1 unknown")).toBeVisible();
  rerender(<MatchupForecast baseline={baseline} targets={targets} hasMoves={false} readOnly />);
  expect(screen.getByText("Saved · read-only")).toBeVisible();
  expect(container.querySelectorAll("tbody tr")).toHaveLength(LEAGUE_CATEGORIES.length);
  expect(container.querySelector('[data-category="pts"]')).toHaveTextContent("120—Unknown");
});
it("retains known counting zeros when only zero-attempt percentages are undefined", () => {
  const baseline = forecast();
  baseline.totals = {
    pts: 0,
    reb: 0,
    ast: 0,
    stl: 0,
    blk: 0,
    threes: 0,
    to: 0,
    fgm: 0,
    fga: 0,
    ftm: 0,
    fta: 0,
  };
  const plan = {
    status: "incomplete",
    evaluation_state: "required_inputs_unknown",
    data_gaps: [],
    baseline,
    projection_metadata: { schedule_coverage: { complete: true } },
  } as unknown as WaiverPlan;
  const { container } = render(
    <MatchupForecast {...matchupForecastData(plan)} targets={targets} hasMoves={false} />,
  );
  expect(container.querySelector('[data-category="pts"] td:nth-of-type(2)')).toHaveTextContent(
    "0110Loss",
  );
  expect(container.querySelector('[data-category="fg_pct"] td:nth-of-type(2)')).toHaveTextContent(
    "—41.67%Unknown",
  );
  plan.data_gaps = ["Roster rates missing"];
  expect(matchupForecastData(plan).complete).toBe(false);
});
