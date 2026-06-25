import { describe, it, expect } from "@jest/globals";
import { new_toolTool } from "./new_tool-tool.js";

describe("new_toolTool", () => {
  it("should execute successfully with valid params", async () => {
    const result = await (new_toolTool.execute as any)("test-id", {
      input: "测试参数",
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.content[0].type).toBe("text");
    expect(result.details.success).toBe(true);
  });

  it("should handle invalid params gracefully", async () => {
    const result = await (new_toolTool.execute as any)("test-id", {});

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.content[0].text).toBe("结果文本");
  });
});