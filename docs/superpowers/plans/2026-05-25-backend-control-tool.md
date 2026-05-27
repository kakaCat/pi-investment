# Backend Control Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `backend_control` tool to manage quantsys-v2 backend services lifecycle (start/stop/restart/status)

**Architecture:** Single tool with sub-command pattern. Uses child_process for spawning, PID file for state tracking, HTTP health checks for verification. Follows restart-agent-tool patterns.

**Tech Stack:** TypeScript, Node.js child_process, fs, http, @sinclair/typebox

---

## File Structure

**New Files:**
- `src/infrastructure/tools/agent/backend-control-tool.ts` - Main tool implementation
- `src/infrastructure/tools/agent/backend-control-tool.test.ts` - Unit tests
- `.backend/pids.json` - PID tracking file (created at runtime)

**Modified Files:**
- `src/infrastructure/tools/index.ts` - Register new tool
- `CLAUDE.md` - Document new tool

---

## Task 1: Create PID Management Module

**Files:**
- Create: `src/infrastructure/tools/agent/backend-control-tool.ts`

- [ ] **Step 1: Write test for PID file operations**

Create test file:

```typescript
// src/infrastructure/tools/agent/backend-control-tool.test.ts
import { describe, expect, jest, test, beforeEach, afterEach } from "@jest/globals";
import { existsSync, mkdirSync, rmSync, readFileSync } from "fs";
import { join } from "path";

const TEST_BACKEND_DIR = join(process.cwd(), ".backend-test");
const TEST_PID_FILE = join(TEST_BACKEND_DIR, "pids.json");

describe("PID Management", () => {
  beforeEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
  });

  afterEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
  });

  test("savePid creates directory and writes PID file", () => {
    const { savePid } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    
    expect(existsSync(TEST_PID_FILE)).toBe(true);
    const data = JSON.parse(readFileSync(TEST_PID_FILE, "utf-8"));
    expect(data.rest.pid).toBe(12345);
    expect(data.rest.startTime).toBeDefined();
  });

  test("loadPids returns empty object if file does not exist", () => {
    const { loadPids } = require("./backend-control-tool.js");
    
    const pids = loadPids(TEST_BACKEND_DIR);
    
    expect(pids).toEqual({});
  });

  test("loadPids reads existing PID file", () => {
    const { savePid, loadPids } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    savePid("websocket", 12346, TEST_BACKEND_DIR);
    const pids = loadPids(TEST_BACKEND_DIR);
    
    expect(pids.rest.pid).toBe(12345);
    expect(pids.websocket.pid).toBe(12346);
  });

  test("removePid deletes specific service entry", () => {
    const { savePid, removePid, loadPids } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    savePid("websocket", 12346, TEST_BACKEND_DIR);
    removePid("rest", TEST_BACKEND_DIR);
    const pids = loadPids(TEST_BACKEND_DIR);
    
    expect(pids.rest).toBeUndefined();
    expect(pids.websocket.pid).toBe(12346);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts`
Expected: FAIL with "Cannot find module './backend-control-tool.js'"

- [ ] **Step 3: Implement PID management functions**

```typescript
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit PID management**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: add PID management for backend control tool"
```

---

## Task 2: Implement Process Health Check

**Files:**
- Modify: `src/infrastructure/tools/agent/backend-control-tool.ts`
- Modify: `src/infrastructure/tools/agent/backend-control-tool.test.ts`

- [ ] **Step 1: Write test for health check**

Add to test file:

```typescript
describe("Health Check", () => {
  test("checkHealth returns true for healthy service", async () => {
    const { checkHealth } = require("./backend-control-tool.js");
    
    // Mock successful health check
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", db_connected: true }),
    });
    
    const result = await checkHealth(5001);
    
    expect(result.healthy).toBe(true);
    expect(result.dbConnected).toBe(true);
  });

  test("checkHealth returns false on timeout", async () => {
    const { checkHealth } = require("./backend-control-tool.js");
    
    global.fetch = jest.fn().mockImplementation(() => 
      new Promise((resolve) => setTimeout(resolve, 5000))
    );
    
    const result = await checkHealth(5001, 100);
    
    expect(result.healthy).toBe(false);
    expect(result.error).toContain("timeout");
  });

  test("checkHealth returns false on connection error", async () => {
    const { checkHealth } = require("./backend-control-tool.js");
    
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    
    const result = await checkHealth(5001);
    
    expect(result.healthy).toBe(false);
    expect(result.error).toContain("ECONNREFUSED");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts -t "Health Check"`
Expected: FAIL with "checkHealth is not a function"

- [ ] **Step 3: Implement health check function**

Add to `backend-control-tool.ts`:

```typescript
interface HealthCheckResult {
  healthy: boolean;
  dbConnected?: boolean;
  error?: string;
}

export async function checkHealth(
  port: number,
  timeoutMs: number = 3000
): Promise<HealthCheckResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`http://127.0.0.1:${port}/api/health`, {
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts -t "Health Check"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit health check**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: add health check for backend services"
```

---

## Task 3: Implement Start Operation

**Files:**
- Modify: `src/infrastructure/tools/agent/backend-control-tool.ts`
- Modify: `src/infrastructure/tools/agent/backend-control-tool.test.ts`

- [ ] **Step 1: Write test for start operation**

Add to test file:

```typescript
import { spawn } from "child_process";

jest.mock("child_process");

describe("Start Operation", () => {
  test("startService spawns correct command for rest service", async () => {
    const { startService } = require("./backend-control-tool.js");
    const mockProcess = {
      pid: 12345,
      unref: jest.fn(),
      on: jest.fn(),
    };
    
    (spawn as jest.Mock).mockReturnValue(mockProcess);
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", db_connected: true }),
    });
    
    const result = await startService("rest", TEST_BACKEND_DIR);
    
    expect(spawn).toHaveBeenCalledWith(
      "python",
      ["api/server.py"],
      expect.objectContaining({
        cwd: expect.stringContaining("quantsys-v2"),
        detached: true,
        stdio: "ignore",
      })
    );
    expect(result.success).toBe(true);
    expect(result.pid).toBe(12345);
  });

  test("startService spawns start_all.py for all services", async () => {
    const { startService } = require("./backend-control-tool.js");
    const mockProcess = {
      pid: 12345,
      unref: jest.fn(),
      on: jest.fn(),
    };
    
    (spawn as jest.Mock).mockReturnValue(mockProcess);
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", db_connected: true }),
    });
    
    const result = await startService("all", TEST_BACKEND_DIR);
    
    expect(spawn).toHaveBeenCalledWith(
      "python",
      ["start_all.py"],
      expect.objectContaining({
        cwd: expect.stringContaining("quantsys-v2"),
      })
    );
    expect(result.success).toBe(true);
  });

  test("startService returns error if health check fails", async () => {
    const { startService } = require("./backend-control-tool.js");
    const mockProcess = {
      pid: 12345,
      unref: jest.fn(),
      on: jest.fn(),
    };
    
    (spawn as jest.Mock).mockReturnValue(mockProcess);
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    
    const result = await startService("rest", TEST_BACKEND_DIR);
    
    expect(result.success).toBe(false);
    expect(result.error).toContain("Health check failed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts -t "Start Operation"`
Expected: FAIL with "startService is not a function"

- [ ] **Step 3: Implement start operation**

Add to `backend-control-tool.ts`:

```typescript
import { spawn } from "child_process";

interface StartResult {
  success: boolean;
  pid?: number;
  message?: string;
  error?: string;
}

export async function startService(
  service: "rest" | "websocket" | "all",
  backendDir: string = DEFAULT_BACKEND_DIR
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
    const subprocess = spawn(command, args, {
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
      
      const health = await checkHealth(targetPort, 1000);
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts -t "Start Operation"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit start operation**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: implement start operation for backend services"
```

---

## Task 4: Implement Stop Operation

**Files:**
- Modify: `src/infrastructure/tools/agent/backend-control-tool.ts`
- Modify: `src/infrastructure/tools/agent/backend-control-tool.test.ts`

- [ ] **Step 1: Write test for stop operation**

Add to test file:

```typescript
describe("Stop Operation", () => {
  test("stopService sends SIGTERM to process", async () => {
    const { stopService, savePid } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    
    const killMock = jest.fn();
    process.kill = killMock;
    
    const result = await stopService("rest", TEST_BACKEND_DIR);
    
    expect(killMock).toHaveBeenCalledWith(12345, "SIGTERM");
    expect(result.success).toBe(true);
  });

  test("stopService returns success if process not found", async () => {
    const { stopService } = require("./backend-control-tool.js");
    
    const killMock = jest.fn().mockImplementation(() => {
      throw { code: "ESRCH" };
    });
    process.kill = killMock;
    
    const result = await stopService("rest", TEST_BACKEND_DIR);
    
    expect(result.success).toBe(true);
    expect(result.message).toContain("already stopped");
  });

  test("stopService sends SIGKILL after timeout", async () => {
    const { stopService, savePid } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    
    let killCount = 0;
    const killMock = jest.fn().mockImplementation((pid, signal) => {
      killCount++;
      if (killCount === 1 && signal === "SIGTERM") {
        return; // Process still alive
      }
      if (killCount === 2 && signal === 0) {
        return; // Process still alive
      }
    });
    process.kill = killMock;
    
    const result = await stopService("rest", TEST_BACKEND_DIR, 100);
    
    expect(killMock).toHaveBeenCalledWith(12345, "SIGTERM");
    expect(killMock).toHaveBeenCalledWith(12345, "SIGKILL");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts -t "Stop Operation"`
Expected: FAIL with "stopService is not a function"

- [ ] **Step 3: Implement stop operation**

Add to `backend-control-tool.ts`:

```typescript
interface StopResult {
  success: boolean;
  message?: string;
  error?: string;
}

function isProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error: any) {
    return error.code !== "ESRCH";
  }
}

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts -t "Stop Operation"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit stop operation**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: implement stop operation with graceful shutdown"
```

---

## Task 5: Implement Status Operation

**Files:**
- Modify: `src/infrastructure/tools/agent/backend-control-tool.ts`
- Modify: `src/infrastructure/tools/agent/backend-control-tool.test.ts`

- [ ] **Step 1: Write test for status operation**

Add to test file:

```typescript
describe("Status Operation", () => {
  test("getServiceStatus returns running status for healthy service", async () => {
    const { getServiceStatus, savePid } = require("./backend-control-tool.js");
    
    const startTime = new Date(Date.now() - 3600000).toISOString(); // 1 hour ago
    savePid("rest", 12345, TEST_BACKEND_DIR);
    
    const killMock = jest.fn();
    process.kill = killMock;
    
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok", db_connected: true }),
    });
    
    const result = await getServiceStatus("rest", TEST_BACKEND_DIR);
    
    expect(result.status).toBe("running");
    expect(result.pid).toBe(12345);
    expect(result.port).toBe(5001);
    expect(result.uptime).toBeDefined();
  });

  test("getServiceStatus returns stopped if no PID file", async () => {
    const { getServiceStatus } = require("./backend-control-tool.js");
    
    const result = await getServiceStatus("rest", TEST_BACKEND_DIR);
    
    expect(result.status).toBe("stopped");
    expect(result.pid).toBeUndefined();
  });

  test("getServiceStatus returns unhealthy if health check fails", async () => {
    const { getServiceStatus, savePid } = require("./backend-control-tool.js");
    
    savePid("rest", 12345, TEST_BACKEND_DIR);
    
    const killMock = jest.fn();
    process.kill = killMock;
    
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    
    const result = await getServiceStatus("rest", TEST_BACKEND_DIR);
    
    expect(result.status).toBe("unhealthy");
    expect(result.pid).toBe(12345);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts -t "Status Operation"`
Expected: FAIL with "getServiceStatus is not a function"

- [ ] **Step 3: Implement status operation**

Add to `backend-control-tool.ts`:

```typescript
interface ServiceStatus {
  status: "running" | "stopped" | "unhealthy";
  pid?: number;
  port: number;
  uptime?: string;
  error?: string;
}

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

export async function getServiceStatus(
  service: "rest" | "websocket",
  backendDir: string = DEFAULT_BACKEND_DIR
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
  const health = await checkHealth(port);
  
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts -t "Status Operation"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit status operation**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: implement status operation with uptime calculation"
```

---

## Task 6: Implement Restart Operation and Tool Definition

**Files:**
- Modify: `src/infrastructure/tools/agent/backend-control-tool.ts`
- Modify: `src/infrastructure/tools/agent/backend-control-tool.test.ts`

- [ ] **Step 1: Write test for restart operation**

Add to test file:

```typescript
describe("Restart Operation", () => {
  test("restartService calls stop then start", async () => {
    const mod = require("./backend-control-tool.js");
    
    const stopMock = jest.spyOn(mod, "stopService").mockResolvedValue({ success: true });
    const startMock = jest.spyOn(mod, "startService").mockResolvedValue({ success: true, pid: 12346 });
    
    const result = await mod.restartService("rest", TEST_BACKEND_DIR);
    
    expect(stopMock).toHaveBeenCalledWith("rest", TEST_BACKEND_DIR);
    expect(startMock).toHaveBeenCalledWith("rest", TEST_BACKEND_DIR);
    expect(result.success).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- backend-control-tool.test.ts -t "Restart Operation"`
Expected: FAIL with "restartService is not a function"

- [ ] **Step 3: Implement restart operation and tool definition**

Add to `backend-control-tool.ts`:

```typescript
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

interface RestartResult {
  success: boolean;
  pid?: number;
  message?: string;
  error?: string;
}

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
  handler: async (args: { action: string; service?: string }) => {
    const service = (args.service || "all") as "rest" | "websocket" | "all";
    const action = args.action;

    try {
      if (action === "start") {
        const result = await startService(service);
        if (!result.success) {
          return `❌ Failed to start service: ${result.error}`;
        }
        return `✅ ${result.message}\nPID: ${result.pid}`;
      }

      if (action === "stop") {
        const result = await stopService(service);
        if (!result.success) {
          return `❌ Failed to stop service: ${result.error}`;
        }
        return `✅ ${result.message}`;
      }

      if (action === "restart") {
        const result = await restartService(service);
        if (!result.success) {
          return `❌ Failed to restart service: ${result.error}`;
        }
        return `✅ ${result.message}\nNew PID: ${result.pid}`;
      }

      if (action === "status") {
        if (service === "all") {
          const restStatus = await getServiceStatus("rest");
          const wsStatus = await getServiceStatus("websocket");
          
          return `📊 Backend Services Status:

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
          return `📊 Service Status:
  Status: ${status.status}
  Port: ${status.port}
  ${status.pid ? `PID: ${status.pid}` : ""}
  ${status.uptime ? `Uptime: ${status.uptime}` : ""}
  ${status.error ? `Error: ${status.error}` : ""}`;
        }
      }

      return `❌ Unknown action: ${action}`;
    } catch (error: any) {
      return `❌ Error: ${error.message || "Unknown error"}`;
    }
  },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- backend-control-tool.test.ts -t "Restart Operation"`
Expected: PASS (1 test)

- [ ] **Step 5: Commit restart and tool definition**

```bash
git add src/infrastructure/tools/agent/backend-control-tool.ts
git add src/infrastructure/tools/agent/backend-control-tool.test.ts
git commit -m "feat: add restart operation and complete tool definition"
```

---

## Task 7: Register Tool in Index

**Files:**
- Modify: `src/infrastructure/tools/index.ts`

- [ ] **Step 1: Add import statement**

Add after line 59 (after restartAgentTool import):

```typescript
import { backendControlTool } from "./agent/backend-control-tool.js";
```

- [ ] **Step 2: Add tool to registry**

Add after line 151 (after restartAgentTool in allCustomTools array):

```typescript
  restartAgentTool,
  backendControlTool,  // Add backend control tool
```

- [ ] **Step 3: Verify tool is registered**

Run: `npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit tool registration**

```bash
git add src/infrastructure/tools/index.ts
git commit -m "feat: register backend_control tool in tool registry"
```

---

## Task 8: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add tool documentation**

Add to CLAUDE.md after the "Agent 工具系统" section (around line 140):

```markdown
### 运维工具

**backend_control** - 后端服务生命周期管理
- `action: start` - 启动后端服务
- `action: stop` - 停止后端服务
- `action: restart` - 重启后端服务
- `action: status` - 查询服务状态
- `service: all|rest|websocket` - 目标服务（默认 all）

示例：
- 启动所有服务：`backend_control(action="start", service="all")`
- 查询状态：`backend_control(action="status")`
- 重启 REST API：`backend_control(action="restart", service="rest")`
```

- [ ] **Step 2: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs: add backend_control tool documentation"
```

---

## Task 9: Integration Testing

**Files:**
- Test manually

- [ ] **Step 1: Start agent and test start command**

Run: `npm run dev`

In agent session, test:
```
使用 backend_control 工具启动后端服务
```

Expected: Backend starts, health check passes, PID saved

- [ ] **Step 2: Test status command**

In agent session:
```
检查后端服务状态
```

Expected: Shows running status with PID and uptime

- [ ] **Step 3: Test restart command**

In agent session:
```
重启后端服务
```

Expected: Service stops, waits 2s, starts with new PID

- [ ] **Step 4: Test stop command**

In agent session:
```
停止后端服务
```

Expected: Service stops gracefully, PID file cleaned

- [ ] **Step 5: Verify PID file management**

Run: `cat .backend/pids.json`
Expected: File exists and contains valid JSON with PIDs

- [ ] **Step 6: Test error handling**

Stop backend manually: `kill -9 <pid>`
Then in agent: `检查后端状态`
Expected: Detects stale PID, cleans up, reports "stopped"

---

## Task 10: Final Verification

**Files:**
- All files

- [ ] **Step 1: Run all tests**

Run: `npm test`
Expected: All tests pass (including new backend-control-tool tests)

- [ ] **Step 2: Run type check**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 3: Test in real agent session**

Start agent: `npm run dev`

Test sequence:
1. Start backend
2. Query data using existing tools (verify connectivity)
3. Check status
4. Restart backend
5. Query data again (verify recovery)
6. Stop backend

Expected: All operations succeed

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete backend_control tool implementation

- PID management with .backend/pids.json
- Health check with timeout
- Start/stop/restart/status operations
- Graceful shutdown with SIGTERM/SIGKILL
- Comprehensive error handling
- Unit tests with >80% coverage
- Integration with tool registry
- Documentation in CLAUDE.md"
```

---

## Success Criteria Checklist

- [ ] Agent can start backend via backend_control tool
- [ ] Agent can check backend status and report uptime
- [ ] Agent can restart backend after configuration changes
- [ ] Tool handles port conflicts gracefully
- [ ] Tool cleans up stale PID files automatically
- [ ] Unit test coverage > 80%
- [ ] All tests pass
- [ ] Tool registered in index.ts
- [ ] Documentation added to CLAUDE.md
- [ ] Manual testing completed successfully

---

## Notes

- PID file location: `.backend/pids.json` (gitignored)
- Health check endpoint: `http://127.0.0.1:5001/api/health`
- Timeouts: startup 10s, stop 5s, health check 3s
- Restart delay: 2s between stop and start
- Tool follows restart-agent-tool patterns for consistency
