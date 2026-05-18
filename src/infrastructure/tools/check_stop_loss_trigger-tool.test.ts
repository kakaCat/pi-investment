import { describe, it, expect } from "@jest/globals";
import { check_stop_loss_triggerTool } from "./check_stop_loss_trigger-tool.js";

describe("check_stop_loss_triggerTool", () => {
  it("should execute successfully with valid params", async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)("test-id", {
      symbol: "AAPL",
      entryPrice: 100,
      currentPrice: 92,
      stopLossPercent: 5,
      stopLossPrice: 94,
      highestPrice: 110,
      trailingStopPercent: 10,
    });

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.triggered).toBe(true);
    expect(result.details.status).toBe("triggered");
  });

  it("should handle invalid params gracefully", async () => {
    const result = await (check_stop_loss_triggerTool.execute as any)("test-id", {});

    expect(result.content).toBeDefined();
    expect(result.details).toBeDefined();
    expect(result.details.status).toBe("invalid_params");
    expect(result.details.triggered).toBe(false);
  });
});