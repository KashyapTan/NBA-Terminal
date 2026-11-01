const api = globalThis.browser ?? globalThis.chrome;
const origins = ["https://*.espn.com/*"];
const status = document.getElementById("status");
let active;
async function current() {
  const [tab] = await api.tabs.query({active: true, currentWindow: true});
  const u = new URL(tab.url);
  if (!["http:", "https:"].includes(u.protocol) || !["localhost", "127.0.0.1"].includes(u.hostname)) {
    throw new Error("Open your paired NBA Terminal localhost tab first.");
  }
  return {tab, origin: u.origin};
}
function showError(error) { status.textContent = error.message === "Open your paired NBA Terminal localhost tab first." ? error.message : "Could not complete setup. Check permissions and the local app tab."; }
document.getElementById("enable").onclick = async () => {
  // Permission request is invoked directly in the click handler (Firefox user gesture).
  const permission = api.permissions.request({permissions: ["cookies"], origins});
  try {
    if (!await permission) { status.textContent = "Permission denied. Manual cookie entry remains available."; return; }
    active = await current();
    const result = await api.runtime.sendMessage({type: "enable", tabId: active.tab.id});
    if (result.state !== "enabled") throw new Error("enable_failed");
    await api.tabs.sendMessage(active.tab.id, {type: "cookie_changed"});
    status.textContent = `Enabled for ${active.origin}, store ${result.storeId}. Existing ESPN login is checked now. If account changed, disconnect and pair again in NBA Terminal.`;
  } catch (error) { showError(error); }
};
document.getElementById("forget").onclick = async () => {
  try {
    active = await current();
    const result = await api.runtime.sendMessage({type: "forget", tabId: active.tab.id});
    if (result.state !== "forgotten") throw new Error("forget_failed");
    // Send only a command to isolated content script, never to the page.
    await api.tabs.sendMessage(active.tab.id, {type: "forget"});
    status.textContent = "Consent forgotten for this local origin. Other origins are unchanged.";
  } catch (error) { showError(error); }
};
document.getElementById("login").onclick = async () => {
  try {
    active = await current();
    const options = {url: "https://www.espn.com/login/"};
    if (active.tab.cookieStoreId) options.cookieStoreId = active.tab.cookieStoreId;
    await api.tabs.create(options);
  } catch (error) { showError(error); }
};
