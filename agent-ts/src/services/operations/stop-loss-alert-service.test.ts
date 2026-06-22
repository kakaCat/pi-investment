import { describe, expect, jest, test, beforeEach, afterEach } from "@jest/globals";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const getStockPriceViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const analyzeMock = jest.fn<(request: any) => Promise<any>>();

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getAnnouncementsViaQuantCli: jest.fn(),
  getBatchStockPricesViaQuantCli: jest.fn(),
  getStockPriceViaQuantCli: getStockPriceViaQuantCliMock,
  getStockNewsViaQuantCli: jest.fn(),
  getStockHistoryViaQuantCli: jest.fn(),
  getStockInfoViaQuantCli: jest.fn(),
  getStockListViaQuantCli: jest.fn(),
}));

await jest.unstable_mockModule("./stop-loss-analyzer-service.js", () => ({
  StopLossAnalyzer: jest.fn().mockImplementation(() => ({
    analyze: analyzeMock,
  })),
}));

const { StopLossAlertService } = await import("./stop-loss-alert-service.js");

describe("StopLossAlertService", () => {
  const tempDirs: string[] = [];

  beforeEach(() => {
    getStockPriceViaQuantCliMock.mockReset();
    analyzeMock.mockReset();
  });

  afterEach(() => {
    for (const dir of tempDirs.splice(0)) {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("fetches current prices through quant CLI before stop-loss analysis", async () => {
    const piDir = mkdtempSync(join(tmpdir(), "stop-loss-alert-"));
    tempDirs.push(piDir);
    writeFileSync(join(piDir, "portfolio.json"), JSON.stringify({
      holdings: [{
        symbol: "600519",
        name: "贵州茅台",
        quantity: 100,
        avg_cost: 100,
        market: "A",
        notes: "止损8%",
      }],
    }));
    getStockPriceViaQuantCliMock.mockResolvedValue(JSON.stringify({ price: 90 }));
    analyzeMock.mockResolvedValue({
      request: {},
      analyzedAt: "2026-05-20T00:00:00+08:00",
      breakoutType: "NEUTRAL",
      confidence: 50,
      suggestedAction: "WARN_AND_WATCH",
      actionReason: "test",
      riskNote: "",
      technical: { trend: "震荡", trendConfirmed: false, supportLevel: null, resistanceLevel: null, pattern: null, rsi: null, macdSignal: null, evidence: [] },
      volume: { vsAvgVolume: null, isShrink: null, isVolumeSpike: null, evidence: [] },
      fundFlow: { mainForceNetFlow: null, retailBuyRatio: null, evidence: [] },
      fundamentals: { hasRecentNegativeNews: null, hasRecentPositiveNews: null, earningsWarning: null, newsSummary: "", evidence: [] },
      evidenceChain: [],
    });

    const result = await new StopLossAlertService(piDir).run();

    expect(getStockPriceViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(analyzeMock).toHaveBeenCalledWith(expect.objectContaining({
      symbol: "600519",
      currentPrice: 90,
    }));
    expect(result.triggered).toBe(true);
  });
});
