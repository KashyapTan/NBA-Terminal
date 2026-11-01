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
      "Acquisition constraints unverified · conditional preview",
      "Forecast inputs support comparing pickup/drop pairs, but no transaction is confirmed. Verify the unresolved acquisition counts or rules shown below.",
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

/** Keep the decisive cause beside the empty sequence, where users look for moves. */
export function EmptyOrderedPlan({
  plan,
  unavailableReason,
  onRecover,
  onRefresh,
}: {
  plan: WaiverPlan | null;
  unavailableReason?: string | null;
  onRecover: () => void;
  onRefresh?: () => void;
}) {
  const status = waiverStatus(plan);
  const diagnostics = [...new Set([...(plan?.data_gaps ?? []), ...(plan?.reasons ?? [])])];
  const conditional = status.state === "conditional_opportunities";
  const actions = {
    required_inputs_unknown:
      "Refresh league data, then review the missing inputs below. Unknown inputs are not a no-benefit result.",
    conditional_opportunities:
      "Verify the current matchup cap, used and remaining counts in ESPN, then enter and confirm them below. Yesterday’s usage is not current confirmation.",
    known_zero_acquisitions:
      "Keep the roster unless ESPN shows a different current allowance; correct the verified counts before recalculating.",
    evaluated_no_material_benefit:
      "Review the selected five, remaining dates, roster protection and explored market before recalculating. No guard-passing improvement was found within these bounds.",
    confirmed_ordered_plan: "Refresh the analysis to load the ordered moves.",
  };
  return (
    <div className="strategy-empty" aria-label="Why no ordered moves are confirmed">
      <h4>
        {conditional
          ? plan?.acquisition_budget?.daily_applicability === "daily"
            ? "Ordered plan withheld: daily acquisition ledger missing"
            : "Ordered plan withheld: acquisition budget unverified"
          : status.title}
      </h4>
      <p>
        {unavailableReason ||
          (conditional
            ? "Forecast inputs support pickup/drop comparisons; acquisition verification prevents an ordered plan."
            : status.explanation)}
      </p>
      {conditional && (
        <p>
          {plan?.recommendations?.length ?? 0} beneficial conditional alternative
          {plan?.recommendations?.length === 1 ? "" : "s"} found. Each is a competing single move,
          subject to verifying at least one acquisition; they are not an executable sequence.
        </p>
      )}
      {plan?.acquisition_budget && (
        <p>
          Matchup cap {plan.acquisition_budget.matchup_cap ?? "unknown"} · current used{" "}
          {plan.acquisition_budget.used ?? "unknown"} · remaining{" "}
          {plan.acquisition_budget.remaining ?? "unknown"}.
          {plan.acquisition_budget.daily_applicability === "daily"
            ? " A daily acquisition ledger is still required."
            : plan.acquisition_budget.daily_applicability === "unreported"
              ? " ESPN did not supply daily-limit applicability; it is separate from these matchup counts."
              : ""}
        </p>
      )}
      {diagnostics.length > 0 && (
        <>
          <ul>
            {diagnostics.slice(0, 3).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          {diagnostics.length > 3 && (
            <details>
              <summary>More evaluation reasons ({diagnostics.length - 3})</summary>
              <ul>
                {diagnostics.slice(3).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {plan?.search && (
        <p>
          Explored {plan.search.candidate_pool ?? "unknown"} candidates · {plan.search.evaluations}{" "}
          evaluations · {plan.search.evaluated_drop_ids?.length ?? "unknown"} of{" "}
          {plan.search.legal_drop_ids?.length ?? "unknown"} legal drops. Market coverage and search
          bounds limit this comparison independently of acquisition verification.
        </p>
      )}
      <p>
        <b>Next step:</b>{" "}
        {plan?.acquisition_budget?.daily_applicability === "daily" && conditional
          ? "ESPN reports a daily acquisition limit. A complete daily ledger is required; matchup totals alone cannot establish transaction legality."
          : unavailableReason
            ? "Resolve the analysis error above and retry."
            : actions[status.state]}
      </p>
      {(status.state === "required_inputs_unknown" || conditional) && (
        <button type="button" onClick={onRecover}>
          Review acquisition counts & required inputs
        </button>
      )}
      {onRefresh && (
        <button type="button" onClick={onRefresh}>
          Refresh league data
        </button>
      )}
    </div>
  );
}
