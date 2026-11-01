import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { WaiverPlan } from "./league-fantasy-model";
import { EmptyOrderedPlan, WaiverStatus, waiverStatus } from "./WaiverStatus";

afterEach(cleanup);
const plan = (state: WaiverPlan["evaluation_state"]) =>
  ({
    status:
      state === "required_inputs_unknown" || state === "conditional_opportunities"
        ? "incomplete"
        : "ready",
    evaluation_state: state,
    reasons: ["Specific missing provider field"],
    data_gaps: ["Specific missing provider field", "Schedule missing"],
  }) as WaiverPlan;

it.each([
  ["required_inputs_unknown", "not yet determinable"],
  ["known_zero_acquisitions", "allowance is zero"],
  ["conditional_opportunities", "no transaction is confirmed"],
  ["confirmed_ordered_plan", "passes the supplied budget"],
  ["evaluated_no_material_benefit", "within the explored market"],
] as const)("explains %s without conflating budget and player value", (state, text) => {
  expect(waiverStatus(plan(state)).explanation).toContain(text);
});

it("keeps missing facts discoverable in compact diagnostics and opens recovery controls", async () => {
  const recover = vi.fn();
  render(<WaiverStatus plan={plan("required_inputs_unknown")} onRecover={recover} />);
  expect(screen.getByRole("status")).toHaveTextContent("not yet determinable");
  expect(screen.getByText("Evaluation diagnostics (2)").closest("details")).not.toHaveAttribute(
    "open",
  );
  expect(screen.getAllByText("Specific missing provider field")).toHaveLength(1);
  await userEvent.click(screen.getByRole("button", { name: /recovery controls/ }));
  expect(recover).toHaveBeenCalledOnce();
});

it("explains beneficial conditional pairs and the exact missing budget field beside the empty sequence", async () => {
  const recover = vi.fn();
  const conditional = {
    ...plan("conditional_opportunities"),
    data_gaps: ["Current matchup acquisitions used unknown: provider counter unavailable."],
    reasons: ["Acquisition budget unknown; no ordered moves confirmed."],
    recommendations: Array.from({ length: 26 }, () => ({})),
    search: {
      candidate_pool: 398,
      evaluations: 804,
      legal_drop_ids: ["a"],
      evaluated_drop_ids: ["a"],
    },
  } as WaiverPlan;
  render(<EmptyOrderedPlan plan={conditional} onRecover={recover} />);
  expect(screen.getByRole("heading")).toHaveTextContent("acquisition budget unverified");
  expect(screen.getByText(/26 beneficial conditional alternatives/)).toBeVisible();
  expect(screen.getByText(/Current matchup acquisitions used unknown/)).toBeVisible();
  expect(screen.getByText(/Yesterday’s usage is not current confirmation/)).toBeVisible();
  expect(screen.getByText(/398 candidates · 804 evaluations/)).toBeVisible();
  expect(screen.queryByText(/No supported beneficial sequence/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button"));
  expect(recover).toHaveBeenCalledOnce();
});

it.each([
  "required_inputs_unknown",
  "known_zero_acquisitions",
  "evaluated_no_material_benefit",
] as const)("keeps %s distinct in the ordered-plan section", (state) => {
  render(<EmptyOrderedPlan plan={plan(state)} onRecover={vi.fn()} />);
  expect(screen.getByRole("heading")).toHaveTextContent(waiverStatus(plan(state)).title);
  expect(screen.getByText(/Specific missing provider field/)).toBeVisible();
  expect(screen.queryByText(/beneficial conditional alternatives found/)).not.toBeInTheDocument();
  expect(screen.getByText(/Next step:/)).toBeVisible();
});
