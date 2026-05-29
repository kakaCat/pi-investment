import { describe, expect, jest, test, beforeEach } from "@jest/globals";
import { mkdtempSync, readFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const runQuantV2Mock = jest.fn<(command: string, params?: Record<string, unknown>) => Promise<any>>();

await jest.unstable_mockModule("../../quant/quant-v2-client.js", () => ({
  runQuantV2: runQuantV2Mock,
  V2_COMMAND_LIST: [],
}));

const { quantCliTool } = await import("./quant-cli-tool.js");
const { setSessionDataDir } = await import("../shared/session-utils.js");

describe("quantCliTool", () => {
  beforeEach(() => {
    runQuantV2Mock.mockReset();
  });

  test("describes the unified CLI contract and available command examples", () => {
    expect(quantCliTool.name).toBe("quant_cli");
    expect(quantCliTool.description).toContain("统一入口");
    expect(quantCliTool.description).toContain("help");
    expect(quantCliTool.description).toContain("使用说明书");
    expect(quantCliTool.description).toContain("stock.technical");
    expect(quantCliTool.description).toContain("stock.quote");
    expect(quantCliTool.description).toContain("stock.batch_quotes");
    expect(quantCliTool.description).toContain("stock.list");
    expect(quantCliTool.description).toContain("stock.info");
    expect(quantCliTool.description).toContain("market.overview");
    expect(quantCliTool.description).toContain("market.index_history");
    expect(quantCliTool.description).toContain("market.macro");
    expect(quantCliTool.description).toContain("analysis.technical");
    expect(quantCliTool.description).toContain("analysis.buy_range");
    expect(quantCliTool.description).toContain("analysis.peers");
    expect(quantCliTool.description).toContain("screening.sector");
    expect(quantCliTool.description).toContain("screening.quality");
    expect(quantCliTool.description).toContain("risk.trade_check");
    expect(quantCliTool.description).toContain("risk.position_size");
    expect(quantCliTool.description).toContain("risk.stop_loss");
    expect(quantCliTool.description).toContain("hk.market_overview");
    expect(quantCliTool.description).toContain("hk.technical");
    expect(quantCliTool.description).toContain("sentiment.stock_fund_flow");
    expect(quantCliTool.description).toContain("sentiment.margin_data");
    expect(quantCliTool.description).toContain("financial.indicators");
    expect(quantCliTool.description).toContain("financial.hk_analysis");
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
    runQuantV2Mock.mockResolvedValueOnce({
      ok: true,
      command: "tools.list",
      data: { commands: [{ name: "stock.technical" }] },
      error: null,
    });

    await (quantCliTool.execute as any)("call-1", { command: "help" });

    expect(runQuantV2Mock).toHaveBeenCalledWith("tools.list", {});
  });

  test("supports a bash-like help command for one command manual", async () => {
    runQuantV2Mock.mockResolvedValueOnce({
      ok: true,
      command: "tools.describe",
      data: { name: "stock.technical" },
      error: null,
    });

    await (quantCliTool.execute as any)("call-1", {
      command: "help",
      params: { name: "stock.technical" },
    });

    expect(runQuantV2Mock).toHaveBeenCalledWith("tools.describe", {
      name: "stock.technical",
    });
  });

  test("validates params then calls the matching QuantSys CLI command", async () => {
    runQuantV2Mock.mockResolvedValueOnce({
      ok: true,
      command: "stock.technical",
      data: { symbol: "600519", indicators: { RSI: 42 } },
      error: null,
    });

    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.technical",
      params: { symbol: "600519", indicators: ["RSI", "MACD"] },
    });

    expect(runQuantV2Mock).toHaveBeenCalledWith("stock.technical", {
      symbol: "600519",
      indicators: ["RSI", "MACD"],
    });
    expect(result.content[0].text).toContain("stock.technical");
    expect(result.details.data).toEqual({ symbol: "600519", indicators: { RSI: 42 } });
  });

  test("stores oversized command output in a local artifact and returns a summary", async () => {
    const dir = mkdtempSync(join(tmpdir(), "pi-tool-artifacts-"));
    setSessionDataDir(dir);
    const largeLog = "类别分布: " + "x".repeat(140_000);
    runQuantV2Mock.mockResolvedValueOnce({
      ok: true,
      command: "data.full_status",
      data: {
        pipeline: {
          latestRuns: [{ logs: [largeLog] }],
        },
      },
      error: null,
    });

    try {
      const result = await (quantCliTool.execute as any)("call-large", {
        command: "data.full_status",
      });

      const text = result.content[0].text;
      expect(text.length).toBeLessThan(20_000);
      expect(text).toContain("完整结果已保存到");
      expect(text).toContain("使用 read 工具查看完整内容");
      expect(text).not.toContain("x".repeat(50_000));

      const filePath = text.match(/完整结果已保存到: (.+\.json)/)?.[1];
      expect(filePath).toBeTruthy();
      const saved = readFileSync(filePath!, "utf-8");
      expect(saved).toContain(largeLog);
      expect(result.details.data.pipeline.latestRuns[0].logs[0]).toBe(largeLog);
    } finally {
      rmSync(dir, { recursive: true, force: true });
      setSessionDataDir("/tmp");
    }
  });

  test("allows stock score and screen commands", async () => {
    runQuantV2Mock
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

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "stock.score", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "stock.screen", {
      pe_max: 20,
      roe_min: 15,
      limit: 10,
      sort_by: "total_score",
    });
  });

  test("allows stock query compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "stock.quote", data: { price: 100.5 }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.info", data: { symbol: "600519" }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.history", data: { count: 30 }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.news", data: { count: 5 }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.announcements", data: { count: 1 }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.batch_quotes", data: { prices: { "600519": 100.5 } }, error: null })
      .mockResolvedValueOnce({ ok: true, command: "stock.list", data: { stocks: [{ symbol: "600519" }] }, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "stock.quote",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "stock.info",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "stock.history",
      params: { symbol: "600519", period: "daily", limit: 30 },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "stock.news",
      params: { symbol: "600519", num: 5 },
    });
    await (quantCliTool.execute as any)("call-5", {
      command: "stock.announcements",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-6", {
      command: "stock.batch_quotes",
      params: { symbols: ["600519", "000001"] },
    });
    await (quantCliTool.execute as any)("call-7", {
      command: "stock.list",
      params: { market: "A", source: "live" },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "stock.quote", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "stock.info", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "stock.history", {
      symbol: "600519",
      period: "daily",
      limit: 30,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "stock.news", {
      symbol: "600519",
      num: 5,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "stock.announcements", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(6, "stock.batch_quotes", {
      symbols: ["600519", "000001"],
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(7, "stock.list", {
      market: "A",
      source: "live",
    });
  });

  test("allows market query compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "market.overview", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.sectors", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.concept_stocks", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.concepts", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.macro", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.north_flow", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.sector_flow", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.margin", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.news", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.hot_stocks", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "market.index_history", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", { command: "market.overview" });
    await (quantCliTool.execute as any)("call-2", { command: "market.sectors" });
    await (quantCliTool.execute as any)("call-3", {
      command: "market.concept_stocks",
      params: { concept: "人工智能" },
    });
    await (quantCliTool.execute as any)("call-4", { command: "market.concepts" });
    await (quantCliTool.execute as any)("call-5", {
      command: "market.macro",
      params: { indicators: ["pmi", "cpi"] },
    });
    await (quantCliTool.execute as any)("call-6", { command: "market.north_flow" });
    await (quantCliTool.execute as any)("call-7", { command: "market.sector_flow" });
    await (quantCliTool.execute as any)("call-8", { command: "market.margin" });
    await (quantCliTool.execute as any)("call-9", {
      command: "market.news",
      params: { num: 9 },
    });
    await (quantCliTool.execute as any)("call-10", {
      command: "market.hot_stocks",
      params: { market: "港股" },
    });
    await (quantCliTool.execute as any)("call-11", {
      command: "market.index_history",
      params: { symbol: "sh000001", start_date: "2026-01-01", end_date: "2026-05-20" },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "market.overview", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "market.sectors", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "market.concept_stocks", {
      concept: "人工智能",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "market.concepts", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "market.macro", {
      indicators: ["pmi", "cpi"],
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(6, "market.north_flow", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(7, "market.sector_flow", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(8, "market.margin", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(9, "market.news", { num: 9 });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(10, "market.hot_stocks", {
      market: "港股",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(11, "market.index_history", {
      symbol: "sh000001",
      start_date: "2026-01-01",
      end_date: "2026-05-20",
    });
  });

  test("allows analysis compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "analysis.technical", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.price_action", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.candlestick", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.buy_range", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.valuation", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.pe_percentile", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.quality", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.exit_plan", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "analysis.peers", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "analysis.technical",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "analysis.price_action",
      params: { symbol: "600519", period: 80 },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "analysis.candlestick",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "analysis.buy_range",
      params: { symbol: "600519", current_price: 100.5 },
    });
    await (quantCliTool.execute as any)("call-5", {
      command: "analysis.valuation",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-6", {
      command: "analysis.pe_percentile",
      params: { symbol: "600519", years: 3 },
    });
    await (quantCliTool.execute as any)("call-7", {
      command: "analysis.quality",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-8", {
      command: "analysis.exit_plan",
      params: { symbol: "600519", entry_price: 90, position_size: 200 },
    });
    await (quantCliTool.execute as any)("call-9", {
      command: "analysis.peers",
      params: { symbol: "600519" },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "analysis.technical", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "analysis.price_action", {
      symbol: "600519",
      period: 80,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "analysis.candlestick", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "analysis.buy_range", {
      symbol: "600519",
      current_price: 100.5,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "analysis.valuation", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(6, "analysis.pe_percentile", {
      symbol: "600519",
      years: 3,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(7, "analysis.quality", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(8, "analysis.exit_plan", {
      symbol: "600519",
      entry_price: 90,
      position_size: 200,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(9, "analysis.peers", {
      symbol: "600519",
    });
  });

  test("allows screening compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "screening.sector", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "screening.quality", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "screening.sector",
      params: { sector: "白酒", min_roe: 15, max_pe: 30, limit: 8 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "screening.quality",
      params: { sector: "白酒", min_score: 65, max_pe: 30, limit: 5 },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "screening.sector", {
      sector: "白酒",
      min_roe: 15,
      max_pe: 30,
      limit: 8,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "screening.quality", {
      sector: "白酒",
      min_score: 65,
      max_pe: 30,
      limit: 5,
    });
  });

  test("allows risk compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "risk.trade_check", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "risk.position_size", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "risk.stop_loss", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "risk.trade_check",
      params: { symbol: "600519", action: "buy", price: 100.5, shares: 300 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "risk.position_size",
      params: { symbol: "600519", price: 100.5, signal_strength: 0.8 },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "risk.stop_loss",
      params: { symbol: "600519", entry_price: 90, current_price: 100, highest_price: 110 },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "risk.trade_check", {
      symbol: "600519",
      action: "buy",
      price: 100.5,
      shares: 300,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "risk.position_size", {
      symbol: "600519",
      price: 100.5,
      signal_strength: 0.8,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "risk.stop_loss", {
      symbol: "600519",
      entry_price: 90,
      current_price: 100,
      highest_price: 110,
    });
  });

  test("allows HK compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "hk.market_overview", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "hk.south_flow", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "hk.technical", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "hk.hot_rank", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", { command: "hk.market_overview" });
    await (quantCliTool.execute as any)("call-2", { command: "hk.south_flow" });
    await (quantCliTool.execute as any)("call-3", {
      command: "hk.technical",
      params: { symbol: "9988" },
    });
    await (quantCliTool.execute as any)("call-4", { command: "hk.hot_rank" });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "hk.market_overview", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "hk.south_flow", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "hk.technical", {
      symbol: "9988",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "hk.hot_rank", {});
  });

  test("allows sentiment compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "sentiment.stock_fund_flow", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.lhb", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.insider_trades", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.fund_holdings", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.top_fund_stocks", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.top_holders", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.holder_changes", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.margin_data", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "sentiment.stock_fund_flow",
      params: { symbol: "600519", days: 5 },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "sentiment.lhb",
      params: { symbol: "600519", date: "20260519" },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "sentiment.insider_trades",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "sentiment.fund_holdings",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-5", {
      command: "sentiment.top_fund_stocks",
    });
    await (quantCliTool.execute as any)("call-6", {
      command: "sentiment.top_holders",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-7", {
      command: "sentiment.holder_changes",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-8", {
      command: "sentiment.margin_data",
      params: { symbol: "600519" },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "sentiment.stock_fund_flow", {
      symbol: "600519",
      days: 5,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "sentiment.lhb", {
      symbol: "600519",
      date: "20260519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "sentiment.insider_trades", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "sentiment.fund_holdings", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "sentiment.top_fund_stocks", {});
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(6, "sentiment.top_holders", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(7, "sentiment.holder_changes", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(8, "sentiment.margin_data", {
      symbol: "600519",
    });
  });

  test("allows financial compatibility commands", async () => {
    runQuantV2Mock
      .mockResolvedValueOnce({ ok: true, command: "financial.indicators", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "financial.statements", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "financial.hk_financials", data: {}, error: null })
      .mockResolvedValueOnce({ ok: true, command: "financial.hk_analysis", data: {}, error: null });

    await (quantCliTool.execute as any)("call-1", {
      command: "financial.indicators",
      params: { symbol: "600519" },
    });
    await (quantCliTool.execute as any)("call-2", {
      command: "financial.statements",
      params: { symbol: "600519", statement: "income", recent_n: 4 },
    });
    await (quantCliTool.execute as any)("call-3", {
      command: "financial.hk_financials",
      params: { symbol: "9988" },
    });
    await (quantCliTool.execute as any)("call-4", {
      command: "financial.hk_analysis",
      params: { symbol: "9988" },
    });

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "financial.indicators", {
      symbol: "600519",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "financial.statements", {
      symbol: "600519",
      statement: "income",
      recent_n: 4,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "financial.hk_financials", {
      symbol: "9988",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "financial.hk_analysis", {
      symbol: "9988",
    });
  });

  test("allows performance analyze and signal arbitrate commands", async () => {
    runQuantV2Mock
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

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "performance.analyze", {
      strategy_id: "rsi",
      days: 90,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "signal.arbitrate", {
      date: "2026-05-20",
      min_confidence_gap: 0.1,
    });
  });

  test("allows priority 2 analytics commands", async () => {
    runQuantV2Mock
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

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "factor.analyze", {
      top_n: 10,
      min_observations: 5,
      sample_limit: 50000,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "sector.aggregate", {
      sector_field: "industry",
      limit: 10,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "benchmark.compare", {
      strategy_return: 0.12,
      benchmark_return: 0.08,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "portfolio.optimize", {
      symbols: "600519,000001",
      method: "risk_parity",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "strategy.optimize", {
      strategy: "rsi",
      metric: "sharpe",
      trials: 9,
    });
  });

  test("allows priority 3 ecosystem commands", async () => {
    runQuantV2Mock
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

    expect(runQuantV2Mock).toHaveBeenNthCalledWith(1, "watch.price_alert", {
      symbol: "600519",
      price: 105,
      above: 100,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(2, "stress.test", {
      positions_json: "[{\"symbol\":\"600519\",\"market_value\":10000}]",
      shock_pct: -0.2,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(3, "trade.verify", {
      trades_json: "[]",
      backtest_json: "[]",
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(4, "portfolio.correlation", {
      prices_json: "{\"600519\":[1,2,3],\"000001\":[1,2,4]}",
      threshold: 0.7,
    });
    expect(runQuantV2Mock).toHaveBeenNthCalledWith(5, "factor.decay", {
      factor: "momentum",
      horizons: "5,10,20",
    });
  });

  test("rejects unknown commands before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.magic",
      params: { symbol: "600519" },
    });

    expect(runQuantV2Mock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的量化命令");
    expect(result.content[0].text).toContain("tools.list");
  });

  test("rejects missing required params before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "stock.klines",
      params: { limit: 10 },
    });

    expect(runQuantV2Mock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("缺少必填参数");
    expect(result.content[0].text).toContain("symbol");
  });

  test("rejects unknown params before calling the CLI", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "signal.list",
      params: { signal_type: "BUY", unexpected: true },
    });

    expect(runQuantV2Mock).not.toHaveBeenCalled();
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

    expect(runQuantV2Mock).not.toHaveBeenCalled();
    expect(invalidSignal.content[0].text).toContain("signal_type");
    expect(invalidSignal.content[0].text).toContain("BUY 或 SELL");
    expect(invalidLimit.content[0].text).toContain("limit");
    expect(invalidLimit.content[0].text).toContain("正数");
  });

  test("validates backtest.run requires symbol or symbols with detailed reason", async () => {
    const result = await (quantCliTool.execute as any)("call-1", {
      command: "backtest.run",
      params: {},
    });

    expect(runQuantV2Mock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("backtest.run 至少需要 symbol 或 symbols 参数之一");
    expect(result.content[0].text).toContain("原因：回测需要指定股票代码才能获取历史数据并执行策略测试");
    expect(result.content[0].text).toContain("命令说明");
    expect(result.content[0].text).toContain("示例 params");
  });

  test("error messages include detailed reasons for validation failures", async () => {
    const missingRequired = await (quantCliTool.execute as any)("call-1", {
      command: "stock.klines",
      params: { limit: 10 },
    });
    const invalidType = await (quantCliTool.execute as any)("call-2", {
      command: "stock.klines",
      params: { symbol: "600519", limit: "not-a-number" },
    });
    const unsupportedParam = await (quantCliTool.execute as any)("call-3", {
      command: "stock.quote",
      params: { symbol: "600519", invalid_param: true },
    });

    expect(runQuantV2Mock).not.toHaveBeenCalled();

    // Missing required parameter
    expect(missingRequired.content[0].text).toContain("缺少必填参数: symbol");
    expect(missingRequired.content[0].text).toContain("原因：该参数是命令执行的必要条件");

    // Invalid type
    expect(invalidType.content[0].text).toContain("limit 必须是整数");
    expect(invalidType.content[0].text).toContain("原因：该参数不接受小数或非数字值");

    // Unsupported parameter
    expect(unsupportedParam.content[0].text).toContain("不支持的参数: invalid_param");
    expect(unsupportedParam.content[0].text).toContain("原因：该命令不接受此参数");
  });
});
