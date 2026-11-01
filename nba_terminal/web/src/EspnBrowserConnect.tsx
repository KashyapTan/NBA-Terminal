import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { browserBridgeApi, type BrowserBridgeStatus } from "./league-fantasy-api";
import { DEFAULT_ESPN_LEAGUE_ID, DEFAULT_ESPN_SEASON_ID } from "./league-fantasy-model";

const setup = "/api/fantasy/espn/bridge/setup";
const messages: Record<NonNullable<BrowserBridgeStatus["state"]>, string> = {
  waiting_extension:
    "Waiting for the extension. Open its popup on this tab and choose Allow ESPN session.",
  no_espn_session:
    "Waiting for ESPN sign-in. Complete sign-in and any verification in the ESPN tab.",
  connected: "Browser session connected. Loading your league…",
  account_changed: "Your ESPN account changed. Re-enable the extension to approve this account.",
  permission_denied:
    "ESPN permission is required. Open the extension and choose Allow ESPN session to retry.",
  error: "The browser connection could not complete. Retry or use the manual fallback.",
};

export function EspnBrowserConnect({ onConnected }: { onConnected?: () => Promise<void> }) {
  const [bridge, setBridge] = useState<BrowserBridgeStatus>({ enabled: false });
  const [league, setLeague] = useState<string>();
  const [season, setSeason] = useState<string>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const readStatus = useCallback(async () => {
    const current = generation.current;
    try {
      const next = await browserBridgeApi.status();
      if (current !== generation.current) return;
      setBridge(next);
      if (next.enabled && next.state === "connected") await onConnected?.();
    } catch {
      /* Setup may be unavailable until the local server is updated. Retry remains explicit. */
    }
  }, [onConnected]);
  useEffect(() => {
    void readStatus();
    const timer = window.setInterval(() => void readStatus(), 2000);
    const changed = () => void readStatus();
    window.addEventListener("nba-espn-bridge", changed);
    return () => {
      generation.current++;
      window.clearInterval(timer);
      window.removeEventListener("nba-espn-bridge", changed);
    };
  }, [readStatus]);
  async function pair(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const current = ++generation.current;
    setError(null);
    setBusy(true);
    try {
      const next = await browserBridgeApi.pair({
        league_id: Number(fields.get("league")),
        season_id: Number(fields.get("season")),
      });
      if (current === generation.current) setBridge(next);
    } catch {
      if (current === generation.current)
        setError("Could not pair this local tab. Check the server and retry.");
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }
  async function cancel() {
    generation.current++;
    setBusy(true);
    try {
      await browserBridgeApi.cancel();
      setBridge({ enabled: false });
    } catch {
      setError("Could not cancel the connection. Retry.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="espn-browser-connect">
      <p>
        Use your ESPN sign-in from this browser. Enable the local extension once, then an existing
        sign-in connects automatically. Sign in and complete verification directly at ESPN.
      </p>
      <details className="espn-setup">
        <summary>One-time browser setup</summary>
        <ol>
          <li>
            Download the <a href={`${setup}/firefox.zip`}>Firefox extension</a> or{" "}
            <a href={`${setup}/chromium.zip`}>Chromium extension</a> and extract it.
          </li>
          <li>
            Follow the{" "}
            <a href={`${setup}/instructions.md`} target="_blank" rel="noreferrer">
              installation instructions
            </a>
            . Firefox temporary loading lasts until the browser restarts; permanent Firefox
            installation requires Mozilla signing.
          </li>
          <li>
            Connect below. Open the extension on this NBA Terminal tab, review consent and choose
            Allow ESPN session to grant ESPN cookie access. Use the browser profile/container where
            you sign in to ESPN.
          </li>
        </ol>
        <p>
          Credentials stay local. The extension reads only the ESPN session cookies after your
          permission.
        </p>
      </details>
      <form onSubmit={(event) => void pair(event)} autoComplete="off">
        <div className="league-fields">
          <label>
            League ID
            <input
              name="league"
              type="number"
              min="1"
              step="1"
              required
              value={league ?? bridge.league_id ?? DEFAULT_ESPN_LEAGUE_ID}
              onChange={(event) => setLeague(event.target.value)}
            />
          </label>
          <label>
            Season ending year
            <input
              name="season"
              type="number"
              min="2019"
              max="2100"
              step="1"
              required
              value={season ?? bridge.season_id ?? DEFAULT_ESPN_SEASON_ID}
              onChange={(event) => setSeason(event.target.value)}
            />
          </label>
        </div>
        <p>
          Connect authorizes this local tab to reuse your ESPN session through the extension. You
          approve browser access in the extension popup.
        </p>
        <button type="submit" disabled={busy}>
          {bridge.enabled ? "Retry ESPN connection" : "Connect ESPN"}
        </button>
        {bridge.enabled && (
          <button type="button" disabled={busy} onClick={() => void cancel()}>
            Cancel connection
          </button>
        )}
        <a
          className="espn-sign-in"
          href="https://www.espn.com/login/"
          target="_blank"
          rel="noreferrer"
        >
          Sign in at ESPN ↗
        </a>
      </form>
      {bridge.enabled && <p role="status">{messages[bridge.state ?? "waiting_extension"]}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
