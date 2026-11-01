import {
  LEAGUE_CATEGORIES,
  formatCategory,
  type Category,
  type PickupRecommendation,
} from "./league-fantasy-model";

export function signedChange(value: number | null | undefined, key?: Category) {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  return `${value > 0 ? "+" : ""}${key?.endsWith("pct") ? `${(value * 100).toFixed(2)} pp` : value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
const number = (value: number | null | undefined) =>
  value == null ? "?" : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

/** All values come from the paired full-roster forecast, never a pickup-only estimate. */
export function WaiverArithmetic({ move }: { move: PickupRecommendation }) {
  return (
    <div className="move-arithmetic">
      <p>{move.rationale}</p>
      <p>
        Selected per-game rate × usable starts. Drop loss counts starts lost after the effective
        date; other lineup changes include displaced and recovered roster starts. Banked actuals
        stay fixed. A negative TO change helps; percentages use team makes / attempts.
      </p>
      <div
        className="league-table-wrap"
        tabIndex={0}
        role="region"
        aria-label="All nine move calculations"
      >
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Team before</th>
              <th>Pickup contribution</th>
              <th>Drop loss</th>
              <th>Other lineup net</th>
              <th>Team after</th>
              <th>Full-team net</th>
            </tr>
          </thead>
          <tbody>
            {LEAGUE_CATEGORIES.map(({ key, label }) => {
              const calc = move.calculation?.[key];
              const impact = move.category_impacts?.[key];
              const weighted = calc?.weighted;
              const shooting = key.endsWith("pct");
              const net =
                impact?.before != null && impact.after != null
                  ? impact.after - impact.before
                  : calc?.net_total;
              const beneficial = net != null && (key === "to" ? net < 0 : net > 0);
              const harmful = net != null && (key === "to" ? net > 0 : net < 0);
              const shootingOther = (part: "makes" | "attempts") => {
                const before = weighted?.[part === "makes" ? "before_makes" : "before_attempts"];
                const after = weighted?.[part === "makes" ? "after_makes" : "after_attempts"];
                const add = weighted?.[part === "makes" ? "add_makes_rate" : "add_attempts_rate"];
                const drop =
                  weighted?.[part === "makes" ? "drop_makes_rate" : "drop_attempts_rate"];
                return before != null &&
                  after != null &&
                  add != null &&
                  drop != null &&
                  calc?.add_starts != null &&
                  calc.drop_starts != null
                  ? after - before - add * calc.add_starts + drop * calc.drop_starts
                  : null;
              };
              return (
                <tr key={key}>
                  <th>
                    {label}
                    {key === "to" ? " ↓" : ""}
                  </th>
                  <td>
                    {formatCategory(impact?.before ?? null, key)}
                    {shooting && (
                      <small>
                        {number(weighted?.before_makes)} / {number(weighted?.before_attempts)}
                      </small>
                    )}
                  </td>
                  <td>
                    {shooting
                      ? `${number(weighted?.add_makes_rate)} / ${number(weighted?.add_attempts_rate)}`
                      : number(calc?.add_rate)}{" "}
                    × {number(calc?.add_starts)} starts
                    {!shooting && <small>= {number(calc?.added_total)}</small>}
                  </td>
                  <td>
                    {shooting
                      ? `${number(weighted?.drop_makes_rate)} / ${number(weighted?.drop_attempts_rate)}`
                      : number(calc?.drop_rate)}{" "}
                    × {number(calc?.drop_starts)} lost starts
                    {!shooting && <small>= {number(calc?.lost_total)}</small>}
                  </td>
                  <td>
                    {shooting
                      ? `${signedChange(shootingOther("makes"))} / ${signedChange(shootingOther("attempts"))}`
                      : signedChange(calc?.lineup_other_net)}
                  </td>
                  <td>
                    {formatCategory(impact?.after ?? null, key)}
                    {shooting && (
                      <small>
                        {number(weighted?.after_makes)} / {number(weighted?.after_attempts)}
                      </small>
                    )}
                  </td>
                  <td className={beneficial ? "league-winning" : harmful ? "league-losing" : ""}>
                    <b>{signedChange(net, key)}</b>
                    {net === 0 && <small>No change</small>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!move.calculation && (
        <p role="status">
          Usable-start arithmetic is missing. This move cannot be treated as a verified benefit.
        </p>
      )}
      <p className="rate-provenance">
        Rates above are the forecast’s selected sample. Rate source, season and fallback provenance
        must accompany the optimizer result; missing provenance is unverified, never proof of a zero
        drop loss.
      </p>
    </div>
  );
}

export function OverallPlanImpact({
  impacts,
}: {
  impacts: PickupRecommendation["category_impacts"];
}) {
  return (
    <div
      className="league-table-wrap"
      role="region"
      tabIndex={0}
      aria-label="Overall plan category changes"
    >
      <table>
        <caption>Entire ordered plan · full-team projected finals</caption>
        <thead>
          <tr>
            <th>Category</th>
            <th>Before plan</th>
            <th>After plan</th>
            <th>Net change</th>
          </tr>
        </thead>
        <tbody>
          {LEAGUE_CATEGORIES.map(({ key, label }) => {
            const impact = impacts?.[key];
            const delta =
              impact?.before != null && impact.after != null ? impact.after - impact.before : null;
            const state =
              delta == null || delta === 0
                ? ""
                : (key === "to" ? delta < 0 : delta > 0)
                  ? "league-winning"
                  : "league-losing";
            return (
              <tr key={key}>
                <th>
                  {label}
                  {key === "to" ? " ↓" : ""}
                </th>
                <td>{formatCategory(impact?.before ?? null, key)}</td>
                <td>{formatCategory(impact?.after ?? null, key)}</td>
                <td className={state}>{signedChange(delta, key)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
