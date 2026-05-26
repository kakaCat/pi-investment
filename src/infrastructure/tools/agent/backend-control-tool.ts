// src/infrastructure/tools/agent/backend-control-tool.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";

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

interface HealthCheckResult {
  healthy: boolean;
  dbConnected?: boolean;
  error?: string;
}

/**
 * Checks health of a backend service
 * @param port - Port number of the service
 * @param timeoutMs - Timeout in milliseconds (default: 3000)
 * @param fetchFn - Optional fetch function for testing
 * @returns Health check result with status and error details
 */
export async function checkHealth(
  port: number,
  timeoutMs: number = 3000,
  fetchFn?: any
): Promise<HealthCheckResult> {
  const fetchFunc = fetchFn || ((input: string, init?: any) => fetch(input, init));
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchFunc(`http://127.0.0.1:${port}/api/health`, {
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      return {
        healthy: false,
        error: `HTTP ${response.status}`,
      };
    }

    const data = await response.json();
    return {
      healthy: data.status === "ok",
      dbConnected: data.db_connected === true,
    };
  } catch (error: any) {
    clearTimeout(timeout);

    if (error.name === "AbortError") {
      return {
        healthy: false,
        error: "Health check timeout",
      };
    }

    return {
      healthy: false,
      error: error.message || "Connection failed",
    };
  }
}

interface StartResult {
  success: boolean;
  pid?: number;
  message?: string;
  error?: string;
}

/**
 * Starts a backend service
 * @param service - Service to start ("rest", "websocket", or "all")
 * @param backendDir - Directory to store PID file (defaults to .backend)
 * @param spawnFn - Optional spawn function for testing
 * @param fetchFn - Optional fetch function for testing
 * @returns Start result with success status, PID, and message
 */
export async function startService(
  service: "rest" | "websocket" | "all",
  backendDir: string = DEFAULT_BACKEND_DIR,
  spawnFn?: any,
  fetchFn?: any
): Promise<StartResult> {
  const quantsysDir = join(PROJECT_ROOT, "quantsys-v2");

  if (!existsSync(quantsysDir)) {
    return {
      success: false,
      error: "quantsys-v2 directory not found",
    };
  }

  let command: string;
  let args: string[];
  let targetPort: number;

  if (service === "all") {
    command = "python";
    args = ["start_all.py"];
    targetPort = 5001; // Check REST API port
  } else if (service === "rest") {
    command = "python";
    args = ["api/server.py"];
    targetPort = 5001;
  } else {
    command = "python";
    args = ["api/server_websocket.py"];
    targetPort = 5003;
  }

  try {
    const spawnFunc = spawnFn || spawn;
    const subprocess = spawnFunc(command, args, {
      cwd: quantsysDir,
      detached: true,
      stdio: "ignore",
    });

    subprocess.unref();

    if (!subprocess.pid) {
      return {
        success: false,
        error: "Failed to spawn process",
      };
    }

    // Save PID
    if (service === "all") {
      savePid("rest", subprocess.pid, backendDir);
      savePid("websocket", subprocess.pid, backendDir);
    } else {
      savePid(service, subprocess.pid, backendDir);
    }

    // Wait for service to become healthy
    const maxWaitMs = 10000;
    const pollIntervalMs = 500;
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));

      const health = await checkHealth(targetPort, 1000, fetchFn);
      if (health.healthy) {
        return {
          success: true,
          pid: subprocess.pid,
          message: `Service ${service} started successfully`,
        };
      }
    }

    return {
      success: false,
      error: "Health check failed after 10 seconds",
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || "Failed to start service",
    };
  }
}

interface StopResult {
  success: boolean;
  message?: string;
  error?: string;
}

/**
 * Checks if a process is alive
 * @param pid - Process ID to check
 * @returns true if process is alive, false otherwise
 */
function isProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error: any) {
    return error.code !== "ESRCH";
  }
}

/**
 * Stops a backend service
 * @param service - Service to stop ("rest", "websocket", or "all")
 * @param backendDir - Directory containing PID file (defaults to .backend)
 * @param gracefulTimeoutMs - Timeout for graceful shutdown (default: 5000ms)
 * @returns Stop result with success status and message
 */
export async function stopService(
  service: "rest" | "websocket" | "all",
  backendDir: string = DEFAULT_BACKEND_DIR,
  gracefulTimeoutMs: number = 5000
): Promise<StopResult> {
  const pids = loadPids(backendDir);
  const servicesToStop = service === "all" ? ["rest", "websocket"] : [service];

  for (const svc of servicesToStop) {
    const pidEntry = pids[svc as "rest" | "websocket"];

    if (!pidEntry) {
      continue;
    }

    const { pid } = pidEntry;

    // Check if process exists
    if (!isProcessAlive(pid)) {
      removePid(svc as "rest" | "websocket", backendDir);
      continue;
    }

    try {
      // Send SIGTERM for graceful shutdown
      process.kill(pid, "SIGTERM");

      // Wait for process to exit
      const startTime = Date.now();
      while (Date.now() - startTime < gracefulTimeoutMs) {
        await new Promise((resolve) => setTimeout(resolve, 500));

        if (!isProcessAlive(pid)) {
          removePid(svc as "rest" | "websocket", backendDir);
          break;
        }
      }

      // If still alive, force kill
      if (isProcessAlive(pid)) {
        process.kill(pid, "SIGKILL");
        await new Promise((resolve) => setTimeout(resolve, 500));
        removePid(svc as "rest" | "websocket", backendDir);
      }
    } catch (error: any) {
      if (error.code === "ESRCH") {
        // Process not found, clean up PID file
        removePid(svc as "rest" | "websocket", backendDir);
      } else if (error.code === "EPERM") {
        return {
          success: false,
          error: `Cannot stop process (PID: ${pid}). Check process owner.`,
        };
      } else {
        return {
          success: false,
          error: error.message || "Failed to stop service",
        };
      }
    }
  }

  return {
    success: true,
    message: `Service ${service} stopped successfully`,
  };
}

interface ServiceStatus {
  status: "running" | "stopped" | "unhealthy";
  pid?: number;
  port: number;
  uptime?: string;
  error?: string;
}

/**
 * Calculates uptime from start time
 * @param startTime - ISO timestamp of when process started
 * @returns Human-readable uptime string
 */
function calculateUptime(startTime: string): string {
  const start = new Date(startTime).getTime();
  const now = Date.now();
  const diffMs = now - start;

  const hours = Math.floor(diffMs / 3600000);
  const minutes = Math.floor((diffMs % 3600000) / 60000);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Gets the status of a backend service
 * @param service - Service to check ("rest" or "websocket")
 * @param backendDir - Directory containing PID file (defaults to .backend)
 * @param fetchFn - Optional fetch function for testing
 * @returns Service status with health information
 */
export async function getServiceStatus(
  service: "rest" | "websocket",
  backendDir: string = DEFAULT_BACKEND_DIR,
  fetchFn?: any
): Promise<ServiceStatus> {
  const port = service === "rest" ? 5001 : 5003;
  const pids = loadPids(backendDir);
  const pidEntry = pids[service];

  if (!pidEntry) {
    return {
      status: "stopped",
      port,
    };
  }

  const { pid, startTime } = pidEntry;

  // Check if process is alive
  if (!isProcessAlive(pid)) {
    removePid(service, backendDir);
    return {
      status: "stopped",
      port,
    };
  }

  // Check health
  const health = await checkHealth(port, 3000, fetchFn);

  if (!health.healthy) {
    return {
      status: "unhealthy",
      pid,
      port,
      uptime: calculateUptime(startTime),
      error: health.error,
    };
  }

  return {
    status: "running",
    pid,
    port,
    uptime: calculateUptime(startTime),
  };
}
