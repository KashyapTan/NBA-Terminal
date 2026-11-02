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

/** Bind the current user statement to the first fresh, verified selected matchup.
 * Its original confirmation/expiry never changes on deployment, reload or refresh.
 * Observed acquisitions or changed bound evidence permanently consume this seed.
 */
export function declaredUsage(snapshot: LeagueSnapshot): PlannerPreferences["usage_declaration"] {
  const team = snapshot.teams.find((team) => team.id === snapshot.selected_team_id);
  const config = currentDeclaration;
  const now = Date.now();
  const teamName = (name: string) =>
    name.trim().replace(/[’‘]/g, "'").replace(/\s+/g, " ").toLowerCase();
  const key = `nba-terminal:usage-declaration:${config.id}`;
  try {
    const saved = localStorage.getItem(key);
    const binding = saved === null ? null : JSON.parse(saved);
    if (binding?.invalidated) return undefined;
    const roster = team?.roster.map((p) => p.id).sort() ?? [];
    const authoritativePositive =
      team &&
      team.weekly_usage_complete !== false &&
      Number.isInteger(team.weekly_used_adds) &&
      team.weekly_used_adds! > config.used;
    const changed =
      binding &&
      (!team ||
        binding.league_id !== snapshot.league.id ||
        binding.season_id !== snapshot.league.season_id ||
        binding.team_id !== snapshot.selected_team_id ||
        binding.matchup_period_id !== snapshot.period.matchup_period_id ||
        snapshot.period.start_date !== config.matchup_start_date ||
        JSON.stringify(binding.roster_ids) !== JSON.stringify(roster) ||
        binding.season_acquisitions !== (team.season_acquisitions ?? null));
    // Reconcile the already-bound stable identity before display/bootstrap
    // eligibility can return. A rename cannot hide a known add, nor can a
    // context switch restore a consumed declaration when old metadata returns.
    if (binding && (authoritativePositive || changed)) {
      localStorage.setItem(key, JSON.stringify({ invalidated: true }));
      return undefined;
    }
    if (
      !team ||
      snapshot.league.id !== config.league_id ||
      snapshot.league.season_id !== config.season_id ||
      teamName(team.name) !== teamName(config.team_name) ||
      snapshot.teams.filter((t) => teamName(t.name) === teamName(config.team_name)).length !== 1 ||
      snapshot.period.start_date !== config.matchup_start_date ||
      snapshot.period.calendar_verified !== true ||
      snapshot.period.context_verified === false ||
      now < Date.parse(config.confirmed_at) ||
      now >= Date.parse(config.expires_at)
    )
      return undefined;
    if (authoritativePositive) {
      localStorage.setItem(key, JSON.stringify({ invalidated: true }));
      return undefined;
    }
    if (binding) return binding;
    const fetchedAt = Date.parse(snapshot.fetched_at);
    // The statement is current evidence within a fixed lease, not an obsolete
    // snapshot token. Bind a fresh post-deploy snapshot, never a stale/future one.
    if (
      !Number.isFinite(fetchedAt) ||
      fetchedAt < Date.parse(config.confirmed_at) ||
      fetchedAt > now ||
      now - fetchedAt > 120000
    )
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
      roster_ids: roster,
      season_acquisitions: team.season_acquisitions ?? null,
      source: config.source,
    };
    localStorage.setItem(key, JSON.stringify(declaration));
    return declaration;
  } catch {
    // Without durable binding/tombstones, reload must not resurrect a consumed zero.
    return undefined;
  }
}
