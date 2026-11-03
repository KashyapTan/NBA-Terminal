import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { DailyLineup } from "./DailyLineup";
import type { DailyLineupDay, PlanForecast } from "./league-fantasy-model";

afterEach(cleanup);
function forecast(name = "Owned guard"): PlanForecast {
  const day: DailyLineupDay = {
    date: "2026-11-02",
    owner: "user",
    capacity: 10,
    available_slots: 10,
    focus: ["pts", "reb", "ast", "fg_pct", "to"],
    players: [
      {
        player_id: "1",
        name,
        team: "BOS",
        positions: ["PG", "G"],
        assigned_slot: "PG",
        state: "start",
        playing: true,
        reason: "focus_selected",
        rates: { pts: 20, ast: 8, fgm: 5, fga: 12, to: 2 },
      },
      {
        player_id: "2",
        name: "Bench big",
        team: "IND",
        positions: ["C"],
        assigned_slot: null,
        state: "bench",
        playing: true,
        reason: "intentional_focus_bench",
        rates: { pts: 100 },
      },
      {
        player_id: "3",
        name: "Already started",
        team: "ATL",
        positions: ["SF"],
        assigned_slot: "SF",
        state: "locked",
        playing: true,
        reason: "already_started_or_banked",
        rates: {},
      },
    ],
  };
  return {
    games: 1,
    minutes: 30,
    probability_five_wins: null,
    totals: {},
    daily_lineups: [day, { ...day, date: "2026-11-03", players: [] }],
  };
}
it("renders source decisions without ranking high raw stats; current roster is default", () => {
  render(<DailyLineup baseline={forecast()} projected={forecast("Unowned preview")} hasMoves />);
  expect(
    within(screen.getByRole("list", { name: "Start players" })).getAllByRole("listitem"),
  ).toHaveLength(2);
  expect(
    within(screen.getByRole("list", { name: "Bench players" })).getByText("Bench big"),
  ).toBeVisible();
  expect(screen.queryByText("Unowned preview")).not.toBeInTheDocument();
  expect(screen.getByText("2/10 active")).toBeVisible();
  expect(screen.getByText("BOS · PG / G")).toBeVisible();
  expect(screen.getByText(/5.0\/12.0 FG/)).toBeVisible();
  expect(screen.getByText(/avoids harm/)).toBeVisible();
  fireEvent.click(screen.getByRole("checkbox", { name: "Preview after planned moves" }));
  expect(screen.getByText("Unowned preview")).toBeVisible();
  expect(screen.getByText(/After plan preview · hypothetical/)).toBeVisible();
});
it("keeps chosen date across observation refresh; shows recomputed source selection", () => {
  const { rerender } = render(<DailyLineup baseline={forecast()} hasMoves={false} />);
  fireEvent.change(screen.getByLabelText("Lineup day"), { target: { value: "2026-11-03" } });
  expect(screen.getByText("No eligible starts today")).toBeVisible();
  rerender(<DailyLineup baseline={forecast("New focus guard")} hasMoves={false} readOnly />);
  expect(screen.getByLabelText("Lineup day")).toHaveValue("2026-11-03");
  expect(screen.getByText("Saved · read only")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Lineup day"), { target: { value: "2026-11-02" } });
  expect(screen.getByText("New focus guard")).toBeVisible();
});
it("shows honest missing/partial states and keyboard/tap help", () => {
  const { rerender } = render(<DailyLineup hasMoves={false} complete={false} />);
  expect(screen.getByText(/Partial data/)).toBeVisible();
  expect(screen.getByText(/Daily lineup unavailable/)).toBeVisible();
  const help = screen.getByRole("button", { name: "About daily lineup" });
  fireEvent.focus(help);
  fireEvent.click(help);
  expect(help).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(help, { key: "Escape" });
  expect(help).toHaveAttribute("aria-expanded", "false");
  const f = forecast();
  f.daily_lineups![0].capacity = 1;
  rerender(<DailyLineup baseline={f} hasMoves={false} />);
  expect(screen.getByText(/3 available & playing · Choose/)).toBeVisible();
});
