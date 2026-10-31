import {test, expect} from "bun:test";
import vm from "node:vm";
import fs from "node:fs";
import {webcrypto} from "node:crypto";

const source = name => fs.readFileSync(new URL(`../src/${name}.js`, import.meta.url), "utf8");
const origin = "http://localhost:5173";
const sender = {url: origin + "/fantasy", frameId: 0, tab: {id: 4, cookieStoreId: "firefox-default"}};
function background() {
  const state = {grants: {[origin]: {id: "consent-1", storeId: "firefox-default"}}, permitted: true,
    cookies: {SWID: "fixture-owner-0001", espn_s2: "synthetic-cookie"}, reads: [], messages: []};
  let listener, changed, removed;
  const browser = {
    runtime: {getURL: name => "moz-extension://test/" + name, onMessage: {addListener: fn => { listener = fn; }}},
    permissions: {contains: async () => state.permitted, onAdded: {addListener: () => {}}, onRemoved: {addListener: fn => { removed = fn; }}},
    storage: {local: {get: async () => structuredClone({grants: state.grants}),
      set: async value => { state.grants = structuredClone(value.grants); }}},
    cookies: {
      get: async options => {state.reads.push(options); return state.cookies[options.name] ? {value: state.cookies[options.name]} : null;},
      getAllCookieStores: async () => [{id: "firefox-default", tabIds: [4]}],
      onChanged: {addListener: fn => {changed = fn;}},
    },
    tabs: {get: async () => ({id: 4, url: origin, cookieStoreId: "firefox-default"}), query: async () => [{id: 4}], sendMessage: async (id, msg) => {state.messages.push([id, msg]);}},
  };
  vm.runInNewContext(source("background"), {browser, URL, crypto: webcrypto, TextEncoder, Uint8Array});
  const call = (s = sender) => new Promise(resolve => listener({type: "credentials"}, s, resolve));
  const message = (m, s) => new Promise(resolve => listener(m, s, resolve));
  return {state, call, message, changed: (...args) => changed(...args), removed: () => removed()};
}
const tick = () => new Promise(resolve => setTimeout(resolve, 20));

test("existing profile login, only exact cookie reads, metadata contains no credentials", async () => {
  const {state, call} = background();
  const result = await call();
  expect(result.state).toBe("ready");
  expect(result.swid).toBe(state.cookies.SWID);
  expect(state.reads.map(x => x.name)).toEqual(["SWID", "espn_s2"]);
  expect(state.reads.every(x => x.storeId === "firefox-default" && x.url === "https://www.espn.com/")).toBe(true);
  expect(JSON.stringify(state.grants)).not.toContain(state.cookies.SWID);
  expect(JSON.stringify(state.grants)).not.toContain(state.cookies.espn_s2);
  expect(state.grants[origin].account).toMatch(/^[a-f0-9]{64}$/);
});
test("permission denied, unpaired, wrong store, missing session, account switch", async () => {
  const {state, call} = background();
  state.permitted = false;
  expect((await call()).state).toBe("permission_denied");
  expect(state.reads).toHaveLength(0);
  state.permitted = true;
  expect((await call({...sender, tab: {id: 4, cookieStoreId: "other"}})).state).toBe("wrong_cookie_store");
  expect((await call({...sender, url: "http://127.0.0.1:5173"})).state).toBe("extension_not_enabled");
  delete state.cookies.espn_s2;
  expect((await call()).state).toBe("no_espn_session");
  state.cookies.espn_s2 = "new-synthetic-cookie";
  expect((await call()).state).toBe("ready");
  state.cookies.SWID = "different-account";
  expect((await call()).state).toBe("account_changed");
  state.grants[origin] = {id: "consent-2", storeId: "firefox-default"};
  expect((await call()).state).toBe("ready");
});
test("forged sender/subframe/remote origin rejected and Chromium store detected", async () => {
  const {call} = background();
  for (const s of [{url: sender.url}, {...sender, frameId: 1}, {...sender, url: "https://evil.example/"},
    {...sender, url: "http://localhost.evil.example/"}]) expect((await call(s)).state).toBe("error");
  expect((await call({...sender, tab: {id: 4}})).state).toBe("ready");
});
test("cookie events filtered and permission revocation notifies local tabs", async () => {
  const {state, changed, removed} = background();
  changed({cookie: {name: "unrelated", domain: ".espn.com"}});
  changed({cookie: {name: "SWID", domain: "espn.com.evil.example"}});
  await tick();
  expect(state.messages).toHaveLength(0);
  changed({cookie: {name: "espn_s2", domain: ".espn.com"}});
  await tick();
  expect(state.messages[0][1]).toEqual({type: "cookie_changed"});
  removed(); await tick();
  expect(state.messages).toHaveLength(2);
});
function contentHarness({enabled = true, result = {state: "ready", swid: "synthetic-swid", espn_s2: "synthetic-s2", fingerprint: "hash"}} = {}) {
  const calls = [], events = [], timers = [];
  let listener, connected = false, currentResult = result, fakeNow = 1000;
  const browser = {runtime: {sendMessage: async () => currentResult,
    onMessage: {addListener: fn => {listener = fn;}}}};
  const fetch = async (path, options) => {
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({path, options, body});
    let response;
    if (path.endsWith("/bridge/status")) response = {enabled, state: "waiting_extension"};
    else if (path.endsWith("/bridge/challenge")) response = {nonce: "ticket", league_id: 123, season_id: 2027};
    else if (path.endsWith("/bridge/refresh")) {connected = !body.state; response = {state: connected ? "connected" : body.state};}
    else if (path.endsWith("/connection")) {enabled = false; connected = false; response = {};}
    else response = {connected};
    return {ok: true, json: async () => response};
  };
  vm.runInNewContext(source("content"), {browser, fetch, Date: {now: () => fakeNow},
    setInterval: (fn, ms) => {timers.push({fn, ms});}, window: {dispatchEvent: e => events.push(e)},
    CustomEvent: function(type, options) {this.type = type; this.detail = options.detail;}});
  return {calls, events, timers, notify: type => listener({type}), result: value => {currentResult = value;}, advance: ms => {fakeNow += ms;}};
}
test("isolated relay posts secrets only to same-origin route, no secret events; cookie changes renew", async () => {
  const h = contentHarness(); await tick();
  const posts = () => h.calls.filter(x => x.path.endsWith("/bridge/refresh"));
  expect(posts()).toHaveLength(1);
  expect(posts()[0].body).toEqual({league_id: 123, season_id: 2027, nonce: "ticket", swid: "synthetic-swid", espn_s2: "synthetic-s2"});
  expect(h.calls.every(x => x.path.startsWith("/api/fantasy/espn/") && x.options.credentials === "same-origin" && x.options.redirect === "error")).toBe(true);
  expect(JSON.stringify(h.events)).not.toContain("synthetic");
  h.notify("cookie_changed"); await tick(); expect(posts()).toHaveLength(1);
  h.result({state: "ready", swid: "synthetic-swid", espn_s2: "new", fingerprint: "changed"});
  h.notify("cookie_changed"); await tick(); expect(posts()).toHaveLength(2);
  h.advance(3600001); h.timers[0].fn(); await tick(); expect(posts()).toHaveLength(3);
  h.result({state: "no_espn_session"}); h.notify("cookie_changed"); await tick();
  expect(posts().at(-1).body.state).toBe("no_espn_session");
  h.notify("forget"); await tick();
  expect(h.calls.at(-1).options.method).toBe("DELETE");
});
test("unpaired page does not request cookies or create challenge", async () => {
  const h = contentHarness({enabled: false}); await tick();
  expect(h.calls.map(x => x.path)).toEqual(["/api/fantasy/espn/bridge/status"]);
});
test("permission denied reaches backend revocation without cookies", async () => {
  const h = contentHarness({result: {state: "permission_denied"}}); await tick();
  const post = h.calls.find(x => x.path.endsWith("/bridge/refresh"));
  expect(post.body.state).toBe("permission_denied");
  expect(post.body.swid).toBeUndefined();
});

test("serialized popup consent generation and Forget reject content-script impersonation", async () => {
  const {state, call, message} = background();
  expect((await message({type: "forget", tabId: 4}, sender)).state).toBe("error");
  const popup = {url: "moz-extension://test/popup.html"};
  const pending = call();
  const forgotten = message({type: "forget", tabId: 4}, popup);
  expect((await pending).state).toBe("ready");
  expect((await forgotten).state).toBe("forgotten");
  expect(state.grants[origin]).toBeUndefined();
  expect((await call()).state).toBe("extension_not_enabled");
  expect((await message({type: "enable", tabId: 4}, popup)).state).toBe("enabled");
  expect(state.grants[origin].account).toBeUndefined();
  expect((await call()).state).toBe("ready");
});
