import {
  categoryValue,
  formatCategory,
  LEAGUE_CATEGORIES,
  type LeagueTeam,
} from "./league-fantasy-model";

const basisLabel = (source: string | null) =>
  source === "nba_derived"
    ? "NBA-derived reconstruction (unofficial)"
    : source === "espn_official"
      ? "ESPN official scoring (NBA reconstruction fallback)"
      : (source ?? "Unavailable");
const gapLabels: Record<string, string> = {
  historical_daily_lineup_missing: "Historical active scoring lineup missing",
  active_eligibility_unknown: "Historical active scoring eligibility unknown",
  schedule_missing: "NBA schedule missing",
  nba_player_game_missing: "NBA player/game production missing",
  duplicate_credit: "Conflicting duplicate scoring credit",
};
function groupedGaps(gaps: NonNullable<LeagueTeam["actuals"]>["nba_derived"]["gaps"]) {
  const groups = new Map<string, string[]>();
  for (const gap of gaps) {
    const key = typeof gap === "string" ? gap : gap.reason;
    const text =
      typeof gap === "string"
        ? gap
        : `${gapLabels[gap.reason] ?? gap.reason}${gap.period != null ? ` · scoring day ${gap.period}` : ""}${gap.player_id != null ? ` · player ${gap.player_id}` : ""}${gap.game_id ? ` · game ${gap.game_id}` : ""}`;
    groups.set(key, [...new Set([...(groups.get(key) ?? []), text])]);
  }
  return [...groups].map(([key, records]) => ({ key, label: gapLabels[key] ?? key, records }));
}

/** Keep provider scoring and reconstructed NBA production distinct. */
export function ActualSources({ teams }: { teams: (LeagueTeam | undefined)[] }) {
  return (
    <section className="actual-sources" aria-label="Actual scoring sources">
      <h3>Actual scoring & source coverage</h3>
      <p>
        ESPN is authoritative for league scoring, ownership and historical active lineups.
        NBA-derived production is a separate reconstruction. Historical active scoring lineups are
        required; today’s roster cannot establish past scoring eligibility.
      </p>
      {teams
        .filter((team): team is LeagueTeam => Boolean(team))
        .map((team) => {
          const actuals = team.actuals;
          const groups = groupedGaps(actuals?.nba_derived.gaps ?? []);
          const unknownCoverage =
            actuals?.nba_derived.expected_player_games == null ||
            actuals.nba_derived.gaps.some(
              (gap) =>
                typeof gap !== "string" &&
                [
                  "schedule_missing",
                  "historical_daily_lineup_missing",
                  "active_eligibility_unknown",
                ].includes(gap.reason),
            );
          const hasTotals =
            actuals &&
            [actuals.official.totals, actuals.nba_derived.totals, actuals.forecast_totals].some(
              (totals) => LEAGUE_CATEGORIES.some(({ key }) => categoryValue(totals, key) != null),
            );
          return (
            <article key={team.id}>
              <h4>{team.name}</h4>
              {actuals ? (
                <>
                  <p>
                    <b>Forecast actuals basis: {basisLabel(actuals.forecast_source)}</b> ·{" "}
                    {actuals.forecast_complete
                      ? "Complete scoring basis"
                      : "Partial / unverified scoring basis"}
                  </p>
                  <p>
                    ESPN official scoring · fetched{" "}
                    {actuals.official.fetched_at ?? "time unavailable"}
                  </p>
                  <p>
                    NBA-derived{" "}
                    {actuals.nba_derived.complete ? "complete" : "partial / unavailable"}
                    {actuals.nba_derived.provisional ? " · provisional" : ""} ·{" "}
                    {unknownCoverage
                      ? `${actuals.nba_derived.covered_player_games ?? "Unknown"} covered · eligible-game total unknown`
                      : `${actuals.nba_derived.covered_player_games} / ${actuals.nba_derived.expected_player_games} eligible player-games`}{" "}
                    · evaluated {actuals.nba_derived.fetched_at ?? "time unavailable"}
                  </p>
                  {actuals.nba_derived.gaps.length > 0 && (
                    <details className="source-gap-details">
                      <summary>
                        Reconstruction gaps ({actuals.nba_derived.gaps.length}) ·{" "}
                        {actuals.forecast_complete
                          ? "official scoring basis available"
                          : "scoring basis incomplete"}
                      </summary>
                      <ul>
                        {groups.map(({ key, label, records }) => (
                          <li key={key}>
                            {records.length > 1 ? (
                              <>
                                <b>{label}</b> · {records.length} distinct player/day records
                                <details>
                                  <summary>Affected days and players</summary>
                                  <ul>
                                    {records.map((record) => (
                                      <li key={record}>{record}</li>
                                    ))}
                                  </ul>
                                </details>
                              </>
                            ) : (
                              records[0]
                            )}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                  {actuals.sources?.length ? (
                    <ul
                      className="provider-freshness"
                      aria-label={`${team.name} NBA provider freshness`}
                    >
                      {actuals.sources.map((source, index) => (
                        <li key={`${source.source}:${source.game_id ?? index}`}>
                          {source.source === "nba_live_boxscore"
                            ? "NBA live box score"
                            : "NBA player game logs"}
                          {source.game_id ? ` · game ${source.game_id}` : ""} · {source.status} ·
                          provider response fetched {source.fetched_at ?? "unavailable"} · provider
                          update time {source.source_updated_at ?? "unverified"}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>
                      NBA provider response time unavailable; reconstruction evaluation time does
                      not establish feed freshness.
                    </p>
                  )}
                  {actuals.discrepancy && (
                    <p className="league-tied">
                      NBA minus ESPN official scoring:{" "}
                      {Object.entries(actuals.discrepancy)
                        .filter(([, delta]) => delta != null && Math.abs(delta) > 1e-9)
                        .map(
                          ([key, delta]) => `${key.toUpperCase()} ${delta! > 0 ? "+" : ""}${delta}`,
                        )
                        .join(" · ") || "No primitive difference"}
                      . Provider corrections can change this comparison.
                    </p>
                  )}
                  {hasTotals ? (
                    <details className="source-total-comparison">
                      <summary>Compare official and NBA-derived totals</summary>
                      <div className="league-table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Category</th>
                              <th>ESPN official</th>
                              <th>NBA-derived</th>
                              <th>Forecast banked</th>
                            </tr>
                          </thead>
                          <tbody>
                            {LEAGUE_CATEGORIES.map(({ key, label }) => (
                              <tr key={key}>
                                <th scope="row">{label}</th>
                                <td>
                                  {formatCategory(categoryValue(actuals.official.totals, key), key)}
                                </td>
                                <td>
                                  {formatCategory(
                                    categoryValue(actuals.nba_derived.totals, key),
                                    key,
                                  )}
                                </td>
                                <td>
                                  {formatCategory(categoryValue(actuals.forecast_totals, key), key)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  ) : (
                    <p>
                      Category totals unavailable from both sources; refresh league data to retry.
                    </p>
                  )}
                </>
              ) : (
                <p className="league-tied">
                  ESPN official totals are displayed. NBA reconstruction and historical
                  scoring-lineup coverage are unverified; source freshness is unavailable.
                </p>
              )}
            </article>
          );
        })}
      <small>
        Live and postgame totals can change with corrections. Started games are banked only;
        remaining live-game production is not projected. NBA endpoint availability and freshness are
        not guaranteed.
      </small>
    </section>
  );
}
