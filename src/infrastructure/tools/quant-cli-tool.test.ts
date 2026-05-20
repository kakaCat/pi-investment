import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<(domain: string, action: string, params?: Record<string, unknown>) => Promise<any>>();

await jest.unstable_mockModule("../quant/quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const { quantCliTool } = await import("./quant-cli-tool.js");

describe("quantCliTool", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("describes the unified CLI contract and available command examples", () => {
    expect(quantCliTool.name).toBe("quant_cli");
    expect(quantCliTool.description).toContain("统一入口");
    expect(quantCliTool.description).toContain("help");
    expect(quantCliTool.description).toContain("使用说明书");
    expect(quantCliTool.description).toContain("stock.technical");
    expect(quantCliTool.description).toContain("stock.score");
    expect(quantCliTool.description).toContain("stock.screen");
    expect(quantCliTool.description).toContain("performance.analyze");
    expect(quantCliTool.description).toContain("signal.arbitrate");
    expect(quantCliTool.description).toContain("factor.analyze");
    expect(quantCliTool.description).toContain("sector.aggregate");
    expect(quantCliTool.description).toContain("benchmark.compare");
    expect(quantCliTool.description).toContain("portfolio.optimize");
    expect(quantCliTool.description).toContain("strategy.optimize");
    expect(quantCliTool.description).toContain("watch.price_alert");
    expect(quantCliTool.description).toContain("stress.test");
    expect(quantCliTool.description).toContain("trade.verify");
    expect(quantCliTool.description).toContain("portfolio.correlation");
    expect(quantCliTool.description).toContain("factor.decay");
    expect(quantCliTool.description).toContain("signal.generate");
    expect(quantCliTool.description).toContain("不要臆造 command");
  });

  test("supports a bash-like help command for command discovery", async () => {
    runQuantCliMock.mockResolvedValueOnce({
      ok: true,
      command: "tools.list",
      data: { commands: [{ name: "stock.technical" }] },
      error: null,
    });

    await (quantCliTool.execute as any)("call-1", { command: "help" });

    expect(runQuantCliMock).toHaveBeenCalledWith("tools", "list", {});
  });

  test("supports a bash-like help command for one command manual", async () => {
    runQuantCliMock.mockResolvedValueOnce({
      ok: true,
      command: "tools.describe",
      data: { name: "stock.technical" },
      error: null,
    });

    await (quantCliTool.execute as any)("call-1", {
      command: "help",
      params: { name: "stock.technical" },
    });

    expect(runQuantCliMock).toHaveBeenCalledWith("tools", "describe", {
      name: "stock.technical",
    });
  });

  test("validates params then calls the matching QuantSys CLI command", async () => {
    runQuantCliMock.mockResolvedValueOnce({
      ok: true,
      command: "stock.technical",
      data: { symbol: "600519", indicators: { RSI: 42 } },
      error: null,
    });

    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.technical",
      params: { symbol: "600519", indicators: ["RSI", "MACD"] },
    });

    expect(runQuantCliMock).toHaveBeenCalledWith("stock", "technical", {
      symbol: "600519",
      indicators: ["RSI", "MACD"],
    });
    expect(result.content[0].text).toContain("stock.technical");
    expect(result.details.data).toEqual({ symbol: "600519", indicators: { RSI: 42 } });
  });

  test("allows stock score and screen commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({
        ok: true,
        command: "stock.score",
        data: { symbol: "600519", total_score: 82 },
        error: null,
      })
      .mockResolvedValueOnce({
        ok: true,
        command: "stock.screen",
        data: { count: 1, stocks: [{ symbol: "600519" }] },
        error: null,
      });

    await (quantCliTool.execute as any)("call-1", {
      command: "stock.score",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "stock.screen",
      params: { pe_max: 20, roe_min: 15, limit: 10, sort_by: "total_score" },
    });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "stock", "score", {
      symbol: "600519",
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "stock", "screen", {
      pe_max: 20,
      roe_min: 15,
      limit: 10,
      sort_by: "total_score",
    });
  });

  test("allows performance analyze and signal arbitrate commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({
        ok: true,
        command: "performance.analyze",
        data: { strategy_id: "rsi", total_signals: 3 },
        error: null,
      })
      .mockResolvedValueOnce({
        ok: true,
        command: "signal.arbitrate",
        data: { results: [{ symbol: "600519", decision: "BUY" }] },
        error: null,
      });

    await (quantCliTool.execute as any)("call-1", {
      command: "performance.analyze",
      params: { strategy_id: "rsi", days: 90 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "signal.arbitrate",
      params: { date: "2026-05-20", min_confidence_gap: 0.1 },
    });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "performance", "analyze", {
      strategy_id: "rsi",
      days: 90,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "signal", "arbitrate", {
      date: "2026-05-20",
      min_confidence_gap: 0.1,
    });
  });

  test("allows priority 2 analytics commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "factor.analyze", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sector.aggregate", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "benchmark.compare", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "portfolio.optimize", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "strategy.optimize", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "factor.analyze",
      params: { top_n: 10, min_observations: 5, sample_limit: 50000 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "sector.aggregate",
      params: { sector_field: "industry", limit: 10 },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "benchmark.compare",
      params: { strategy_return: 0.12, benchmark_return: 0.08 },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "portfolio.optimize",
      params: { symbols: "600519,000001", method: "risk_parity" },
    });
    await (quantCliTool.execute as any)("call-5", {
      command: "strategy.optimize",
      params: { strategy: "rsi", metric: "sharpe", trials: 9 },
    });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "factor", "analyze", {
      top_n: 10,
      min_observations: 5,
      sample_limit: 50000,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "sector", "aggregate", {
      sector_field: "industry",
      limit: 10,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "benchmark", "compare", {
      strategy_return: 0.12,
      benchmark_return: 0.08,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "portfolio", "optimize", {
      symbols: "600519,000001",
      method: "risk_parity",
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "strategy", "optimize", {
      strategy: "rsi",
      metric: "sharpe",
      trials: 9,
    });
  });

  test("allows priority 3 ecosystem commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "watch.price_alert", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stress.test", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "trade.verify", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "portfolio.correlation", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "factor.decay", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "watch.price_alert",
      params: { symbol: "600519", price: 105, above: 100 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "stress.test",
      params: { positions_json: "[{\"symbol\":\"600519\",\"market_value\":10000}]", shock_pct: -0.2 },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "trade.verify",
      params: { trades_json: "[]", backtest_json: "[]" },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "portfolio.correlation",
      params: { prices_json: "{\"600519\":[1,2,3],\"000001\":[1,2,4]}", threshold: 0.7 },
    });
    await (quantCliTool.execute as any)("call-5", {
      command: "factor.decay",
      params: { factor: "momentum", horizons: "5,10,20" },
    });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "watch", "price-alert", {
      symbol: "600519",
      price: 105,
      above: 100,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "stress", "test", {
      positions_json: "[{\"symbol\":\"600519\",\"market_value\":10000}]",
      shock_pct: -0.2,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "trade", "verify", {
      trades_json: "[]",
      backtest_json: "[]",
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "portfolio", "correlation", {
      prices_json: "{\"600519\":[1,2,3],\"000001\":[1,2,4]}",
      threshold: 0.7,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "factor", "decay", {
      factor: "momentum",
      horizons: "5,10,20",
    });
  });

  test("rejects unknown commands before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.magic",
      params: { symbol: "600519" },
    });

    expect(runQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的量化命令");
    expect(result.content[0].text).toContain("tools.list");
  });

  test("rejects missing required params before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.klines",
      params: { limit: 10 },
    });

    expect(runQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("缺少必填参数");
    expect(result.content[0].text).toContain("symbol");
  });

  test("rejects unknown params before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "signal.list",
      params: { signal_type: "BUY", unexpected: true },
    });

    expect(runQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的参数");
    expect(result.content[0].text).toContain("unexpected");
  });

  test("rejects invalid enum and numeric values before calling the CLI", async () => {
    const invalidSignal = await (quantCliTool.execute as any)("call-1", {
      command: "signal.list",
      params: { signal_type: "HOLD" },
    });
    const invalidLimit = await (quantCliTool.execute as any)("call-2", {
      command: "stock.klines",
      params: { symbol: "600519", limit: 0 },
    });

    expect(runQuantCliMock).not.toHaveBeenCalled();
    expect(invalidSignal.content[0].text).toContain("signal_type");
    expect(invalidSignal.content[0].text).toContain("BUY 或 SELL");
    expect(invalidLimit.content[0].text).toContain("limit");
    expect(invalidLimit.content[0].text).toContain("正数");
  });
});
