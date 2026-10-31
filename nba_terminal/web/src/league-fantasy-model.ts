export const LEAGUE_CATEGORIES = [
  { key: "pts", label: "PTS" },
  { key: "reb", label: "REB" },
  { key: "ast", label: "AST" },
  { key: "stl", label: "STL" },
  { key: "blk", label: "BLK" },
  { key: "threes", label: "3PM" },
  { key: "to", label: "TO" },
  { key: "fg_pct", label: "FG%" },
  { key: "ft_pct", label: "FT%" },
] as const;
export type Category = (typeof LEAGUE_CATEGORIES)[number]["key"];
export type Stats = Partial<
  Record<Category | "fgm" | "fga" | "ftm" | "fta" | "minutes" | "games", number | null>
>;
export type CategoryState = "winning" | "tied" | "losing" | "unknown";
export interface LeaguePlayer {
  id: string;
  name: string;
  positions: string[];
  lineup_slot: string | null;
  injury_status: string | null;
  injured: boolean | null;
  locked: boolean | null;
  availability: "FREEAGENT" | "WAIVERS" | "ONTEAM" | "UNKNOWN";
  eligible: boolean;
  current_rates: Stats | null;
  current_games: number | null;
  prior_rates: Stats | null;
  prior_games: number | null;
  schedule:
    | {
        date: string;
        start_at: string;
        started: boolean;
        scoring_period_id: number;
        opponent_pro_team_id: number | null;
      }[]
    | null;
  today: boolean | null;
  remaining_games: number | null;
  undroppable?: boolean | null;
  droppable?: boolean | null;
  health_status?: "available" | "out";
  health_source?: "espn" | "assumed_available";
  current_rates_source?: string | null;
  season_rank?: number | null;
  draft_rank?: number | null;
  draft_pick?: number | null;
  draft_round?: number | null;
}
export interface LeagueTeam {
  id: number;
  name: string;
  ownership_verified: boolean;
  roster: LeaguePlayer[];
  totals: Stats | null;
  weekly_used_adds: number | null;
  remaining_adds: number | null;
}
export interface LeagueStatus {
  connected: boolean;
  league_id?: number;
  season_id?: number;
  team_id?: number;
  auth_mode?: "public" | "private";
  ownership_verified?: boolean;
  expires_at?: string;
  teams?: { id: number; name: string; selectable: boolean; ownership_verified: boolean }[];
}
export interface LeagueSnapshot {
  schema_version: 1;
  fetched_at: string;
  source: "espn_unofficial";
  league: {
    id: number;
    season_id: number;
    name: string;
    team_count: number;
    supported: boolean;
    unsupported_reason: string | null;
    lineup_slots: string[];
    acquisition_settings: {
      weekly_add_limit: number | null;
      limit_per_scoring_period: boolean | null;
      season_add_limit: number | null;
    };
  };
  period: {
    matchup_period_id: number;
    scoring_period_id: number;
    dates: string[];
    remaining_dates: string[];
    start_date?: string | null;
    end_date?: string | null;
  };
  selected_team_id: number;
  opponent_team_id: number | null;
  teams: LeagueTeam[];
  free_agents: LeaguePlayer[];
  free_agents_truncated: boolean;
  data_gaps: string[];
}
export interface ConnectLeague {
  league_id: number;
  season_id: number;
  team_id?: number;
  swid?: string;
  espn_s2?: string;
}
export interface PlannerPreferences {
  context?: { league_id: number; team_id: number; matchup_period_id: number; fetched_at: string };
  user_confirmed_eligibility?: boolean;
  candidate_ids?: string[];
  droppable_ids?: string[];
  max_stream_slots?: number;
  weekly_add_limit?: number | null;
  used_adds?: number | null;
  available_adds?: number | null;
  user_confirmed_counts?: boolean;
  protected_ids?: string[];
  uncertainty_mode?: "history" | "sensitivity";
  margin_sd?: Partial<Record<Category, number>>;
  /** Explicit, snapshot-bound corrections confirmed by the user, never ESPN assertions. */
  player_overrides?: Record<
    string,
    { schedule?: string[]; injured?: boolean; protected?: boolean }
  >;
  remaining_dates?: string[];
}
/** UI boundary for the later optimizer adapter; never compute probabilities in the browser. */
export interface CategoryStrategy {
  classification: "favored" | "swing" | "reachable" | "punt" | "unknown";
  explanation: string;
  projected_margin: number | null;
  historical_margin: number | null;
  target_priority: number | null;
}
export interface PickupRecommendation {
  add_id: string;
  drop_id: string;
  date: string;
  probability_gain: number | null;
  category_probability_gains?: Partial<Record<Category, number>>;
  gains: Partial<Record<Category, number | null>>;
  games_gain: number | null;
  minutes_gain: number | null;
  season_cost: number | null;
  net_score: number | null;
  target_categories: Category[];
  rationale: string;
}
export interface WaiverPlan {
  strategy?: Partial<Record<Category, CategoryStrategy>>;
  recommendations?: PickupRecommendation[];
  recommendation_kind?: "alternatives";
  plan?: WaiverPlan["actions"];
  uncertainty?: { source: string; calibrated: boolean };
  status: "ready" | "incomplete" | "unavailable";
  reasons: string[];
  remaining_adds: number | null;
  baseline: PlanForecast | null;
  projected: PlanForecast | null;
  actions: {
    date: string;
    add_id: string;
    drop_id: string;
    stream_slot: string | number;
    gains: Partial<Record<Category, number | null>>;
    probability_gain: number | null;
  }[];
  assumptions: string[];
  limitations: string[];
  data_gaps: string[];
  provenance?: Record<string, unknown>;
}
export interface PlanForecast {
  basis?: "recorded" | "forecast";
  totals: Stats;
  games: number | null;
  minutes: number | null;
  probability_five_wins: number | null;
}
export function categoryValue(stats: Stats | null, key: Category): number | null {
  if (!stats) return null;
  if (key === "fg_pct" || key === "ft_pct") {
    const made = stats[key === "fg_pct" ? "fgm" : "ftm"];
    const attempts = stats[key === "fg_pct" ? "fga" : "fta"];
    if (made != null && attempts != null) return attempts > 0 ? made / attempts : null;
  }
  const value = stats[key];
  return value != null && Number.isFinite(value) ? value : null;
}
export function compareCategory(
  user: number | null,
  opponent: number | null,
  key: Category,
): CategoryState {
  if (user === null || opponent === null) return "unknown";
  if (Math.abs(user - opponent) < 1e-9) return "tied";
  return (key === "to" ? user < opponent : user > opponent) ? "winning" : "losing";
}
export function formatCategory(value: number | null, key: Category) {
  return value === null
    ? "Unavailable"
    : key.endsWith("pct")
      ? `${(value * 100).toFixed(2)}%`
      : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
export function eligibleCandidates(snapshot: LeagueSnapshot) {
  const rostered = new Set(
    snapshot.teams.flatMap((team) => team.roster.map((player) => player.id)),
  );
  return snapshot.free_agents.filter(
    (player, index, rows) =>
      player.eligible &&
      player.availability === "FREEAGENT" &&
      !rostered.has(player.id) &&
      rows.findIndex((row) => row.id === player.id) === index,
  );
}
