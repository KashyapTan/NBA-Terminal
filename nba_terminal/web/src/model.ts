export type Team = {
  id: number;
  abbreviation: string;
  name: string;
  nickname: string;
};

export type Game = {
  game_id: string;
  date: string;
  start_time?: string;
  status: string;
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
  players: PlayerLine[];
  teams: TeamLine[];
};

export type Shot = {
  x: number;
  y: number;
  made: boolean;
  description: string;
  period: number | null;
  distance: number | null;
};

export type PlayerAnalysis = {
  game_id: string;
  player: PlayerLine;
  stats: PlayerLine;
  shots: Shot[];
  shot_chart_state: "available" | "unavailable" | "error";
};
