/**
 * QuantSys Daemon Adapter — TypeScript client for QuantSys CLI daemon mode.
 *
 * Maintains a long-running `python -m quantsys.cli --daemon` process that
 * communicates via stdin/stdout using JSON-RPC 2.0 protocol.
 * Automatically restarts on crashes.
 *
 * Replaces the old python-bridge.ts (akshare_bridge.py daemon).
 */

import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import { existsSync } from "node:fs";
import * as readline from "readline";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..", "..", "..");
const QUANT_ROOT = join(PROJECT_ROOT, "quant");
const VENV_PYTHON = join(PROJECT_ROOT, ".venv", "bin", "python3");
const RESTART_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 150_000;
const STARTUP_TIMEOUT_MS = 5000;

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

interface PendingRequest {
  resolve: (value: string) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

class QuantSysDaemon {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, PendingRequest>();
  private isShuttingDown = false;
  private restartTimer: NodeJS.Timeout | null = null;
  private rl: readline.Interface | null = null;
  private startupPromise: Promise<void> | null = null;

  constructor() {
    this.startupPromise = this.start();
    process.on("exit", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());
    process.on("SIGTERM", () => this.shutdown());
  }

  private async start(): Promise<void> {
    if (this.isShuttingDown) return;

    try {
      // Use venv Python if available, otherwise fall back to system python3
      const pythonCmd = existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";

      // Add QUANT_ROOT to PYTHONPATH so 'api' module can be imported
      const pythonPath = process.env.PYTHONPATH
        ? `${QUANT_ROOT}:${process.env.PYTHONPATH}`
        : QUANT_ROOT;

      this.process = spawn(pythonCmd, ["-m", "quantsys.cli", "--daemon"], {
        cwd: QUANT_ROOT,
        stdio: ["pipe", "pipe", "pipe"],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: "1",
          PYTHONPATH: pythonPath,
        },
      });

      this.rl = readline.createInterface({
        input: this.process.stdout!,
        crlfDelay: Infinity,
      });

      this.rl.on("line", (line: string) => {
        this.handleResponse(line);
      });

      this.process.stderr?.on("data", (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) {
          console.error(`[quantsys-daemon stderr] ${msg}`);
        }
      });

      this.process.on("exit", (code, signal) => {
        console.warn(
          `[quantsys-daemon] Process exited (code=${code}, signal=${signal})`
        );
        this.cleanup();

        for (const [id, pending] of this.pendingRequests) {
          clearTimeout(pending.timer);
          pending.reject(new Error("QuantSys daemon process exited unexpectedly"));
          this.pendingRequests.delete(id);
        }

        if (!this.isShuttingDown) {
          console.log(
            `[quantsys-daemon] Restarting in ${RESTART_DELAY_MS}ms...`
          );
          this.restartTimer = setTimeout(() => {
            this.startupPromise = this.start();
          }, RESTART_DELAY_MS);
        }
      });

      this.process.on("error", (err) => {
        console.error(`[quantsys-daemon] Process error:`, err);
      });

      console.log(`[quantsys-daemon] Started (PID=${this.process.pid})`);

      // Wait for daemon to be ready
      await this.waitForReady();
    } catch (error) {
      console.error(`[quantsys-daemon] Failed to start:`, error);
      if (!this.isShuttingDown) {
        this.restartTimer = setTimeout(() => {
          this.startupPromise = this.start();
        }, RESTART_DELAY_MS);
      }
      throw error;
    }
  }

  private async waitForReady(timeoutMs = STARTUP_TIMEOUT_MS): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (this.process && this.process.exitCode === null) {
        // Process is alive, consider it ready
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`QuantSys daemon failed to start within ${timeoutMs}ms`);
  }

  private cleanup(): void {
    if (this.rl) {
      this.rl.close();
      this.rl.removeAllListeners();
      this.rl = null;
    }
    if (this.process) {
      this.process.stdin?.removeAllListeners();
      this.process.stdout?.removeAllListeners();
      this.process.stderr?.removeAllListeners();
      this.process.removeAllListeners();
    }
    this.process = null;
  }

  private handleResponse(line: string): void {
    if (!line.trim()) return;

    try {
      const response: JsonRpcResponse = JSON.parse(line);

      if (response.jsonrpc !== "2.0" || typeof response.id !== "number") {
        console.warn(`[quantsys-daemon] Invalid JSON-RPC response:`, line);
        return;
      }

      const pending = this.pendingRequests.get(response.id);
      if (!pending) {
        console.warn(
          `[quantsys-daemon] Received response for unknown request ID ${response.id}`
        );
        return;
      }

      clearTimeout(pending.timer);
      this.pendingRequests.delete(response.id);

      if (response.error) {
        pending.reject(new Error(response.error.message));
      } else {
        const resultStr =
          typeof response.result === "string"
            ? response.result
            : JSON.stringify(response.result);
        pending.resolve(resultStr);
      }
    } catch (error) {
      console.error(
        `[quantsys-daemon] Failed to parse response:`,
        line,
        error
      );
    }
  }

  async call(
    method: string,
    params: Record<string, unknown> = {}
  ): Promise<string> {
    // If daemon is not running, attempt to restart
    if (!this.process || this.process.exitCode !== null) {
      console.warn("[quantsys-daemon] Not running, attempting restart...");
      this.startupPromise = this.start();

      try {
        await this.startupPromise;
      } catch (error) {
        throw new Error(
          `QuantSys daemon is not running and failed to restart: ${
            error instanceof Error ? error.message : String(error)
          }\n\n` +
          `To manually start the daemon, run:\n` +
          `  cd quant && python3 -m quantsys.cli --daemon`
        );
      }
    }

    // Wait for any pending startup to complete
    if (this.startupPromise) {
      await this.startupPromise;
    }

    const id = ++this.requestId;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);

      this.pendingRequests.set(id, { resolve, reject, timer });

      try {
        const requestLine = JSON.stringify(request) + "\n";
        this.process!.stdin!.write(requestLine, "utf8", (err) => {
          if (err) {
            clearTimeout(timer);
            this.pendingRequests.delete(id);
            reject(
              new Error(`Failed to write to QuantSys daemon: ${err.message}`)
            );
          }
        });
      } catch (error) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  shutdown(): void {
    if (this.isShuttingDown) return;
    this.isShuttingDown = true;

    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }

    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new Error("QuantSys daemon is shutting down"));
      this.pendingRequests.delete(id);
    }

    const proc = this.process;
    if (proc) {
      try {
        proc.stdin?.end();
        proc.kill("SIGTERM");
        setTimeout(() => {
          if (proc.exitCode === null) {
            proc.kill("SIGKILL");
          }
        }, 2000);
      } catch (error) {
        console.error(`[quantsys-daemon] Error during shutdown:`, error);
      }
    }

    this.cleanup();
  }
}

let daemon: QuantSysDaemon | null = null;

export async function callQuantSysDaemon(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  if (!daemon) {
    daemon = new QuantSysDaemon();
  }
  return daemon.call(func, args);
}

export function shutdownQuantSysDaemon(): void {
  if (daemon) {
    daemon.shutdown();
    daemon = null;
  }
}
