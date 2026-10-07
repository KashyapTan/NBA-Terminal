export interface DevService {
  name: string;
  command: string;
  args: string[];
  cwd: string;
}

export function getDevServices({
  repoRoot,
  webRoot,
  bunExecutable,
}: {
  repoRoot: string;
  webRoot: string;
  bunExecutable: string;
}): DevService[] {
  return [
    {
      name: "FastAPI",
      command: "uv",
      args: ["run", "uvicorn", "nba_terminal.webapp:app", "--host", "127.0.0.1", "--port", "8000"],
      cwd: repoRoot,
    },
    {
      name: "Vite",
      command: bunExecutable,
      args: ["run", "vite", "--host", "127.0.0.1"],
      cwd: webRoot,
    },
  ];
}
