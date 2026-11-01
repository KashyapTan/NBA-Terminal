import type { PlayerAnalysis } from "./model";

export interface PlayerSearchResult {
  player_id: number;
  name: string;
  active: boolean;
}
export interface PlayerProfile {
  player_id: number;
  player_name: string;
  season: string;
  phase: string;
  history: PlayerAnalysis["history"];
  advanced: Record<string, number | string | null>;
  advanced_state: "available" | "unavailable" | "error";
  advanced_note: string;
  advanced_source: string;
  shooting: Record<string, { value: number | null; games: number }>;
}
async function get<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok)
    throw new Error(`Player data request failed (${response.status}). Retry shortly.`);
  return response.json();
}
export const searchPlayers = (query: string, signal?: AbortSignal) =>
  get<{ players: PlayerSearchResult[] }>(
    "/api/players?" + new URLSearchParams({ q: query }),
    signal,
  );
export const getPlayerProfile = (id: number, season: string, phase: string, signal?: AbortSignal) =>
  get<PlayerProfile>(`/api/players/${id}?` + new URLSearchParams({ season, phase }), signal);

export interface GameAnalysisExtras {
  advanced_stats_source?: string;
  derived_game_shooting?: Record<string, { value: number | null; games: number }>;
}

export interface ProfileMeasureData {
  measure: string;
  row: Record<string, number | string | null>;
  state: "available" | "unavailable" | "error";
  note: string;
  source: string;
  season: string;
  phase: string;
}
export interface ShootingTables {
  state: "available" | "unavailable" | "error";
  note: string;
  source?: string;
  tables: Record<
    string,
    {
      state: "available" | "unavailable" | "error";
      note: string;
      rows: Array<Record<string, string | number | null>>;
    }
  >;
}
export const getPlayerMeasure = (
  id: number,
  measure: string,
  season: string,
  phase: string,
  signal?: AbortSignal,
) =>
  get<ProfileMeasureData>(
    `/api/players/${id}/measures/${measure}?` + new URLSearchParams({ season, phase }),
    signal,
  );
export const getPlayerShooting = (
  id: number,
  season: string,
  phase: string,
  signal?: AbortSignal,
) =>
  get<ShootingTables>(
    `/api/players/${id}/shooting?` + new URLSearchParams({ season, phase }),
    signal,
  );
export const getPlayerHistory = (id: number, season: string, phase: string, signal?: AbortSignal) =>
  get<
    Pick<PlayerProfile, "player_id" | "player_name" | "season" | "phase" | "history" | "shooting">
  >(`/api/players/${id}/history?` + new URLSearchParams({ season, phase }), signal);
