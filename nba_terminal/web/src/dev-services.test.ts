import { describe, expect, it } from "vitest";
import { getDevServices } from "./dev-services";

describe("development service commands", () => {
  it("starts FastAPI through uv and Vite through Bun from their project directories", () => {
    const services = getDevServices({
      repoRoot: "/workspace/nba-terminal",
      webRoot: "/workspace/nba-terminal/nba_terminal/web",
      bunExecutable: "/usr/local/bin/bun",
    });

    expect(services).toEqual([
      {
        name: "FastAPI",
        command: "uv",
        args: [
          "run",
          "uvicorn",
          "nba_terminal.webapp:app",
          "--host",
          "127.0.0.1",
          "--port",
          "8000",
        ],
        cwd: "/workspace/nba-terminal",
      },
      {
        name: "Vite",
        command: "/usr/local/bin/bun",
        args: ["run", "vite", "--host", "127.0.0.1"],
        cwd: "/workspace/nba-terminal/nba_terminal/web",
      },
    ]);
  });

  it("forwards CLI arguments to Vite without changing the FastAPI port", () => {
    const services = getDevServices({
      repoRoot: "/workspace/nba-terminal",
      webRoot: "/workspace/nba-terminal/nba_terminal/web",
      bunExecutable: "/usr/local/bin/bun",
      viteArgs: ["--port", "4173", "--strictPort"],
    });

    expect(services[0].args).toContain("8000");
    expect(services[1].args).toEqual([
      "run",
      "vite",
      "--host",
      "127.0.0.1",
      "--port",
      "4173",
      "--strictPort",
    ]);
  });
});
