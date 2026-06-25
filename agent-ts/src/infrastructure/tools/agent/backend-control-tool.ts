// src/infrastructure/tools/agent/backend-control-tool.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync, openSync, closeSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { spawn, execSync } from "child_process";
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PID_FILE_NAME = "pids.json";
const QUANTSYS_DIR_NAME = "quantsys-v2";
const MAX_DEPTH = 20;

/**
 * Locates the repo root by walking up from `startDir` until a directory
 * containing `quantsys-v2/` is found. quantsys-v2 is the backend this tool
 * manages, so its presence is the authoritative anchor regardless of where the
 * TypeScript code lives (repo root or the agent-ts/ subdirectory) or whether a
 * package.json sits alongside it.
 *
 * An explicit `QUANTSYS_PROJECT_ROOT` env var overrides the search entirely,
 * which is the escape hatch for non-standard layouts and CI.
 *
 * Returns null when no quantsys-v2 directory can be found; callers surface a
 * clear error rather than spawning against a guessed, possibly-wrong path.
 */
function findProjectRoot(startDir: string = __dirname): string | null {
  const override = process.env.QUANTSYS_PROJECT_ROOT;
  if (override && existsSync(join(override, QUANTSYS_DIR_NAME))) {
    return override;
  }

  let current = startDir;
  let depth = 0;

  while (depth < MAX_DEPTH) {
    if (existsSync(join(current, QUANTSYS_DIR_NAME))) {
      return current;
    }
    const parent = dirname(current);
    if (parent === current) {
      break; // reached filesystem root without a match
    }
    current = parent;
    depth++;
  }

  return null;
}

const PROJECT_ROOT = findProjectRoot();
// PROJECT_ROOT may be null when quantsys-v2 cannot be located. PID bookkeeping
// still needs a directory, so fall back to cwd; startService re-validates the
// real quantsys-v2 path before spawning and returns a clear error if missing.
const DEFAULT_BACKEND_DIR = join(PROJECT_ROOT ?? process.cwd(), ".backend");

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

/**
 * Reads the last N lines from a service log file
 * @param lines - Number of lines to read
 * @param service - Service name ("rest", "websocket", or "all")
 * @returns Array of log lines, or error message if file doesn't exist
 */
function readServiceLogs(lines: number, service: "rest" | "websocket" | "all"): string[] {
  const logFile = service === "all"
    ? "/tmp/quantsys-v2.log"
    : `/tmp/quantsys-v2-${service}.log`;

  if (!existsSync(logFile)) {
    return ["日志文件不存在"];
  }

  try {
    const content = execSync(`tail -n ${lines} "${logFile}"`, {
      encoding: "utf-8",
      timeout: 2000,
    });
    return content.trim().split("\n");
  } catch (error: any) {
    return [`读取日志失败: ${error.message}`];
  }
}

/**
 * Checks if a port is currently in use
 * @param port - Port number to check
 * @returns true if port is in use, false otherwise
 */
function isPortInUse(port: number): boolean {
  try {
    const result = execSync(`lsof -ti:${port}`, {
      encoding: "utf-8",
      timeout: 2000,
    });
    return result.trim().length > 0;
  } catch {
    return false;
  }
}

/**
 * Gets the PID of the process using a port
 * @param port - Port number to check
 * @returns PID of the process, or null if port is not in use
 */
function getProcessOnPort(port: number): number | null {
  try {
    const result = execSync(`lsof -ti:${port}`, {
      encoding: "utf-8",
      timeout: 2000,
    });
    const pid = parseInt(result.trim().split("\n")[0]);
    return isNaN(pid) ? null : pid;
  } catch {
    return null;
  }
}

/**
 * Analyzes log lines for common error patterns
 * @param logs - Array of log lines to analyze
 * @returns Array of detected error lines
 */
function detectErrorsInLogs(logs: string[]): string[] {
  const errorPatterns = [
    /ModuleNotFoundError/,
    /ImportError/,
    /Address already in use/,
    /Connection refused/,
    /Database.*error/i,
    /Exception/,
    /Error:/,
    /Failed to/,
  ];

  return logs.filter(line =>
    errorPatterns.some(pattern => pattern.test(line))
  );
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
  diagnostics?: {
    reason: "process_crashed" | "port_conflict" | "health_check_timeout";
    logs?: string[];
    detectedErrors?: string[];
    hint?: string;
    conflictingPid?: number;
    elapsedMs?: number;
  };
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
  const quantsysDir = PROJECT_ROOT
    ? join(PROJECT_ROOT, QUANTSYS_DIR_NAME)
    : null;

  if (!quantsysDir || !existsSync(quantsysDir)) {
    return {
      success: false,
      error:
        `${QUANTSYS_DIR_NAME} directory not found (searched up from ${__dirname}). ` +
        `Set QUANTSYS_PROJECT_ROOT to the directory containing ${QUANTSYS_DIR_NAME}/ if it lives elsewhere.`,
    };
  }

  let command: string;
  let args: string[];
  let targetPort: number;

  if (service === "all") {
    // Spring Boot style unified process - single server.py includes scheduler
    command = "python";
    args = ["adapters/inbound/api/server.py"];
    targetPort = 5001;
  } else if (service === "rest") {
    // Spring Boot style unified process - single server.py includes scheduler
    command = "python";
    args = ["adapters/inbound/api/server.py"];
    targetPort = 5001;
  } else {
    // WebSocket service (if still using separate process)
    command = "python";
    args = ["api/server_websocket.py"];
    targetPort = 5003;
  }

  try {
    // Determine log file path
    const logFile = service === "all"
      ? "/tmp/quantsys-v2.log"
      : `/tmp/quantsys-v2-${service}.log`;

    // Open log file for writing
    const logFd = openSync(logFile, "a");

    const spawnFunc = spawnFn || spawn;
    const subprocess = spawnFunc(command, args, {
      cwd: quantsysDir,
      detached: true,
      stdio: ["ignore", logFd, logFd], // Redirect stdout and stderr to log file
    });

    subprocess.unref();

    // Close log file descriptor after spawn
    closeSync(logFd);

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

    // Wait for service to become healthy - staged polling
    const stage1MaxMs = 5000;  // Stage 1: fast polling for 5 seconds
    const stage2MaxMs = 10000; // Stage 2: slow polling for 10 seconds
    const stage1IntervalMs = 500;
    const stage2IntervalMs = 1000;
    const startTime = Date.now();

    // Stage 1: Fast polling (0-5 seconds)
    while (Date.now() - startTime < stage1MaxMs) {
      await new Promise((resolve) => setTimeout(resolve, stage1IntervalMs));

      const health = await checkHealth(targetPort, 1000, fetchFn);
      if (health.healthy) {
        return {
          success: true,
          pid: subprocess.pid,
          message: `Service ${service} started successfully`,
        };
      }
    }

    // Stage 2: Slow polling (5-15 seconds)
    while (Date.now() - startTime < stage1MaxMs + stage2MaxMs) {
      await new Promise((resolve) => setTimeout(resolve, stage2IntervalMs));

      const health = await checkHealth(targetPort, 1000, fetchFn);
      if (health.healthy) {
        return {
          success: true,
          pid: subprocess.pid,
          message: `Service ${service} started successfully`,
        };
      }
    }

    // Health check timeout - run diagnostics
    const elapsedMs = Date.now() - startTime;

    // Diagnostic Step 1: Check if process is still alive
    if (!subprocess.pid || !isProcessAlive(subprocess.pid)) {
      const logs = readServiceLogs(50, service);
      const detectedErrors = detectErrorsInLogs(logs);

      return {
        success: false,
        error: "进程启动后崩溃",
        diagnostics: {
          reason: "process_crashed",
          logs,
          detectedErrors,
          hint: detectedErrors.length > 0
            ? "检测到以下错误，请查看日志"
            : "进程异常退出，未检测到明显错误",
          elapsedMs,
        },
      };
    }

    // Diagnostic Step 2: Check for port conflicts
    if (isPortInUse(targetPort)) {
      const conflictingPid = getProcessOnPort(targetPort);

      // Check if it's our process or another process
      if (conflictingPid && conflictingPid !== subprocess.pid) {
        return {
          success: false,
          error: `端口 ${targetPort} 已被其他进程占用`,
          diagnostics: {
            reason: "port_conflict",
            conflictingPid,
            hint: `使用 'kill ${conflictingPid}' 终止冲突进程，或使用 'backend_control stop' 清理旧进程`,
            elapsedMs,
          },
        };
      }
    }

    // Diagnostic Step 3: Analyze service logs
    const logs = readServiceLogs(30, service);
    const detectedErrors = detectErrorsInLogs(logs);

    return {
      success: false,
      error: "服务未响应健康检查",
      diagnostics: {
        reason: "health_check_timeout",
        logs,
        detectedErrors,
        hint: detectedErrors.length > 0
          ? "检测到以下错误，请查看日志"
          : "未检测到明显错误，可能是启动时间过长或依赖服务未就绪",
        elapsedMs,
      },
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

interface RestartResult {
  success: boolean;
  pid?: number;
  message?: string;
  error?: string;
}

/**
 * Restarts a backend service
 * @param service - Service to restart ("rest", "websocket", or "all")
 * @param backendDir - Directory containing PID file (defaults to .backend)
 * @returns Restart result with success status, new PID, and message
 */
export async function restartService(
  service: "rest" | "websocket" | "all",
  backendDir: string = DEFAULT_BACKEND_DIR
): Promise<RestartResult> {
  const stopResult = await stopService(service, backendDir);

  if (!stopResult.success) {
    return {
      success: false,
      error: `Failed to stop service: ${stopResult.error}`,
    };
  }

  await new Promise((resolve) => setTimeout(resolve, 2000));

  const startResult = await startService(service, backendDir);

  if (!startResult.success) {
    return {
      success: false,
      error: `Failed to start service: ${startResult.error}`,
    };
  }

  return {
    success: true,
    pid: startResult.pid,
    message: `Service ${service} restarted successfully`,
  };
}

export const backendControlTool: ToolDefinition = {
  name: "backend_control",
  label: "Backend Control",
  description: "Manage quantsys-v2 backend services lifecycle (start/stop/restart/status)",
  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("start"),
      Type.Literal("stop"),
      Type.Literal("restart"),
      Type.Literal("status"),
    ], {
      description: "Operation to perform",
    }),
    service: Type.Optional(Type.Union([
      Type.Literal("all"),
      Type.Literal("rest"),
      Type.Literal("websocket"),
    ], {
      description: "Target service (default: all)",
      default: "all",
    })),
  }),
  execute: async (_toolCallId, args: any) => {
    const service = (args.service || "all") as "rest" | "websocket" | "all";
    const action = args.action;

    let resultText = "";

    try {
      if (action === "start") {
        const result = await startService(service);
        if (!(result as any).success) {
          let errorText = `❌ Failed to start service: ${(result as any).error}`;

          if (result.diagnostics) {
            errorText += `\n\n**诊断信息:**`;
            errorText += `\n- 原因: ${result.diagnostics.reason}`;

            if (result.diagnostics.elapsedMs) {
              errorText += `\n- 等待时间: ${result.diagnostics.elapsedMs}ms`;
            }

            if (result.diagnostics.conflictingPid) {
              errorText += `\n- 冲突进程 PID: ${result.diagnostics.conflictingPid}`;
            }

            if (result.diagnostics.hint) {
              errorText += `\n- 建议: ${result.diagnostics.hint}`;
            }

            if (result.diagnostics.detectedErrors && result.diagnostics.detectedErrors.length > 0) {
              errorText += `\n\n**检测到的错误:**`;
              result.diagnostics.detectedErrors.slice(0, 5).forEach(err => {
                errorText += `\n  ${err}`;
              });
            }

            if (result.diagnostics.logs && result.diagnostics.logs.length > 0) {
              errorText += `\n\n**最近日志 (最后10行):**`;
              result.diagnostics.logs.slice(-10).forEach(log => {
                errorText += `\n  ${log}`;
              });
            }
          }

          resultText = errorText;
        } else {
          let successText = `✅ ${(result as any).message}\nPID: ${result.pid}`;

          if (result.diagnostics?.elapsedMs) {
            successText += `\n启动耗时: ${result.diagnostics.elapsedMs}ms`;
          }

          resultText = successText;
        }
      } else if (action === "stop") {
        const result = await stopService(service);
        if (!(result as any).success) {
          resultText = `❌ Failed to stop service: ${(result as any).error}`;
        } else {
          resultText = `✅ ${(result as any).message}`;
        }
      } else if (action === "restart") {
        const result = await restartService(service);
        if (!(result as any).success) {
          resultText = `❌ Failed to restart service: ${(result as any).error}`;
        } else {
          resultText = `✅ ${(result as any).message}\nNew PID: ${result.pid}`;
        }
      } else if (action === "status") {
        if (service === "all") {
          const restStatus = await getServiceStatus("rest");
          const wsStatus = await getServiceStatus("websocket");

          resultText = `📊 Backend Services Status:

REST API (port 5001):
  Status: ${restStatus.status}
  ${restStatus.pid ? `PID: ${restStatus.pid}` : ""}
  ${restStatus.uptime ? `Uptime: ${restStatus.uptime}` : ""}
  ${restStatus.error ? `Error: ${restStatus.error}` : ""}

WebSocket (port 5003):
  Status: ${wsStatus.status}
  ${wsStatus.pid ? `PID: ${wsStatus.pid}` : ""}
  ${wsStatus.uptime ? `Uptime: ${wsStatus.uptime}` : ""}
  ${wsStatus.error ? `Error: ${wsStatus.error}` : ""}`;
        } else {
          const status = await getServiceStatus(service as "rest" | "websocket");
          resultText = `📊 Service Status:
  Status: ${status.status}
  Port: ${status.port}
  ${status.pid ? `PID: ${status.pid}` : ""}
  ${status.uptime ? `Uptime: ${status.uptime}` : ""}
  ${status.error ? `Error: ${status.error}` : ""}`;
        }
      } else {
        resultText = `❌ Unknown action: ${action}`;
      }
    } catch (error: any) {
      resultText = `❌ Error: ${error.message || "Unknown error"}`;
    }

    return {
      content: [
        {
          type: "text" as const,
          text: resultText,
        },
      ],
      details: {
        action,
        service,
      },
    };
  },
};
