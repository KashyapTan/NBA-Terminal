import type {
  ConnectLeague,
  LeagueSnapshot,
  LeagueStatus,
  PlannerPreferences,
  WaiverPlan,
} from "./league-fantasy-model";
const BASE = "/api/fantasy/espn";
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    signal,
    headers: {
      "X-Fantasy-Request": "1",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  // Never surface upstream bodies or credentials in errors, including malformed proxy responses.
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? "Connection expired or private access was rejected. Reconnect to ESPN."
        : response.status === 403
          ? "League access denied. This connection requires a local, same-origin deployment and valid team ownership."
          : response.status === 429
            ? "ESPN is rate limiting requests. Try again shortly."
            : "League request failed. Check connection details and retry.",
    );
  return response.json() as Promise<T>;
}
export const leagueFantasyApi = {
  status: (signal?: AbortSignal) => request<LeagueStatus>("/status", "GET", undefined, signal),
  connect: (body: ConnectLeague) => request<LeagueStatus>("/connect", "POST", body),
  selectTeam: (teamId: number) => request<LeagueStatus>("/team", "PUT", { team_id: teamId }),
  disconnect: () => request<LeagueStatus>("/connection", "DELETE"),
  snapshot: (options: { refresh?: boolean; compareTeamId?: number; signal?: AbortSignal } = {}) => {
    const query = new URLSearchParams({ refresh: String(options.refresh ?? false) });
    if (options.compareTeamId !== undefined)
      query.set("compare_team_id", String(options.compareTeamId));
    return request<LeagueSnapshot>(`/snapshot?${query}`, "GET", undefined, options.signal);
  },
};
export type LeagueFantasyApi = typeof leagueFantasyApi;

export const requestWaiverPlan = (preferences: PlannerPreferences) =>
  request<WaiverPlan>("/plan", "POST", preferences);

export interface BrowserBridgeStatus {
  enabled: boolean;
  league_id?: number;
  season_id?: number;
  team_id?: number | null;
  state?:
    | "waiting_extension"
    | "no_espn_session"
    | "connected"
    | "account_changed"
    | "permission_denied"
    | "error";
}
export const browserBridgeApi = {
  pair: (input: Pick<ConnectLeague, "league_id" | "season_id" | "team_id">) =>
    request<BrowserBridgeStatus>("/bridge/pair", "POST", input),
  status: () => request<BrowserBridgeStatus>("/bridge/status"),
  cancel: () => request<LeagueStatus>("/connection", "DELETE"),
};
