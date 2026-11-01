import {
  LEAGUE_CATEGORIES,
  formatCategory,
  type Category,
  type LeaguePlayer,
  type PickupRecommendation,
  type PlanArithmetic,
} from "./league-fantasy-model";

export function signedChange(value: number | null | undefined, key?: Category) {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  return `${value > 0 ? "+" : ""}${key?.endsWith("pct") ? `${(value * 100).toFixed(2)} pp` : value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
const number = (value: number | null | undefined) =>
  value == null ? "?" : value.toLocaleString(undefined, { maximumFractionDigits: 2 });

/** All values come from the paired full-roster forecast, never a pickup-only estimate. */
export function WaiverArithmetic({
  move,
  addPlayer,
  dropPlayer,
}: {
  move: PickupRecommendation;
  addPlayer?: LeaguePlayer;
  dropPlayer?: LeaguePlayer;
}) {
  return (
    <div className="move-arithmetic">
      <p>{move.rationale}</p>
      <p>
        Selected per-game rate × usable starts. Drop loss counts starts lost after the effective
        date; other lineup changes include displaced and recovered roster starts. Banked actuals
        stay fixed. A negative TO change helps; percentages use team makes / attempts.
      </p>
      {move.lineup_changes && (
        <p className="lineup-start-changes">
          Other roster starts: {move.lineup_changes.displaced.length} displaced ·{" "}
          {move.lineup_changes.recovered.length} recovered ·{" "}
          {signedChange(move.lineup_changes.net_starts)} net.
          {move.lineup_changes.displaced.length > 0 && (
            <>
              {" "}
              Displaced:{" "}
              {move.lineup_changes.displaced.map((row) => `${row.name} (${row.date})`).join(", ")}.
            </>
          )}
          {move.lineup_changes.recovered.length > 0 && (
            <>
              {" "}
              Recovered:{" "}
              {move.lineup_changes.recovered.map((row) => `${row.name} (${row.date})`).join(", ")}.
            </>
          )}
        </p>
      )}
      <CategoryNetSummary arithmetic={move.arithmetic} impacts={move.category_impacts} />
      <p className="arithmetic-scroll-hint">
        Scroll the table horizontally on narrow screens to compare every term.
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
              const impact = move.arithmetic?.categories[key] ?? move.category_impacts?.[key];
              const exact = move.arithmetic?.categories[key];
              const weighted =
                exact?.makes && exact.attempts
                  ? {
                      before_makes: exact.makes.before,
                      before_attempts: exact.attempts.before,
                      after_makes: exact.makes.after,
                      after_attempts: exact.attempts.after,
                      add_makes_rate: calc?.weighted?.add_makes_rate,
                      add_attempts_rate: calc?.weighted?.add_attempts_rate,
                      drop_makes_rate: calc?.weighted?.drop_makes_rate,
                      drop_attempts_rate: calc?.weighted?.drop_attempts_rate,
                    }
                  : calc?.weighted;
              const shooting = key.endsWith("pct");
              const net =
                impact?.before != null && impact.after != null
                  ? impact.after - impact.before
                  : calc?.net_total;
              const beneficial = net != null && (key === "to" ? net < 0 : net > 0);
              const harmful = net != null && (key === "to" ? net > 0 : net < 0);
              const shootingOther = (part: "makes" | "attempts") => {
                if (exact?.[part]?.spillover != null) return exact[part].spillover;
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
                  <th scope="row">
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
      {move.zero_drop_reason && (
        <p className="zero-drop-reason">
          <b>Why drop loss is zero:</b> {move.zero_drop_reason}
        </p>
      )}
      <div className="rate-provenance">
        <RateEvidence player={addPlayer} evidence={move.rate_evidence?.add} role="Pickup" />
        <RateEvidence player={dropPlayer} evidence={move.rate_evidence?.drop} role="Drop" />
      </div>
    </div>
  );
}

export function OverallPlanImpact({ arithmetic }: { arithmetic: PlanArithmetic }) {
  return (
    <div className="overall-plan-impact">
      <CategoryNetSummary arithmetic={arithmetic} />
      <p className="arithmetic-scroll-hint">
        All nine net changes above; scroll the arithmetic table horizontally for every term.
      </p>
      <div
        className="league-table-wrap"
        role="region"
        tabIndex={0}
        aria-label="Overall plan category changes"
      >
        <table>
          <caption>
            Entire ordered plan · before + pickup − drop + other roster changes = after
          </caption>
          <thead>
            <tr>
              <th>Category</th>
              <th>Before plan</th>
              <th>Added</th>
              <th>Dropped</th>
              <th>Other roster net</th>
              <th>After plan</th>
              <th>Full-team net</th>
            </tr>
          </thead>
          <tbody>
            {LEAGUE_CATEGORIES.map(({ key, label }) => {
              const row = arithmetic?.categories[key];
              const delta = row?.net;
              const state =
                delta == null || delta === 0
                  ? ""
                  : (key === "to" ? delta < 0 : delta > 0)
                    ? "league-winning"
                    : "league-losing";
              return (
                <tr key={key}>
                  <th scope="row">
                    {label}
                    {key === "to" ? " ↓" : ""}
                  </th>
                  <td>
                    {formatCategory(row?.before ?? null, key)}
                    {row?.makes && (
                      <small>
                        {number(row.makes.before)} / {number(row.attempts?.before)}
                      </small>
                    )}
                  </td>
                  <td>
                    {row?.makes
                      ? `${number(row.makes.add)} / ${number(row.attempts?.add)}`
                      : number(row?.add)}
                  </td>
                  <td>
                    {row?.makes
                      ? `${number(row.makes.drop)} / ${number(row.attempts?.drop)}`
                      : number(row?.drop)}
                  </td>
                  <td>
                    {row?.makes
                      ? `${signedChange(row.makes.spillover)} / ${signedChange(row.attempts?.spillover)}`
                      : signedChange(row?.spillover)}
                  </td>
                  <td>
                    {formatCategory(row?.after ?? null, key)}
                    {row?.makes && (
                      <small>
                        {number(row.makes.after)} / {number(row.attempts?.after)}
                      </small>
                    )}
                  </td>
                  <td className={state}>{signedChange(delta, key)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RateEvidence({
  player,
  role,
  evidence: selected,
}: {
  player?: LeaguePlayer;
  role: string;
  evidence?: LeaguePlayer["rate_provenance"];
}) {
  const evidence = selected ?? player?.rate_provenance;
  return (
    <p>
      {role} rate sample:{" "}
      {evidence ? (
        <>
          {evidence.source ?? "Source unknown"} · season {evidence.season ?? "unknown"} ·{" "}
          {evidence.games ?? "unknown"} observed games
          {evidence.small_sample ? " · small sample" : ""} · {evidence.status} · fetched{" "}
          {evidence.fetched_at ?? "time unavailable"}
          {evidence.fallback ? ` · fallback: ${evidence.reason ?? "NBA sample unavailable"}` : ""}
        </>
      ) : (
        "Provenance unavailable; missing loss inputs do not establish zero loss."
      )}
    </p>
  );
}

function CategoryNetSummary({
  arithmetic,
  impacts,
}: {
  arithmetic?: PlanArithmetic;
  impacts?: PickupRecommendation["category_impacts"];
}) {
  return (
    <div className="nine-category-net" aria-label="All nine net changes">
      {LEAGUE_CATEGORIES.map(({ key, label }) => {
        const impact = impacts?.[key];
        const net =
          arithmetic?.categories[key]?.net ??
          (impact?.before != null && impact.after != null ? impact.after - impact.before : null);
        const style =
          net == null || net === 0
            ? ""
            : (key === "to" ? net < 0 : net > 0)
              ? "league-winning"
              : "league-losing";
        return (
          <span key={key}>
            {label}
            {key === "to" ? " ↓" : ""}
            <b className={style}>{signedChange(net, key)}</b>
          </span>
        );
      })}
    </div>
  );
}
