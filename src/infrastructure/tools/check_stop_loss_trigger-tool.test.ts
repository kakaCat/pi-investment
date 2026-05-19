import { describe, it, expect } from "@jest/globals";
import { check_stop_loss_triggerTool } from "./check_stop_loss_trigger-tool.js";

describe("check_stop_loss_triggerTool", () => {
  it("should execute successfully with valid params", async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)("test-id", {
      symbol: "AAPL",
      currentPrice: 91,
      costPrice: 100,
      stopLossPct: 8,
      quantity: 10,
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.triggered).toBe(true);
    expect(result.details.stopLossPrice).toBe(92);
  });

  it("should handle invalid params gracefully", async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)("test-id", {});
    expect(result.content).toBeDefined();
    expect(result.content[0].text).toContain("止损检查失败");
  });
});