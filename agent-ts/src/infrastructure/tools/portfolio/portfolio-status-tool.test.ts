// src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
import { describe, expect, test } from "@jest/globals";
import { computePortfolioView } from "./portfolio-status-tool.js";

describe("computePortfolioView 账目恒等式", () => {
  test("total_value 语义为总资产（含现金）时，总资产不得重复加计现金", () => {
    // 真实 API 响应：0 持仓时 total_value == cash
    const view = computePortfolioView({
      cash: "147070.15",
      total_value: "147070.15",
      positions: [],
      last_rebalance_date: "2026-07-17",
    });

    expect(view.total_assets).toBeCloseTo(147070.15, 2);
    expect(view.total_market_value).toBeCloseTo(0, 2);
    expect(view.cash).toBeCloseTo(147070.15, 2);
  });

  test("有持仓时：持仓市值 = 总资产 - 现金", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "100000",
      positions: [
        {
          symbol: "600519",
          shares: 40,
          avg_price: "1000",
          current_price: "1500",
          market_value: "60000",
          profit: "20000",
          profit_rate: "50",
        },
      ],
    });

    expect(view.total_assets).toBeCloseTo(100000, 2);
    expect(view.total_market_value).toBeCloseTo(60000, 2);
    expect(view.holdings[0].market_value).toBeCloseTo(60000, 2);
    expect(view.total_pnl).toBeCloseTo(20000, 2);
  });

  test("total_value 缺失时回退为 现金 + 持仓市值合计", () => {
    const view = computePortfolioView({
      cash: "40000",
      positions: [
        { symbol: "600519", shares: 40, market_value: "60000", profit: "0" },
      ],
    });

    expect(view.total_assets).toBeCloseTo(100000, 2);
    expect(view.total_market_value).toBeCloseTo(60000, 2);
  });

  test("summary 中 总资产 = 现金 + 持仓市值（恒等式可见）", () => {
    const view = computePortfolioView({
      cash: "147070.15",
      total_value: "147070.15",
      positions: [],
    });

    // 恒等式：total_assets === cash + total_market_value
    expect(view.total_assets).toBeCloseTo(view.cash + view.total_market_value, 2);
    expect(view.summary).toContain("147070.15");
    expect(view.summary).not.toContain("294140");
  });
});
