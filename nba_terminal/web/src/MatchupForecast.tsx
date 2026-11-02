import { InfoTooltip } from "./InfoTooltip";
import {
  type Category,
  compareCategory,
  formatCategory,
  LEAGUE_CATEGORIES,
  type PlanForecast,
  type Stats,
} from "./league-fantasy-model";
import { signedChange } from "./WaiverArithmetic";

export interface MatchupForecastProps {
  baseline?: PlanForecast | null;
  projected?: PlanForecast | null;
  hasMoves: boolean;
  targets: Category[];
  readOnly?: boolean;
}

// A percentage without its team makes/attempts cannot establish a weighted forecast.
export function forecastValue(stats: Stats | null | undefined, key: Category): number | null {
  const finite = (value: number | null | undefined): value is number =>
    value != null && Number.isFinite(value);
  if (key === "fg_pct" || key === "ft_pct") {
    const made = stats?.[key === "fg_pct" ? "fgm" : "ftm"];
    const attempts = stats?.[key === "fg_pct" ? "fga" : "fta"];
    return finite(made) && finite(attempts) && attempts > 0 ? made / attempts : null;
  }
  const value = stats?.[key];
  return finite(value) ? value : null;
}

const edgeLabel = { winning: "Win", losing: "Loss", tied: "Tie", unknown: "Unknown" };
const display = (value: number | null, key: Category) =>
  value == null ? "—" : formatCategory(value, key);

/** Only source forecast totals are displayed: no per-move summing or browser lineup estimates. */
export function MatchupForecast({
  baseline,
  projected,
  hasMoves,
  targets,
  readOnly,
}: MatchupForecastProps) {
  const before = baseline?.basis === "forecast" ? baseline : null;
  const after = hasMoves && projected?.basis === "forecast" ? projected : null;
  const rows = LEAGUE_CATEGORIES.map(({ key, label }) => {
    const current = forecastValue(baseline?.actual_primitives?.user, key);
    const currentOpponent = forecastValue(baseline?.actual_primitives?.opponent, key);
    const user = forecastValue(before?.totals, key);
    const opponent = forecastValue(before?.opponent_totals, key);
    const planned = forecastValue(after?.totals, key);
    const plannedOpponent = forecastValue(after?.opponent_totals, key);
    const change = user != null && planned != null ? planned - user : null;
    return {
      key,
      label,
      current,
      currentOpponent,
      user,
      opponent,
      planned,
      change,
      edge: compareCategory(user, opponent, key),
      plannedEdge: compareCategory(planned, plannedOpponent, key),
    };
  });
  function score(planned: boolean) {
    const states = rows.map((row) => (planned ? row.plannedEdge : row.edge));
    const count = (state: string) => states.filter((value) => value === state).length;
    return `${count("winning")}–${count("losing")}–${count("tied")} W–L–T${count("unknown") ? ` · ${count("unknown")} unknown` : ""}`;
  }
  const incomplete = rows.some(
    (row) => row.edge === "unknown" || (hasMoves && row.plannedEdge === "unknown"),
  );
  return (
    <section className="ww-forecast" aria-label="End-of-matchup comparison">
      <div className="ww-section-label">
        <h3>End of matchup</h3>
        <InfoTooltip label="About the matchup forecast">
          Now is banked scoring in this matchup. End week adds remaining usable lineup production
          for both teams. After plan uses the entire ordered plan. FG% and FT% use total makes /
          attempts; fewer TO wins. Stars mark your five focus categories. Estimates can change.
        </InfoTooltip>
      </div>
      <p className="ww-forecast-score">
        <span>
          Projected <b>{score(false)}</b>
        </span>
        {hasMoves && (
          <span>
            After plan <b>{score(true)}</b>
          </span>
        )}
        {readOnly && <span className="ww-forecast-caution">Saved · read-only</span>}
      </p>
      <p className="ww-forecast-legend">You / Opp · ★ Focus · TO ↓ lower wins</p>
      <table className="ww-forecast-table">
        <caption className="ww-sr-only">
          All nine categories, current scoring and end-of-matchup forecasts
        </caption>
        <thead>
          <tr>
            <th scope="col">Cat</th>
            <th scope="col">
              Now<small>You / Opp</small>
            </th>
            <th scope="col">
              End week<small>You / Opp</small>
            </th>
            <th scope="col">
              After plan<small>You · change</small>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const gain = row.change != null && (row.key === "to" ? row.change < 0 : row.change > 0);
            const loss = row.change != null && (row.key === "to" ? row.change > 0 : row.change < 0);
            return (
              <tr key={row.key} data-category={row.key} data-focus={targets.includes(row.key)}>
                <th scope="row">
                  {row.label}
                  {row.key === "to" && " ↓"}
                  {targets.includes(row.key) && (
                    <span className="ww-focus" aria-label="Focus category">
                      {" "}
                      ★
                    </span>
                  )}
                </th>
                <td>
                  <span>{display(row.current, row.key)}</span>
                  <small>{display(row.currentOpponent, row.key)}</small>
                </td>
                <td>
                  <span>{display(row.user, row.key)}</span>
                  <small>{display(row.opponent, row.key)}</small>
                  <b className={`ww-edge ww-edge-${row.edge}`}>{edgeLabel[row.edge]}</b>
                </td>
                <td>
                  <span>{display(row.planned, row.key)}</span>
                  <small className={gain ? "ww-gain" : loss ? "ww-loss" : ""}>
                    {row.change == null ? "—" : signedChange(row.change, row.key)}
                  </small>
                  {hasMoves && (
                    <b className={`ww-edge ww-edge-${row.plannedEdge}`}>
                      {edgeLabel[row.plannedEdge]}
                    </b>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {(incomplete || !hasMoves) && (
        <p className="ww-forecast-note" role="status">
          {incomplete
            ? "Some forecast inputs are unavailable (—). See Full analysis & data."
            : "No recommended moves · baseline forecast shown."}
        </p>
      )}
    </section>
  );
}
