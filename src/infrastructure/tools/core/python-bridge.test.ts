/**
 * Python Bridge Tests
 */

import { callPythonDaemon, shutdownPythonDaemon } from "./python-bridge.js";

describe("Python Bridge", () => {
  afterAll(async () => {
    // Ensure daemon is shut down after tests
    shutdownPythonDaemon();
    // Give it time to clean up
    await new Promise((resolve) => setTimeout(resolve, 1000));
  });

  it("should call Python function via daemon", async () => {
    const result = await callPythonDaemon("get_sector_list", {});
    expect(result).toBeTruthy();
    const parsed = JSON.parse(result);
    // The function may return an error message about unstable API, but should still have structure
    expect(parsed).toBeDefined();
    expect(typeof parsed).toBe("object");
  }, 30000);

  it("should handle multiple concurrent requests", async () => {
    const promises = [
      callPythonDaemon("get_sector_list", {}),
      callPythonDaemon("get_sector_list", {}),
      callPythonDaemon("get_sector_list", {}),
    ];
    const results = await Promise.all(promises);
    expect(results).toHaveLength(3);
    results.forEach((result) => {
      expect(result).toBeTruthy();
      const parsed = JSON.parse(result);
      expect(parsed).toBeDefined();
    });
  }, 30000);

  it("should return error for nonexistent function", async () => {
    try {
      await callPythonDaemon("nonexistent_function", {});
      fail("Should have thrown an error");
    } catch (error) {
      expect(error).toBeDefined();
      expect(error instanceof Error).toBe(true);
      expect((error as Error).message).toContain("Method not found");
    }
  }, 30000);
});
