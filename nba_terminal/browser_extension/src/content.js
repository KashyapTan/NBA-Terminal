/* Isolated world only. No window/message/DOM inputs; never expose cookies to page JS. */
(() => {
  const api = globalThis.browser ?? globalThis.chrome;
  const root = "/api/fantasy/espn";
  let busy = false, lastFingerprint = null, renewedAt = 0, nextAttempt = 0;
  async function request(path, data) {
    const response = await fetch(root + path, {method: data === undefined ? "GET" : "POST",
      credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: {"Content-Type": "application/json", "X-Fantasy-Request": "1"},
      ...(data === undefined ? {} : {body: JSON.stringify(data)})});
    const result = await response.json();
    if (!response.ok) throw new Error("local_request_failed");
    return result;
  }
  function advise(state) {
    // Advisory only: UI must re-fetch authenticated backend status.
    const detail = typeof cloneInto === "function" ? cloneInto({state}, window) : {state};
    window.dispatchEvent(new CustomEvent("nba-espn-bridge", {detail}));
  }
  async function sync() {
    if (busy || Date.now() < nextAttempt) return;
    busy = true;
    try {
      const pair = await request("/bridge/status");
      if (!pair.enabled) { lastFingerprint = null; renewedAt = 0; return; }
      const result = await api.runtime.sendMessage({type: "credentials"});
      if (["extension_not_enabled", "wrong_cookie_store"].includes(result.state)) {
        advise(result.state); return;
      }
      const status = await request("/status");
      if (result.state === "ready" && result.fingerprint === lastFingerprint && status.connected &&
          Date.now() - renewedAt < 3600000) return;
      if (result.state !== "ready" && result.state === pair.state) return;
      const ticket = await request("/bridge/challenge", {});
      // League/team config comes from authenticated backend, never webpage messages.
      const data = {league_id: ticket.league_id, season_id: ticket.season_id, nonce: ticket.nonce};
      if (result.state === "ready") Object.assign(data, {swid: result.swid, espn_s2: result.espn_s2});
      else data.state = result.state;
      const updated = await request("/bridge/refresh", data);
      lastFingerprint = result.fingerprint ?? null;
      renewedAt = Date.now();
      advise(updated.state);
    } catch {
      // Static errors only, never serialize network/API exceptions containing secrets.
      nextAttempt = Date.now() + 300000;
      advise("error");
    } finally { busy = false; }
  }
  api.runtime.onMessage.addListener(message => {
    if (message?.type === "forget") {
      void fetch(root + "/connection", {method: "DELETE", credentials: "same-origin", redirect: "error",
        headers: {"X-Fantasy-Request": "1"}}).then(() => advise("disconnected"), () => advise("error"));
    }
    if (message?.type === "cookie_changed") { nextAttempt = 0; void sync(); }
  });
  setInterval(() => { void sync(); }, 60000);
  // Pairing can occur after content script startup; inexpensive local status only.
  setInterval(async () => {
    if (busy) return;
    try {
      const pair = await request("/bridge/status");
      if (!pair.enabled) { lastFingerprint = null; renewedAt = 0; return; }
      // An explicit new Pair/Retry must not wait behind an old error backoff
      // or a prior connection's one-minute poll. No page-to-extension command.
      if (pair.state === "waiting_extension") { nextAttempt = 0; lastFingerprint = null; }
      if (!lastFingerprint) void sync();
    } catch { /* Local server may be restarting. Normal sync keeps bounded backoff. */ }
  }, 2000);
  void sync();
})();
