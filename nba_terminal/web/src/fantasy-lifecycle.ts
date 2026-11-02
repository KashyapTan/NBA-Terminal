import { useEffect, useRef, useState } from "react";
import currentUsageDeclaration from "./current-usage-declaration.json";
import { FantasyApiError } from "./league-fantasy-api";
import type { LeagueSnapshot, PlannerPreferences, WaiverPlan } from "./league-fantasy-model";
import { declaredUsage } from "./usage-declaration";

export interface FantasyLifecycle {
  state: "connected" | "refreshing" | "stale" | "reconnect-needed";
  resultIdentity: string | null;
  action: string;
  readOnly: boolean;
}
export function stableIdentity(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableIdentity).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.entries(value)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, part]) => `${JSON.stringify(key)}:${stableIdentity(part)}`)
      .join(",")}}`;
  return JSON.stringify(value) ?? "null";
}
const qualificationDay = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" });
function observationDay(value: unknown) {
  const parsed = typeof value === "string" ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) ? qualificationDay.format(parsed) : value;
}
export function snapshotIdentity(snapshot: LeagueSnapshot): string {
  // Observation times do not change facts. Actual dates, starts, source
  // completeness/freshness flags and immutable evidence expiry still do.
  return stableIdentity([
    observationDay(snapshot.fetched_at), // current qualification day can expire cached samples
    JSON.parse(
      JSON.stringify(snapshot, function (key, value) {
        // ENGINE sample timestamps decide same-day qualification, not intraday
        // plan identity. Preserve the NY date (and invalid/missing evidence).
        if (key === "sample_as_of" || (key === "as_of" && Object.hasOwn(this, "team_games"))) {
          return observationDay(value);
        }
        if (["fetched_at", "evaluated_at", "as_of"].includes(key) || key.endsWith("_fetched_at"))
          return undefined;
        // Both states mean current usable source facts within the provider TTL.
        // Stale/failed/missing/unknown are deliberately never collapsed.
        if (key.endsWith("status") && (value === "fresh" || value === "cached")) return "current";
        return value;
      }),
    ),
  ]);
}
export function retryable(error: unknown): boolean {
  return !(error instanceof FantasyApiError) || error.retryable;
}
export function reconnectNeeded(error: unknown): boolean {
  return error instanceof FantasyApiError && error.reconnectNeeded;
}
export function useWaiverPlan(
  snapshot: LeagueSnapshot,
  preferences: PlannerPreferences,
  onPlan:
    | ((preferences: PlannerPreferences, signal?: AbortSignal) => Promise<WaiverPlan>)
    | undefined,
  attempt: number,
  blocked: boolean,
  refreshing: boolean,
) {
  const [, tickLease] = useState(0);
  const expiresAt = preferences.usage_declaration?.expires_at ?? currentUsageDeclaration.expires_at;
  const expiry = Date.parse(expiresAt);
  const leaseExpired = Number.isFinite(expiry) && Date.now() >= expiry;
  useEffect(() => {
    if (!Number.isFinite(expiry) || Date.now() >= expiry) return;
    const timer = setTimeout(
      () => tickLease((current) => current + 1),
      Math.min(2147483647, expiry - Date.now() + 1),
    );
    return () => clearTimeout(timer);
  }, [expiry, leaseExpired]);
  const identity = stableIdentity([snapshotIdentity(snapshot), preferences, leaseExpired]);
  const latest = useRef({ snapshot, preferences, onPlan });
  latest.current = { snapshot, preferences, onPlan };
  const [result, setResult] = useState<{ plan: WaiverPlan; identity: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revoked, setRevoked] = useState(false);
  useEffect(() => {
    if (!latest.current.onPlan || !snapshot.league.supported || blocked) {
      setBusy(false);
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    setBusy(true);
    setError(null);
    setRevoked(false);
    async function run(tries: number) {
      const { snapshot: current, preferences: prefs, onPlan: fetchPlan } = latest.current;
      try {
        const plan = await fetchPlan!(
          {
            ...prefs,
            usage_declaration: prefs.usage_declaration ?? declaredUsage(current),
            context: {
              league_id: current.league.id,
              season_id: current.league.season_id,
              team_id: current.selected_team_id,
              matchup_period_id: current.period.matchup_period_id,
              fetched_at: current.fetched_at,
            },
          },
          controller.signal,
        );
        if (active) {
          setResult({ plan, identity });
          setBusy(false);
          setError(null);
        }
      } catch (failure) {
        if (!active) return;
        setError(
          reconnectNeeded(failure) ? "Reconnect to ESPN." : "Analysis unavailable. Retry shortly.",
        );
        if (reconnectNeeded(failure)) {
          setResult(null);
          setRevoked(true);
        }
        if (retryable(failure) && tries < 2)
          timer = setTimeout(() => void run(tries + 1), 2000 * 2 ** tries);
        else setBusy(false);
      }
    }
    void run(0);
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [identity, attempt, blocked, snapshot.league.supported, !!onPlan]);
  const outdated = result?.identity !== identity;
  const readOnly = blocked || refreshing || busy || !!error || outdated;
  const lifecycle: FantasyLifecycle = {
    state: revoked
      ? "reconnect-needed"
      : error || blocked
        ? "stale"
        : busy || refreshing || outdated
          ? "refreshing"
          : "connected",
    resultIdentity: result?.identity ?? null,
    readOnly,
    action: revoked
      ? "Reconnect ESPN"
      : error || blocked
        ? "Retry refresh"
        : busy || refreshing || outdated
          ? "Updating analysis"
          : "Up to date",
  };
  return { plan: result?.plan ?? null, busy, error, lifecycle };
}
