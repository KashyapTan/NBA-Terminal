import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { getDevServices } from "../src/dev-services.ts";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const webRoot = fileURLToPath(new URL("../", import.meta.url));
const services = getDevServices({
  repoRoot,
  webRoot,
  bunExecutable: process.execPath,
});
const children = [];
let stopping = false;
let shutdownTimer;

function signalChild(child, signal) {
  if (!child.pid) return;

  try {
    if (process.platform === "win32") {
      child.kill(signal);
    } else {
      process.kill(-child.pid, signal);
    }
  } catch (error) {
    if (error.code !== "ESRCH") {
      console.error(`Could not send ${signal} to child process ${child.pid}:`, error.message);
    }
  }
}

function finishWhenChildrenExit() {
  if (children.every(({ child }) => child.exitCode !== null || child.signalCode !== null)) {
    clearTimeout(shutdownTimer);
  }
}

function stopAll(code, signal = "SIGTERM") {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;

  for (const { child } of children) signalChild(child, signal);

  shutdownTimer = setTimeout(() => {
    for (const { child } of children) {
      if (child.exitCode === null && child.signalCode === null) signalChild(child, "SIGKILL");
    }
  }, 5000);
  shutdownTimer.unref();
  finishWhenChildrenExit();
}

process.once("SIGINT", () => stopAll(130, "SIGINT"));
process.once("SIGTERM", () => stopAll(143, "SIGTERM"));

for (const service of services) {
  if (stopping) break;

  try {
    const child = spawn(service.command, service.args, {
      cwd: service.cwd,
      stdio: "inherit",
      detached: process.platform !== "win32",
    });
    children.push({ child, name: service.name });

    child.on("error", (error) => {
      console.error(`[${service.name}] failed to start:`, error.message);
      stopAll(1);
    });
    child.on("close", (code, signal) => {
      if (!stopping) {
        const result = code ?? 1;
        console.error(`[${service.name}] exited (${signal ?? result}); stopping the other service.`);
        stopAll(result === 0 ? 1 : result);
      }
      finishWhenChildrenExit();
    });
  } catch (error) {
    console.error(`[${service.name}] failed to start:`, error.message);
    stopAll(1);
  }
}
