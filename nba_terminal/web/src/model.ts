export type Team = {
  id: number;
  abbreviation: string;
  name: string;
  nickname: string;
  logo_url?: string | null;
};

export type Game = {
  game_id: string;
  date: string;
  start_time?: string;
  status: string;
  status_id?: number;
  phase: string;
  home_team: Team;
  away_team: Team;
  home_score: number | null;
  away_score: number | null;
};

export type Meta = {
  current_season: string;
  seasons: string[];
  supported_from: string;
};

export type FantasyPlayer = {
  player_id: number;
  player_name: string;
  team_id: number | null;
  team_abbreviation: string | null;
  team_name: string | null;
  games: number | null;
  minutes_total: number | null;
  points: number | null;
  rebounds: number | null;
  assists: number | null;
  steals: number | null;
  blocks: number | null;
  turnovers: number | null;
  threes_made: number | null;
  three_attempts: number | null;
  field_goals_made: number | null;
  field_goal_attempts: number | null;
  free_throws_made: number | null;
  free_throw_attempts: number | null;
};

export type FantasySeason = {
  season: string;
  supported: boolean;
  phase: "Regular Season";
  players: FantasyPlayer[];
};

export type GamesResponse = {
  season: string;
  supported: boolean;
  games: Game[];
  phases: string[];
};

export type UpcomingResponse = {
  games: Game[];
  days: string[];
};

export type PlayerLine = {
  player_id: number;
  player_name: string;
  team_id: number;
  team: Team | null;
  starter?: number | null;
  min?: string | number | null;
  pts?: number | null;
  reb?: number | null;
  ast?: number | null;
  stl?: number | null;
  blk?: number | null;
  tov?: number | null;
  fgm?: number | null;
  fga?: number | null;
  fg3m?: number | null;
  fg3a?: number | null;
  ftm?: number | null;
  fta?: number | null;
  oreb?: number | null;
  dreb?: number | null;
  pf?: number | null;
  plus_minus?: number | null;
  [key: string]: unknown;
};

export type TeamLine = {
  team: Team | null;
  pts?: number | null;
};

export type BoxScore = {
  game_id: string;
  away_team?: Team | null;
  home_team?: Team | null;
  players: PlayerLine[];
  teams: TeamLine[];
};

export type Shot = {
  x: number;
  y: number;
  made: boolean;
  description: string;
  event_type?: string | null;
  shot_type?: string | null;
  period: number | null;
  distance: number | null;
  minutes_remaining?: number | null;
  seconds_remaining?: number | null;
  zone?: string | null;
};

export type PlayerGameLogRow = {
  game_id?: string | null;
  game_date?: string | null;
  matchup?: string | null;
  wl?: string | null;
  min?: number | null;
  pts?: number | null;
  reb?: number | null;
  ast?: number | null;
  stl?: number | null;
  blk?: number | null;
  tov?: number | null;
  fgm?: number | null;
  fga?: number | null;
  fg_pct?: number | null;
  fg3m?: number | null;
  fg3a?: number | null;
  fg3_pct?: number | null;
  ftm?: number | null;
  fta?: number | null;
  ft_pct?: number | null;
  plus_minus?: number | null;
  pra?: number | null;
  pr?: number | null;
  pa?: number | null;
  ra?: number | null;
  stocks?: number | null;
  efg_pct?: number | null;
  ts_pct?: number | null;
  fg3a_rate?: number | null;
  fta_rate?: number | null;
  pts_per_fga?: number | null;
};

export type PlayerHistory = {
  state: "available" | "unavailable" | "error";
  note: string;
  season: string;
  phase: string;
  opponent: string | null;
  games_played: number;
  opponent_games_played: number;
  summary: Record<
    string,
    {
      label: string;
      mean: number;
      std: number;
      consistency_cv: number;
      games: number;
      last_5: number | null;
      last_5_games: number;
      last_10: number | null;
      last_10_games: number;
      last_20: number | null;
      last_20_games: number;
    }
  >;
  games: PlayerGameLogRow[];
  opponent_games: PlayerGameLogRow[];
};

export type PlayerGameContext = {
  game_id: string;
  team: Team | null;
  opponent: Team | null;
  team_score?: number | null;
  opponent_score?: number | null;
  season: string;
  phase: string;
  game_date?: string | null;
  matchup?: string | null;
  result?: string | null;
  opponent_abbreviation?: string;
};

export type PlayerAnalysis = {
  game_id: string;
  player: PlayerLine;
  stats: PlayerLine;
  shots: Shot[];
  shot_chart_state: "available" | "unavailable" | "error";
  advanced_stats: Record<string, number | null>;
  advanced_stats_state: "available" | "unavailable" | "error";
  advanced_stats_note: string;
  history: PlayerHistory;
  history_state: "available" | "unavailable" | "error";
  game_context: PlayerGameContext;
};
