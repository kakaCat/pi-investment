// src/infrastructure/tools/agent/backend-control-tool.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

function findProjectRoot(startDir: string = __dirname): string {
  let current = startDir;
  while (true) {
    if (
      existsSync(join(current, "package.json")) &&
      existsSync(join(current, "quantsys-v2"))
    ) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      return join(startDir, "..", "..", "..", "..");
    }
    current = parent;
  }
}

const PROJECT_ROOT = findProjectRoot();
const DEFAULT_BACKEND_DIR = join(PROJECT_ROOT, ".backend");

interface PidEntry {
  pid: number;
  startTime: string;
}

interface PidStore {
  rest?: PidEntry;
  websocket?: PidEntry;
}

export function savePid(
  service: "rest" | "websocket",
  pid: number,
  backendDir: string = DEFAULT_BACKEND_DIR
): void {
  if (!existsSync(backendDir)) {
    mkdirSync(backendDir, { recursive: true });
  }

  const pidFile = join(backendDir, "pids.json");
  const pids = loadPids(backendDir);

  pids[service] = {
    pid,
    startTime: new Date().toISOString(),
  };

  writeFileSync(pidFile, JSON.stringify(pids, null, 2), "utf-8");
}

export function loadPids(backendDir: string = DEFAULT_BACKEND_DIR): PidStore {
  const pidFile = join(backendDir, "pids.json");

  if (!existsSync(pidFile)) {
    return {};
  }

  try {
    const content = readFileSync(pidFile, "utf-8");
    return JSON.parse(content);
  } catch (error) {
    return {};
  }
}

export function removePid(
  service: "rest" | "websocket",
  backendDir: string = DEFAULT_BACKEND_DIR
): void {
  const pidFile = join(backendDir, "pids.json");
  const pids = loadPids(backendDir);

  delete pids[service];

  if (Object.keys(pids).length === 0) {
    if (existsSync(pidFile)) {
      writeFileSync(pidFile, "{}", "utf-8");
    }
  } else {
    writeFileSync(pidFile, JSON.stringify(pids, null, 2), "utf-8");
  }
}
