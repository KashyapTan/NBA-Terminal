import type { WaiverPlan } from "./league-fantasy-model";

/** Summary never converts unavailable evidence into a negative player evaluation. */
export function waiverStatus(plan: WaiverPlan | null) {
  const state =
    plan?.evaluation_state ??
    (!plan || plan.status !== "ready"
      ? "required_inputs_unknown"
      : plan.recommended_plan?.budget_before === 0
        ? "known_zero_acquisitions"
        : plan.recommended_plan?.moves.length
          ? "confirmed_ordered_plan"
          : "evaluated_no_material_benefit");
  const summaries = {
    required_inputs_unknown: [
      "Plan unavailable: required inputs incomplete",
      "Today’s useful available players are not yet determinable. Missing evidence prevents a supported comparison; it does not establish that no free agent helps.",
    ],
    known_zero_acquisitions: [
      "No acquisition budget remaining",
      "Your verified acquisition allowance is zero. This does not establish whether an available player would improve the roster.",
    ],
    conditional_opportunities: [
      "Acquisition budget unknown · conditional preview",
      "Forecast inputs support comparing pickup/drop pairs, but no transaction is confirmed. Verify matchup cap, used and remaining acquisitions in ESPN, then enter the counts below.",
    ],
    confirmed_ordered_plan: [
      "Confirmed ordered plan",
      "The explored sequence passes the supplied budget and protection rules. Review all nine category tradeoffs; ESPN remains authoritative for transaction validation.",
    ],
    evaluated_no_material_benefit: [
      "No supported beneficial sequence",
      "No materially beneficial sequence passed the guards within the explored market and search bounds. This is a remaining-matchup comparison, not proof that every free agent is unhelpful today.",
    ],
  };
  return { state, title: summaries[state][0], explanation: summaries[state][1] };
}

export function WaiverStatus({
  plan,
  onRecover,
}: {
  plan: WaiverPlan | null;
  onRecover: () => void;
}) {
  const status = waiverStatus(plan);
  return (
    <section
      className={`waiver-status waiver-status-${status.state}`}
      aria-label="Waiver evaluation status"
    >
      <h3>{status.title}</h3>
      <p role="status">{status.explanation}</p>
      {(status.state === "required_inputs_unknown" ||
        status.state === "conditional_opportunities") && (
        <button type="button" onClick={onRecover}>
          Review missing inputs & recovery controls
        </button>
      )}
      {plan && (plan.reasons.length > 0 || plan.data_gaps.length > 0) && (
        <details>
          <summary>
            Evaluation diagnostics ({new Set([...plan.reasons, ...plan.data_gaps]).size})
          </summary>
          <ul>
            {[...new Set([...plan.reasons, ...plan.data_gaps])].map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
