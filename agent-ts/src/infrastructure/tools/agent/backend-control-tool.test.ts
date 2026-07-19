// src/infrastructure/tools/agent/backend-control-tool.test.ts
import { describe, expect, jest, test, beforeEach, afterEach } from "@jest/globals";
import { existsSync, mkdirSync, rmSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";

const TEST_BACKEND_DIR = join(process.cwd(), ".backend-test");
const TEST_PID_FILE = join(TEST_BACKEND_DIR, "pids.json");

describe("Python command resolution", () => {
  const TMP_DIR = join(process.cwd(), ".venv-resolve-test");

  beforeEach(() => {
    if (existsSync(TMP_DIR)) {
      rmSync(TMP_DIR, { recursive: true });
    }
  });

  afterEach(() => {
    if (existsSync(TMP_DIR)) {
      rmSync(TMP_DIR, { recursive: true });
    }
  });

  test("resolvePythonCommand prefers quantsysDir/venv/bin/python when it exists", async () => {
    const { resolvePythonCommand } = await import("./backend-control-tool.js");

    mkdirSync(join(TMP_DIR, "venv", "bin"), { recursive: true });
    writeFileSync(join(TMP_DIR, "venv", "bin", "python"), "");

    expect(resolvePythonCommand(TMP_DIR)).toBe(join(TMP_DIR, "venv", "bin", "python"));
  });

  test("resolvePythonCommand falls back to bare 'python' when venv is missing", async () => {
    const { resolvePythonCommand } = await import("./backend-control-tool.js");

    mkdirSync(TMP_DIR, { recursive: true });

    expect(resolvePythonCommand(TMP_DIR)).toBe("python");
  });
});

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

    const result = await checkHealth(5001, 3000, mockFetch);

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

    const result = await checkHealth(5001, 3000, mockFetch);

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

    const expectedPython = mod.resolvePythonCommand(
      join(process.cwd(), "..", "quantsys-v2")
    );
    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(mockSpawn).toHaveBeenCalledWith(
      expectedPython,
      ["adapters/inbound/api/server.py"],
      expect.objectContaining({
        cwd: expect.stringContaining("quantsys-v2"),
        detached: true,
      })
    );
    expect(result.success).toBe(true);
    expect(result.pid).toBe(12345);
  });

  test("startService spawns server.py for all services (Spring Boot style)", async () => {
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

    const expectedPythonAll = mod.resolvePythonCommand(
      join(process.cwd(), "..", "quantsys-v2")
    );
    const result = await mod.startService("all", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(mockSpawn).toHaveBeenCalledWith(
      expectedPythonAll,
      ["adapters/inbound/api/server.py"],
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
    expect(result.error).toBeDefined();
    expect(result.diagnostics).toBeDefined();
    expect(result.diagnostics?.elapsedMs).toBeGreaterThanOrEqual(15000);
  }, 20000);
});

describe("startService with staged polling", () => {
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

  test("should succeed in stage 1 for fast-starting services", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    let healthCheckCount = 0;
    const mockFetch = jest.fn().mockImplementation(() => {
      healthCheckCount++;
      if (healthCheckCount >= 2) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "ok", db_connected: true }),
        });
      }
      return Promise.reject(new Error("Connection refused"));
    });

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(true);
    expect(result.pid).toBe(12345);
    expect(healthCheckCount).toBeLessThanOrEqual(10);
  });

  test("should succeed in stage 2 for slow-starting services", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    let healthCheckCount = 0;
    const mockFetch = jest.fn().mockImplementation(() => {
      healthCheckCount++;
      if (healthCheckCount >= 15) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "ok", db_connected: true }),
        });
      }
      return Promise.reject(new Error("Connection refused"));
    });

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(true);
    expect(result.pid).toBe(12345);
  }, 20000);
});

describe("startService diagnostic errors", () => {
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

  test("should detect process crash and return logs", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockFetch = jest.fn() as any;
    mockFetch.mockRejectedValue(new Error("Connection refused"));

    const originalKill = process.kill;
    process.kill = jest.fn().mockImplementation(() => {
      const error: any = new Error("ESRCH");
      error.code = "ESRCH";
      throw error;
    }) as any;

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(false);
    expect(result.error).toContain("进程启动后崩溃");
    expect(result.diagnostics?.reason).toBe("process_crashed");
    expect(result.diagnostics?.logs).toBeDefined();

    process.kill = originalKill;
  }, 20000);

  test("should return diagnostics with reason and elapsed time on timeout", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockFetch = jest.fn() as any;
    mockFetch.mockRejectedValue(new Error("Connection refused"));

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(false);
    expect(result.diagnostics).toBeDefined();
    expect(result.diagnostics?.reason).toMatch(/process_crashed|port_conflict|health_check_timeout/);
    expect(result.diagnostics?.elapsedMs).toBeGreaterThanOrEqual(15000);
    expect(result.diagnostics?.logs).toBeDefined();
  }, 20000);

  test("should include hint in diagnostics", async () => {
    const mod = await import("./backend-control-tool.js");

    const mockSpawn = jest.fn().mockReturnValue({
      pid: 12345,
      unref: jest.fn(),
    });

    const mockFetch = jest.fn() as any;
    mockFetch.mockRejectedValue(new Error("Connection refused"));

    const result = await mod.startService("rest", TEST_BACKEND_DIR, mockSpawn as any, mockFetch);

    expect(result.success).toBe(false);
    expect(result.diagnostics).toBeDefined();
    expect(result.diagnostics?.hint).toBeDefined();
    expect(typeof result.diagnostics?.hint).toBe("string");
  }, 20000);
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

describe("Status Operation", () => {
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

  test("getServiceStatus returns running status for healthy service", async () => {
    const mod = await import("./backend-control-tool.js");

    mod.savePid("rest", 12345, TEST_BACKEND_DIR);

    const killMock = jest.fn() as any;
    const originalKill = process.kill;
    process.kill = killMock;

    const mockJson = jest.fn() as any;
    mockJson.mockResolvedValue({ status: "ok", db_connected: true });

    const mockFetch = jest.fn() as any;
    mockFetch.mockResolvedValue({
      ok: true,
      json: mockJson,
    });

    const result = await mod.getServiceStatus("rest", TEST_BACKEND_DIR, mockFetch);

    expect(result.status).toBe("running");
    expect(result.pid).toBe(12345);
    expect(result.port).toBe(5001);
    expect(result.uptime).toBeDefined();

    process.kill = originalKill;
  });

  test("getServiceStatus returns stopped if no PID file", async () => {
    const mod = await import("./backend-control-tool.js");

    const result = await mod.getServiceStatus("rest", TEST_BACKEND_DIR);

    expect(result.status).toBe("stopped");
    expect(result.pid).toBeUndefined();
  });

  test("getServiceStatus returns unhealthy if health check fails", async () => {
    const mod = await import("./backend-control-tool.js");

    mod.savePid("rest", 12345, TEST_BACKEND_DIR);

    const killMock = jest.fn() as any;
    const originalKill = process.kill;
    process.kill = killMock;

    const mockFetch = jest.fn() as any;
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

    const result = await mod.getServiceStatus("rest", TEST_BACKEND_DIR, mockFetch);

    expect(result.status).toBe("unhealthy");
    expect(result.pid).toBe(12345);

    process.kill = originalKill;
  });
});
