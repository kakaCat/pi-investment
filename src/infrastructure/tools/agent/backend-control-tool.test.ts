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
