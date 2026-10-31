/* Only extension-owned UI and isolated content scripts use runtime messaging.
   No externally_connectable, page message listener, cookie writes, or ESPN fetches. */
const api = globalThis.browser ?? globalThis.chrome;
const ESPN_ORIGINS = ["https://*.espn.com/*"];
function localOrigin(value) {
  try {
    const u = new URL(value);
    return ["http:", "https:"].includes(u.protocol) &&
      ["localhost", "127.0.0.1"].includes(u.hostname) ? u.origin : null;
  } catch { return null; }
}
async function digest(value) {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))))
    .map(x => x.toString(16).padStart(2, "0")).join("");
}
async function storeFor(tab) {
  if (tab.cookieStoreId) return tab.cookieStoreId;
  const stores = await api.cookies.getAllCookieStores();
  return stores.find(s => s.tabIds.includes(tab.id))?.id;
}
async function credentials(sender) {
  const origin = localOrigin(sender.url);
  if (!sender.tab || sender.frameId !== 0 || !origin) throw new Error("invalid_sender");
  const grants = (await api.storage.local.get("grants")).grants ?? {};
  const grant = grants[origin];
  if (!grant) return {state: "extension_not_enabled"};
  const permitted = await api.permissions.contains({permissions: ["cookies"], origins: ESPN_ORIGINS});
  if (!permitted) return {state: "permission_denied"};
  const storeId = await storeFor(sender.tab);
  if (!storeId || storeId !== grant.storeId) return {state: "wrong_cookie_store"};
  // Exact names, normal first-party ESPN cookie store, no unrelated domain reads.
  const options = {url: "https://www.espn.com/", storeId};
  const [swid, s2] = await Promise.all([
    api.cookies.get({...options, name: "SWID"}), api.cookies.get({...options, name: "espn_s2"})
  ]);
  if (!swid?.value || !s2?.value) return {state: "no_espn_session"};
  const account = await digest(swid.value.toLowerCase().replace(/[{}]/g, ""));
  if (grant.account && grant.account !== account) return {state: "account_changed"};
  if (!grant.account) {
    // Re-read before saving so Forget cannot be undone by an in-flight cookie read.
    const latest = (await api.storage.local.get("grants")).grants ?? {};
    if (latest[origin]?.id !== grant.id) return {state: "extension_not_enabled"};
    latest[origin].account = account;
    await api.storage.local.set({grants: latest});
  }
  return {state: "ready", swid: swid.value, espn_s2: s2.value,
    fingerprint: await digest(swid.value + "\n" + s2.value)};
}
// Serialize consent updates and cookie reads across tabs; Forget cannot race a
// background account-hash write and resurrect a deleted consent record.
let queue = Promise.resolve();
async function handle(message, sender) {
  if (message.type === "credentials") return credentials(sender);
  if (sender.url !== api.runtime.getURL("popup.html") || !Number.isInteger(message.tabId)) {
    throw new Error("invalid_sender");
  }
  const tab = await api.tabs.get(message.tabId);
  const origin = localOrigin(tab.url);
  if (!origin) throw new Error("invalid_sender");
  const grants = (await api.storage.local.get("grants")).grants ?? {};
  if (message.type === "enable") {
    const storeId = await storeFor(tab);
    if (!storeId) throw new Error("store_missing");
    grants[origin] = {id: crypto.randomUUID(), storeId};
  } else if (message.type === "forget") delete grants[origin];
  await api.storage.local.set({grants});
  return {state: message.type === "enable" ? "enabled" : "forgotten", origin,
    storeId: grants[origin]?.storeId};
}
api.runtime.onMessage.addListener((message, sender, reply) => {
  if (!["credentials", "enable", "forget"].includes(message?.type)) return false;
  const task = queue.then(() => handle(message, sender));
  queue = task.catch(() => {});
  task.then(reply, () => reply({state: "error"}));
  return true;
});
async function notify() {
  // No tabs permission: query only declared loopback content-script hosts.
  const tabs = await api.tabs.query({url: ["http://localhost/*", "http://127.0.0.1/*",
    "https://localhost/*", "https://127.0.0.1/*"]});
  await Promise.allSettled(tabs.map(tab => api.tabs.sendMessage(tab.id, {type: "cookie_changed"})));
}
let watchingCookies = false;
function watchCookies() {
  if (watchingCookies || !api.cookies?.onChanged) return;
  try {
    api.cookies.onChanged.addListener(change => {
      if (["SWID", "espn_s2"].includes(change.cookie.name) && /(^|\.)espn\.com$/.test(change.cookie.domain.replace(/^\./, ""))) {
        void notify();
      }
    });
    watchingCookies = true;
  } catch { /* Optional cookies permission has not been granted yet. */ }
}
watchCookies();
api.permissions.onAdded.addListener(() => { watchCookies(); void notify(); });
api.permissions.onRemoved.addListener(() => { void notify(); });
