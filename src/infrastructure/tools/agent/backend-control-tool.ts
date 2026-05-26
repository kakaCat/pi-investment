// src/infrastructure/tools/agent/backend-control-tool.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PID_FILE_NAME = "pids.json";
const MAX_DEPTH = 20;

function findProjectRoot(startDir: string = __dirname): string {
  let current = startDir;
  let depth = 0;

  while (depth < MAX_DEPTH) {
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
    depth++;
  }

  // Fallback if max depth reached
  return join(startDir, "..", "..", "..", "..");
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

/**
 * Saves a PID entry for a backend service
 * @param service - Service name ("rest" or "websocket")
 * @param pid - Process ID
 * @param backendDir - Directory to store PID file (defaults to .backend)
 * @throws Error if unable to write PID file
 */
export function savePid(
  service: "rest" | "websocket",
  pid: number,
  backendDir: string = DEFAULT_BACKEND_DIR
): void {
  if (!existsSync(backendDir)) {
    mkdirSync(backendDir, { recursive: true });
  }

  const pidFile = join(backendDir, PID_FILE_NAME);
  const pids = loadPids(backendDir);

  pids[service] = {
    pid,
    startTime: new Date().toISOString(),
  };

  try {
    writeFileSync(pidFile, JSON.stringify(pids, null, 2), "utf-8");
  } catch (error) {
    throw new Error(`Failed to write PID file: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * Loads PID entries from the PID file
 * @param backendDir - Directory containing PID file (defaults to .backend)
 * @returns PID store object, or empty object if file doesn't exist or is corrupted
 */
export function loadPids(backendDir: string = DEFAULT_BACKEND_DIR): PidStore {
  const pidFile = join(backendDir, PID_FILE_NAME);

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

/**
 * Removes a PID entry for a backend service
 * @param service - Service name ("rest" or "websocket")
 * @param backendDir - Directory containing PID file (defaults to .backend)
 * @throws Error if unable to write PID file
 */
export function removePid(
  service: "rest" | "websocket",
  backendDir: string = DEFAULT_BACKEND_DIR
): void {
  const pidFile = join(backendDir, PID_FILE_NAME);
  const pids = loadPids(backendDir);

  delete pids[service];

  try {
    if (Object.keys(pids).length === 0) {
      if (existsSync(pidFile)) {
        writeFileSync(pidFile, "{}", "utf-8");
      }
    } else {
      writeFileSync(pidFile, JSON.stringify(pids, null, 2), "utf-8");
    }
  } catch (error) {
    throw new Error(`Failed to write PID file: ${error instanceof Error ? error.message : String(error)}`);
  }
}
