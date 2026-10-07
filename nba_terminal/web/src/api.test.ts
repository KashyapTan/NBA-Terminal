import { afterEach, describe, expect, it, vi } from "vitest";
import { getGame, getGames, getJson, getMeta, getPlayerAnalysis, getUpcoming } from "./api";

describe("API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns successful JSON and builds the app endpoint paths", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetch);
    await expect(getJson("/api/example")).resolves.toEqual({ ok: true });
    await getMeta();
    await getUpcoming();
    await getGames("2025-26");
    await getGame("0022400001");
    await getPlayerAnalysis("0022400001", "123", "2025-26", "Playoffs");
    expect(fetch.mock.calls.map(([path]) => path)).toEqual([
      "/api/example",
      "/api/meta",
      "/api/upcoming",
      "/api/games?season=2025-26",
      "/api/games/0022400001",
      "/api/games/0022400001/players/123?season=2025-26&phase=Playoffs",
    ]);
  });

  it("surfaces structured API detail on an error response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => ({ detail: "Source offline" }),
      }),
    );
    await expect(getJson("/api/error")).rejects.toThrow("Source offline");
  });

  it("falls back to the HTTP status when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => {
          throw new Error("invalid JSON");
        },
      }),
    );
    await expect(getJson("/api/error")).rejects.toThrow("Request failed (503)");
  });
});
