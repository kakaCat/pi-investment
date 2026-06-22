import { describe, it, expect } from "@jest/globals";
import { test_toolTool } from "./test_tool-tool.js";

describe("test_toolTool", () => {
  it("should execute successfully with valid params", async () => {
    const result = await (test_toolTool.execute as any)("test-id", {
      input: "hello",
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe("text");
    expect(result.details).toBeDefined();
    expect(result.details.success).toBe(true);
  });

  it("should handle invalid params gracefully", async () => {
    const result = await (test_toolTool.execute as any)("test-id", {});

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe("text");
    expect(result.details).toBeDefined();
  });
});