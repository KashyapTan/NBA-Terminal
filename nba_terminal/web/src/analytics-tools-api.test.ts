import { afterEach, expect, it, vi } from "vitest";
import { getAnalyticsTool, getToolsMeta } from "./analytics-tools-api";
afterEach(() => vi.unstubAllGlobals());
it("encodes read-only search and filename values as query data", async () => {
  const response = { state: "ready", files: [] };
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response });
  vi.stubGlobal("fetch", fetch);
  expect(
    await getAnalyticsTool("picks", { q: "Curry & <script>", filename: "../note.MD" }),
  ).toEqual(response);
  const url = new URL(fetch.mock.calls[0][0], "http://localhost");
  expect(url.pathname).toBe("/api/tools/picks");
  expect(url.searchParams.get("q")).toBe("Curry & <script>");
  expect(url.searchParams.get("filename")).toBe("../note.MD");
});
it("uses the focused static tools metadata route", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ teams: [] }) });
  vi.stubGlobal("fetch", fetch);
  await getToolsMeta();
  expect(fetch).toHaveBeenCalledWith("/api/tools/meta");
});
