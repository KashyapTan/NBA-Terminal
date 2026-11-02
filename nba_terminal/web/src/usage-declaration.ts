import currentDeclaration from "./current-usage-declaration.json";
import type { LeagueSnapshot, PlannerPreferences } from "./league-fantasy-model";

export function bindUsage(snapshot: LeagueSnapshot, used: number, confirmedAt: string) {
  const team = snapshot.teams.find((team) => team.id === snapshot.selected_team_id)!;
  return {
    league_id: snapshot.league.id,
    season_id: snapshot.league.season_id,
    team_id: snapshot.selected_team_id,
    matchup_period_id: snapshot.period.matchup_period_id,
    used,
    confirmed_at: confirmedAt,
    expires_at: new Date(Date.parse(confirmedAt) + 3600000).toISOString(),
    snapshot_at: snapshot.fetched_at,
    roster_ids: team.roster.map((player) => player.id).sort(),
    season_acquisitions: team.season_acquisitions ?? null,
    source: "user-confirmed current matchup usage",
  };
}

/** One authorized declaration, never a zero default for arbitrary weeks/teams.
 * Persist the first observed scope/evidence; reload/refresh cannot renew its lease.
 * Private browser access was unavailable: this reviewed bootstrap is only usable
 * against the exact snapshot the user confirmed, until its fixed expiry.
 */
export function declaredUsage(snapshot: LeagueSnapshot): PlannerPreferences["usage_declaration"] {
  const team = snapshot.teams.find((team) => team.id === snapshot.selected_team_id);
  const config = currentDeclaration;
  if (
    !team ||
    snapshot.league.id !== config.league_id ||
    snapshot.league.season_id !== config.season_id ||
    team.name !== config.team_name ||
    snapshot.period.start_date !== config.matchup_start_date ||
    Date.now() >= Date.parse(config.expires_at)
  )
    return undefined;
  const key = `nba-terminal:usage-declaration:${config.id}`;
  try {
    const saved = localStorage.getItem(key);
    if (saved !== null) return JSON.parse(saved);
    if (Date.parse(snapshot.fetched_at) !== Date.parse(config.evidence_snapshot_at))
      return undefined;
    const declaration = {
      league_id: config.league_id,
      season_id: config.season_id,
      team_id: snapshot.selected_team_id,
      matchup_period_id: snapshot.period.matchup_period_id,
      used: config.used,
      confirmed_at: config.confirmed_at,
      expires_at: config.expires_at,
      snapshot_at: snapshot.fetched_at,
      roster_ids: team.roster.map((player) => player.id).sort(),
      season_acquisitions: team.season_acquisitions ?? null,
      source: config.source,
    };
    localStorage.setItem(key, JSON.stringify(declaration));
    return declaration;
  } catch {
    // Without durable binding, do not re-seed usage on each render/reload.
    return undefined;
  }
}
