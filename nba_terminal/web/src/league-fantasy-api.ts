import type {
  ConnectLeague,
  LeagueSnapshot,
  LeagueStatus,
  PlannerPreferences,
  WaiverPlan,
} from "./league-fantasy-model";
const BASE = "/api/fantasy/espn";
export class FantasyApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(
      status === 401 || status === 403
        ? "Reconnect to ESPN to verify league access."
        : "League data is temporarily unavailable. Retry shortly.",
    );
  }
  get reconnectNeeded() {
    return (
      this.status === 401 ||
      (this.status === 403 &&
        !["team_not_owned", "origin_denied", "local_only", "request_header_required"].includes(
          this.code,
        ))
    );
  }
  get retryable() {
    return [408, 429, 502, 503, 504].includes(this.status) || this.status >= 500;
  }
}
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const timeout = AbortSignal.timeout(
    path === "/plan" ? 180000 : path.startsWith("/snapshot") ? 120000 : 15000,
  );
  const response = await fetch(`${BASE}${path}`, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: {
      "X-Fantasy-Request": "1",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  // Never surface upstream bodies or credentials in errors, including malformed proxy responses.
  if (!response.ok) {
    // Read only the machine code. Never expose provider messages/bodies.
    const payload = await Promise.resolve()
      .then(() => response.json())
      .catch(() => null);
    const code = payload?.detail?.code;
    throw new FantasyApiError(
      response.status,
      typeof code === "string" && /^[a-z_]{1,64}$/.test(code) ? code : "request_failed",
    );
  }
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

export const requestWaiverPlan = (preferences: PlannerPreferences, signal?: AbortSignal) =>
  request<WaiverPlan>("/plan", "POST", preferences, signal);

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
