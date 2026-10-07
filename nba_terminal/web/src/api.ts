import type { BoxScore, GamesResponse, Meta, PlayerAnalysis, UpcomingResponse } from "./model";

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail || message;
    } catch {
      // Keep the HTTP status message when the error response has no JSON body.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export const getMeta = () => getJson<Meta>("/api/meta");
export const getUpcoming = () => getJson<UpcomingResponse>("/api/upcoming");
export const getGames = (season: string) =>
  getJson<GamesResponse>(`/api/games?season=${encodeURIComponent(season)}`);
export const getGame = (gameId: string) =>
  getJson<BoxScore>(`/api/games/${encodeURIComponent(gameId)}`);
export const getPlayerAnalysis = (
  gameId: string,
  playerId: string,
  season: string,
  phase: string,
) =>
  getJson<PlayerAnalysis>(
    `/api/games/${encodeURIComponent(gameId)}/players/${encodeURIComponent(playerId)}?season=${encodeURIComponent(season)}&phase=${encodeURIComponent(phase)}`,
  );
