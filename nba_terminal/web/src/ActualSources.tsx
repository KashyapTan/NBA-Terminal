import {
  LEAGUE_CATEGORIES,
  categoryValue,
  formatCategory,
  type LeagueTeam,
} from "./league-fantasy-model";

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
          return (
            <article key={team.id}>
              <h4>{team.name}</h4>
              {actuals ? (
                <>
                  <p>
                    <b>Forecast actuals basis: {actuals.forecast_source}</b> ·{" "}
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
                    {actuals.nba_derived.covered_player_games ?? "?"} /{" "}
                    {actuals.nba_derived.expected_player_games ?? "?"} eligible player-games ·
                    fetched {actuals.nba_derived.fetched_at ?? "time unavailable"}
                  </p>
                  {actuals.nba_derived.gaps.length > 0 && (
                    <p className="league-tied">{actuals.nba_derived.gaps.join(" · ")}</p>
                  )}
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
                            <th>{label}</th>
                            <td>
                              {formatCategory(categoryValue(actuals.official.totals, key), key)}
                            </td>
                            <td>
                              {formatCategory(categoryValue(actuals.nba_derived.totals, key), key)}
                            </td>
                            <td>
                              {formatCategory(categoryValue(actuals.forecast_totals, key), key)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
