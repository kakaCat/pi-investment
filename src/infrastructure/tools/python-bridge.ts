/**
 * Python Bridge - Persistent Python process with JSON-RPC communication
 *
 * Maintains a long-running Python daemon process that communicates via stdin/stdout
 * using JSON-RPC protocol. Automatically restarts on crashes and handles lifecycle.
 */

import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import * as readline from "readline";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PYTHON_SCRIPT = join(__dirname, "..", "..", "..", "python", "akshare_bridge.py");
const RESTART_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 90000; // 90 seconds (max timeout, controlled by caller)

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

class PythonDaemon {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, PendingRequest>();
  private isShuttingDown = false;
  private restartTimer: NodeJS.Timeout | null = null;
  private rl: readline.Interface | null = null;

  constructor() {
    this.start();

    // Graceful shutdown on process exit
    process.on("exit", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());
    process.on("SIGTERM", () => this.shutdown());
  }

  private start(): void {
    if (this.isShuttingDown) return;

    try {
      // Spawn Python process in daemon mode
      this.process = spawn("python3", [PYTHON_SCRIPT, "--daemon"], {
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, TQDM_DISABLE: "1", PYTHONUNBUFFERED: "1" },
      });

      // Set up readline interface for line-by-line stdout reading
      this.rl = readline.createInterface({
        input: this.process.stdout!,
        crlfDelay: Infinity,
      });

      this.rl.on("line", (line) => {
        this.handleResponse(line);
      });

      // Handle stderr
      this.process.stderr?.on("data", (data) => {
        const msg = data.toString().trim();
        if (msg) {
          console.error(`[python-daemon stderr] ${msg}`);
        }
      });

      // Handle process exit
      this.process.on("exit", (code, signal) => {
        console.warn(`[python-daemon] Process exited (code=${code}, signal=${signal})`);
        this.cleanup();

        // Reject all pending requests
        const entries = Array.from(this.pendingRequests.entries());
        for (const [id, pending] of entries) {
          clearTimeout(pending.timer);
          pending.reject(new Error("Python process exited unexpectedly"));
          this.pendingRequests.delete(id);
        }

        // Auto-restart after delay
        if (!this.isShuttingDown) {
          console.log(`[python-daemon] Restarting in ${RESTART_DELAY_MS}ms...`);
          this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
        }
      });

      // Handle process errors
      this.process.on("error", (err) => {
        console.error(`[python-daemon] Process error:`, err);
      });

      console.log(`[python-daemon] Started (PID=${this.process.pid})`);
    } catch (error) {
      console.error(`[python-daemon] Failed to start:`, error);
      // Retry after delay
      if (!this.isShuttingDown) {
        this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
      }
    }
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
        console.warn(`[python-daemon] Invalid JSON-RPC response:`, line);
        return;
      }

      const pending = this.pendingRequests.get(response.id);
      if (!pending) {
        console.warn(`[python-daemon] Received response for unknown request ID ${response.id}`);
        return;
      }

      clearTimeout(pending.timer);
      this.pendingRequests.delete(response.id);

      if (response.error) {
        pending.reject(new Error(response.error.message));
      } else {
        // Convert result to JSON string for compatibility with existing code
        const resultStr = typeof response.result === "string"
          ? response.result
          : JSON.stringify(response.result, null, 0);
        pending.resolve(resultStr);
      }
    } catch (error) {
      console.error(`[python-daemon] Failed to parse response:`, line, error);
    }
  }

  async call(method: string, params: Record<string, unknown> = {}): Promise<string> {
    if (!this.process || this.process.exitCode !== null) {
      throw new Error("Python daemon is not running");
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
            reject(new Error(`Failed to write to Python process: ${err.message}`));
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

    // Reject all pending requests
    const entries = Array.from(this.pendingRequests.entries());
    for (const [id, pending] of entries) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Python daemon is shutting down"));
      this.pendingRequests.delete(id);
    }

    if (this.process) {
      try {
        // Close stdin to signal the Python process to exit gracefully
        this.process.stdin?.end();
        this.process.kill("SIGTERM");
        // Force kill after 2 seconds
        setTimeout(() => {
          if (this.process && this.process.exitCode === null) {
            this.process.kill("SIGKILL");
          }
        }, 2000);
      } catch (error) {
        console.error(`[python-daemon] Error during shutdown:`, error);
      }
    }

    this.cleanup();
  }
}

// Singleton instance
let daemon: PythonDaemon | null = null;

/**
 * Call a Python function via the persistent daemon process.
 *
 * @param func Function name to call
 * @param args Arguments to pass to the function
 * @returns JSON string result from Python
 */
export async function callPythonDaemon(func: string, args: Record<string, unknown> = {}): Promise<string> {
  if (!daemon) {
    daemon = new PythonDaemon();
  }
  return daemon.call(func, args);
}

/**
 * Shutdown the Python daemon (for testing or graceful exit).
 */
export function shutdownPythonDaemon(): void {
  if (daemon) {
    daemon.shutdown();
    daemon = null;
  }
}
