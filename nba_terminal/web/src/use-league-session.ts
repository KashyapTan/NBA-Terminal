import { useCallback, useEffect, useRef, useState } from "react";
import { leagueFantasyApi, type LeagueFantasyApi } from "./league-fantasy-api";
import { reconnectNeeded, snapshotIdentity, type FantasyLifecycle } from "./fantasy-lifecycle";
import type { ConnectLeague, LeagueSnapshot, LeagueStatus } from "./league-fantasy-model";

function context(status: LeagueStatus) {
  return JSON.stringify([
    status.connected,
    status.league_id,
    status.season_id,
    status.team_id,
    status.context_id,
  ]);
}
export function useLeagueFantasy(api: LeagueFantasyApi = leagueFantasyApi) {
  const [status, setStatus] = useState<LeagueStatus>({ connected: false });
  const [snapshot, setSnapshot] = useState<LeagueSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const currentStatus = useRef(status);
  const generation = useRef(0);
  const snapshotFlight = useRef<Promise<void> | null>(null);
  const statusFlight = useRef<Promise<void> | null>(null);
  const controller = useRef<AbortController | null>(null);
  const failures = useRef(0);
  const nextAttempt = useRef(0);
  const mutations = useRef<Promise<void>>(Promise.resolve());
  const mutating = useRef(false);
  const sourceFailed = useRef(false);
  const lastSnapshotAt = useRef(0);
  const invalidate = useCallback(() => {
    generation.current++;
    controller.current?.abort();
    snapshotFlight.current = null;
    statusFlight.current = null;
    setSnapshot(null);
    sourceFailed.current = false;
  }, []);
  const acceptStatus = useCallback(
    (next: LeagueStatus) => {
      if (context(next) !== context(currentStatus.current)) invalidate();
      currentStatus.current = next;
      if (!next.connected || !next.team_id) setLoading(false);
      setStatus((previous) =>
        JSON.stringify(previous) === JSON.stringify(next) ? previous : next,
      );
      if (next.refresh_failed) {
        sourceFailed.current = true;
        setError("ESPN refresh unavailable. Previous data is read-only; retry refresh.");
      } else if (!sourceFailed.current) setError(null);
    },
    [invalidate],
  );
  const failed = useCallback(
    (failure: unknown) => {
      if (reconnectNeeded(failure)) {
        invalidate();
        currentStatus.current = { connected: false };
        setStatus(currentStatus.current);
        setError("Reconnect to ESPN to verify access.");
      } else setError("League refresh unavailable. Previous data is read-only; retry refresh.");
      failures.current++;
      nextAttempt.current =
        Date.now() + Math.min(60000, 2000 * 2 ** Math.min(failures.current - 1, 5));
    },
    [invalidate],
  );
  const fetchSnapshot = useCallback(
    (refresh = false): Promise<void> => {
      if (mutating.current) return Promise.resolve();
      if (snapshotFlight.current) return snapshotFlight.current;
      const stamp = generation.current;
      const abort = new AbortController();
      controller.current = abort;
      setLoading(true);
      const task = (async () => {
        try {
          const next = await api.snapshot({ refresh, signal: abort.signal });
          if (stamp !== generation.current) return;
          setSnapshot(next);
          sourceFailed.current = false;
          lastSnapshotAt.current = Date.now();
          setError(null);
          failures.current = 0;
          nextAttempt.current = 0;
        } catch (failure) {
          if (stamp === generation.current) {
            sourceFailed.current = true;
            failed(failure);
          }
        } finally {
          if (stamp === generation.current) setLoading(false);
        }
      })();
      snapshotFlight.current = task;
      void task.finally(() => {
        if (snapshotFlight.current === task) snapshotFlight.current = null;
      });
      return task;
    },
    [api, failed],
  );
  const refreshStatus = useCallback((): Promise<void> => {
    if (mutating.current) return Promise.resolve();
    if (statusFlight.current) return statusFlight.current;
    const stamp = generation.current;
    const task = (async () => {
      try {
        const next = await api.status();
        if (stamp === generation.current) acceptStatus(next);
      } catch (failure) {
        if (stamp === generation.current) failed(failure);
      } finally {
        if (stamp === generation.current && !snapshotFlight.current) setLoading(false);
      }
    })();
    statusFlight.current = task;
    void task.finally(() => {
      if (statusFlight.current === task) statusFlight.current = null;
    });
    return task;
  }, [api, acceptStatus, failed]);
  useEffect(() => {
    void refreshStatus();
    return () => {
      generation.current++;
      controller.current?.abort();
      snapshotFlight.current = null;
      statusFlight.current = null;
    };
  }, [refreshStatus]);
  const statusContext = context(status);
  useEffect(() => {
    if (currentStatus.current.connected && currentStatus.current.team_id) void fetchSnapshot();
  }, [statusContext, fetchSnapshot]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let checking = false;
    let snapshotQueued = false;
    async function poll(snapshotDue: boolean) {
      if (
        !active ||
        document.visibilityState === "hidden" ||
        (snapshotDue && Date.now() < nextAttempt.current)
      )
        return;
      if (checking) {
        snapshotQueued ||= snapshotDue;
        return;
      }
      checking = true;
      try {
        await refreshStatus();
        if (
          active &&
          currentStatus.current.connected &&
          currentStatus.current.team_id &&
          (snapshotDue ||
            (Date.now() >= nextAttempt.current &&
              (failures.current > 0 || Date.now() - lastSnapshotAt.current >= 60000)))
        )
          await fetchSnapshot(true);
      } finally {
        checking = false;
        if (active && snapshotQueued) {
          snapshotQueued = false;
          void poll(true);
        }
      }
    }
    // Self-scheduled: slow provider calls cannot overlap the next interval.
    async function tick() {
      await poll(true);
      if (active) timer = setTimeout(() => void tick(), 60000);
    }
    timer = setTimeout(() => void tick(), 60000);
    const changed = () => void poll(false);
    window.addEventListener("nba-espn-bridge", changed);
    window.addEventListener("focus", changed);
    document.addEventListener("visibilitychange", changed);
    return () => {
      active = false;
      clearTimeout(timer);
      window.removeEventListener("nba-espn-bridge", changed);
      window.removeEventListener("focus", changed);
      document.removeEventListener("visibilitychange", changed);
    };
  }, [refreshStatus, fetchSnapshot]);
  const mutate = (action: () => Promise<LeagueStatus>) => {
    invalidate();
    mutating.current = true;
    const stamp = generation.current;
    setLoading(true);
    setError(null);
    // Serialize writes, skip superseded queued selections. A slower old team
    // mutation must never become the server's final selection after a newer one.
    const task = mutations.current.then(async () => {
      if (stamp !== generation.current) return;
      try {
        const next = await action();
        if (stamp === generation.current) {
          mutating.current = false;
          acceptStatus(next);
          setLoading(false);
        }
      } catch (failure) {
        if (stamp === generation.current) {
          mutating.current = false;
          failed(failure);
          setLoading(false);
        }
      }
    });
    mutations.current = task;
    return task;
  };
  const lifecycle: FantasyLifecycle = {
    state: !status.connected
      ? "reconnect-needed"
      : error
        ? "stale"
        : loading || !snapshot
          ? "refreshing"
          : "connected",
    resultIdentity: snapshot ? snapshotIdentity(snapshot) : null,
    readOnly: !status.connected || !snapshot || loading || !!error,
    action: !status.connected
      ? "Connect ESPN"
      : error
        ? "Retry refresh"
        : loading || !snapshot
          ? "Updating league"
          : "Up to date",
  };
  return {
    status,
    snapshot,
    loading,
    error,
    lifecycle,
    connect: (input: ConnectLeague) => mutate(() => api.connect(input)),
    selectTeam: (id: number) => mutate(() => api.selectTeam(id)),
    disconnect: () => mutate(() => api.disconnect()),
    refresh: () => fetchSnapshot(true),
    refreshStatus,
  };
}
