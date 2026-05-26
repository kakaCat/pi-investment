// src/infrastructure/tools/agent/backend-control-tool.test.ts
import { describe, expect, jest, test, beforeEach, afterEach } from "@jest/globals";
import { existsSync, mkdirSync, rmSync, readFileSync, writeFileSync } from "fs";
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

  test("savePid creates directory and writes PID file", async () => {
    const { savePid } = await import("./backend-control-tool.js");

    savePid("rest", 12345, TEST_BACKEND_DIR);

    expect(existsSync(TEST_PID_FILE)).toBe(true);
    const data = JSON.parse(readFileSync(TEST_PID_FILE, "utf-8"));
    expect(data.rest.pid).toBe(12345);
    expect(data.rest.startTime).toBeDefined();
  });

  test("loadPids returns empty object if file does not exist", async () => {
    const { loadPids } = await import("./backend-control-tool.js");

    const pids = loadPids(TEST_BACKEND_DIR);

    expect(pids).toEqual({});
  });

  test("loadPids reads existing PID file", async () => {
    const { savePid, loadPids } = await import("./backend-control-tool.js");

    savePid("rest", 12345, TEST_BACKEND_DIR);
    savePid("websocket", 12346, TEST_BACKEND_DIR);
    const pids = loadPids(TEST_BACKEND_DIR);

    expect(pids.rest?.pid).toBe(12345);
    expect(pids.websocket?.pid).toBe(12346);
  });

  test("removePid deletes specific service entry", async () => {
    const { savePid, removePid, loadPids } = await import("./backend-control-tool.js");

    savePid("rest", 12345, TEST_BACKEND_DIR);
    savePid("websocket", 12346, TEST_BACKEND_DIR);
    removePid("rest", TEST_BACKEND_DIR);
    const pids = loadPids(TEST_BACKEND_DIR);

    expect(pids.rest).toBeUndefined();
    expect(pids.websocket?.pid).toBe(12346);
  });

  test("loadPids returns empty object for corrupted JSON file", async () => {
    const { loadPids } = await import("./backend-control-tool.js");

    // Create corrupted JSON file
    if (!existsSync(TEST_BACKEND_DIR)) {
      mkdirSync(TEST_BACKEND_DIR, { recursive: true });
    }
    writeFileSync(TEST_PID_FILE, "{ invalid json }", "utf-8");

    const pids = loadPids(TEST_BACKEND_DIR);

    expect(pids).toEqual({});
  });

  test("removePid handles non-existent service gracefully", async () => {
    const { savePid, removePid, loadPids } = await import("./backend-control-tool.js");

    savePid("rest", 12345, TEST_BACKEND_DIR);
    removePid("websocket", TEST_BACKEND_DIR); // Remove service that doesn't exist
    const pids = loadPids(TEST_BACKEND_DIR);

    expect(pids.rest?.pid).toBe(12345);
    expect(pids.websocket).toBeUndefined();
  });

  test("removePid writes empty object when removing last service", async () => {
    const { savePid, removePid, loadPids } = await import("./backend-control-tool.js");

    savePid("rest", 12345, TEST_BACKEND_DIR);
    removePid("rest", TEST_BACKEND_DIR);

    expect(existsSync(TEST_PID_FILE)).toBe(true);
    const content = readFileSync(TEST_PID_FILE, "utf-8");
    expect(content).toBe("{}");

    const pids = loadPids(TEST_BACKEND_DIR);
    expect(pids).toEqual({});
  });
});

describe("Health Check", () => {
  test("checkHealth returns true for healthy service", async () => {
    const { checkHealth } = await import("./backend-control-tool.js");

    // @ts-expect-error - Mock fetch for testing
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      // @ts-expect-error - Mock response
      json: jest.fn().mockResolvedValue({ status: "ok", db_connected: true }),
    });

    const result = await checkHealth(5001, 3000, mockFetch as any);

    expect(result.healthy).toBe(true);
    expect(result.dbConnected).toBe(true);
  });

  test("checkHealth returns false on timeout", async () => {
    const { checkHealth } = await import("./backend-control-tool.js");

    const mockFetch = jest.fn().mockImplementation(() =>
      new Promise((_, reject) => {
        setTimeout(() => reject({ name: "AbortError" }), 50);
      })
    );

    const result = await checkHealth(5001, 100, mockFetch as any);

    expect(result.healthy).toBe(false);
    expect(result.error).toContain("timeout");
  });

  test("checkHealth returns false on connection error", async () => {
    const { checkHealth } = await import("./backend-control-tool.js");

    // @ts-expect-error - Mock fetch for testing
    const mockFetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));

    const result = await checkHealth(5001, 3000, mockFetch as any);

    expect(result.healthy).toBe(false);
    expect(result.error).toContain("ECONNREFUSED");
  });
});

describe("Start Operation", () => {
  beforeEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
  });

  test("startService spawns correct command for rest service", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockJson = jest.fn() as any;
    mockJson.mockResolvedValue({ status: "ok", db_connected: true });

    const mockFetch = jest.fn() as any;
    mockFetch.mockResolvedValue({
      ok: true,
      json: mockJson,
    });

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(mockSpawn).toHaveBeenCalledWith(
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
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockJson = jest.fn() as any;
    mockJson.mockResolvedValue({ status: "ok", db_connected: true });

    const mockFetch = jest.fn() as any;
    mockFetch.mockResolvedValue({
      ok: true,
      json: mockJson,
    });

    const result = await mod.startService("all", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(mockSpawn).toHaveBeenCalledWith(
      "python",
      ["start_all.py"],
      expect.objectContaining({
        cwd: expect.stringContaining("quantsys-v2"),
      })
    );
    expect(result.success).toBe(true);
  });

  test("startService returns error if health check fails", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockFetch = jest.fn() as any;
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(false);
    expect(result.error).toContain("Health check failed");
  }, 15000);
});

describe("Stop Operation", () => {
  beforeEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
    jest.clearAllMocks();
  });

  afterEach(() => {
    if (existsSync(TEST_BACKEND_DIR)) {
      rmSync(TEST_BACKEND_DIR, { recursive: true });
    }
  });

  test("stopService sends SIGTERM to process", async () => {
    const mod = await import("./backend-control-tool.js");

    mod.savePid("rest", 12345, TEST_BACKEND_DIR);

    let processKilled = false;
    const killMock = jest.fn() as any;
    killMock.mockImplementation((pid: number, signal: any) => {
      if (signal === "SIGTERM") {
        processKilled = true;
        return;
      }
      if (signal === 0) {
        // Check if process is alive
        if (processKilled) {
          const error: any = new Error("ESRCH");
          error.code = "ESRCH";
          throw error;
        }
        return;
      }
    });
    const originalKill = process.kill;
    process.kill = killMock;

    const result = await mod.stopService("rest", TEST_BACKEND_DIR);

    expect(killMock).toHaveBeenCalledWith(12345, "SIGTERM");
    expect(result.success).toBe(true);

    process.kill = originalKill;
  });

  test("stopService returns success if process not found", async () => {
    const mod = await import("./backend-control-tool.js");

    mod.savePid("rest", 12345, TEST_BACKEND_DIR);

    const killMock = jest.fn().mockImplementation(() => {
      const error: any = new Error("ESRCH");
      error.code = "ESRCH";
      throw error;
    });
    const originalKill = process.kill;
    process.kill = killMock as any;

    const result = await mod.stopService("rest", TEST_BACKEND_DIR);

    expect(result.success).toBe(true);
    expect(result.message).toContain("stopped");

    process.kill = originalKill;
  });

  test("stopService sends SIGKILL after timeout", async () => {
    const mod = await import("./backend-control-tool.js");

    mod.savePid("rest", 12345, TEST_BACKEND_DIR);

    let killCount = 0;
    const killMock = jest.fn() as any;
    killMock.mockImplementation((pid: number, signal: any) => {
      killCount++;
      if (killCount === 1 && signal === "SIGTERM") {
        return; // Process still alive
      }
      if (signal === 0) {
        return; // Process still alive (checking)
      }
      if (signal === "SIGKILL") {
        // Process killed
        const error: any = new Error("ESRCH");
        error.code = "ESRCH";
        throw error;
      }
    });
    const originalKill = process.kill;
    process.kill = killMock;

    const result = await mod.stopService("rest", TEST_BACKEND_DIR, 100);

    expect(killMock).toHaveBeenCalledWith(12345, "SIGTERM");
    expect(killMock).toHaveBeenCalledWith(12345, "SIGKILL");

    process.kill = originalKill;
  }, 10000);
});
