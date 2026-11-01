import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { WaiverPlan } from "./league-fantasy-model";
import { WaiverStatus, waiverStatus } from "./WaiverStatus";

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
