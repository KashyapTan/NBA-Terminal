import { getJson } from "./api";

export type AnalyticsTool = "predictor" | "consistency" | "defense" | "slate" | "picks" | "catalog";
export type ToolRow = Record<string, string | number | boolean | null>;
export interface ToolMeta {
  today: string;
  season: string;
  teams: { id: number; abbreviation: string; full_name: string }[];
  players: { id: number; full_name: string }[];
}
export interface EndpointMetadata {
  name: string;
  category: string;
  parameters: Record<string, string>;
  datasets: Record<string, string[]>;
}
export interface ToolResult {
  state: "ready" | "partial" | "error" | "empty";
  errors: string[];
  fetched_at: string;
  resources: Record<string, { fetched_at: string; state: string }>;
  rows?: ToolRow[];
  projection?: number | null;
  baseline?: number;
  season_avg?: number;
  last_5?: number;
  last_10?: number;
  valid_games?: number;
  avg_minutes?: number | null;
  minute_factor?: number;
  minutes_adjustment?: number;
  defense_adjustment?: number | null;
  pace_adjustment?: number | null;
  rest_adjustment?: number | null;
  home_adjustment?: number | null;
  minutes_estimated?: boolean;
  last_5_fallback?: boolean;
  last_10_fallback?: boolean;
  context?: Record<string, number | boolean | null>;
  context_sources?: Record<string, string>;
  missing_context?: string[];
  league_means?: Record<string, number | null>;
  league_counts?: Record<string, number>;
  roster_players?: number;
  ranked_players?: number;
  excluded?: Record<string, number>;
  qualified_players?: number;
  evaluated_players?: number;
  missing_players?: number;
  insufficient_players?: number;
  games?: {
    game_id: string;
    home_team: { abbreviation: string };
    away_team: { abbreviation: string };
    status: string;
  }[];
  files?: { filename: string; preview: string }[];
  filename?: string;
  content?: string;
  endpoints?: EndpointMetadata[];
  version?: string;
}
export const getToolsMeta = () => getJson<ToolMeta>("/api/tools/meta");
export const getAnalyticsTool = (tool: AnalyticsTool, params: Record<string, string>) =>
  getJson<ToolResult>(`/api/tools/${tool}?${new URLSearchParams(params)}`);
