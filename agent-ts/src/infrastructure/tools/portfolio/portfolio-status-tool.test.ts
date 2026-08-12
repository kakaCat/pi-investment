// src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
import { describe, expect, test } from "@jest/globals";
import { computePortfolioView, getPortfolioStatus } from "./portfolio-status-tool.js";

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

describe("portfolio_status 账户显式化", () => {
  test("action=get 缺 account 返回错误和提示", async () => {
    const result = await getPortfolioStatus({ action: "get" } as any);
    expect((result as any).success).toBe(false);
    expect((result as any).error).toMatch(/account/);
  });
});

describe("computePortfolioView 新域模型", () => {
  test("资金两态 + 新持仓列映射", () => {
    const view = computePortfolioView({
      cash_available: "110030.89",
      cash_frozen: "0",
      position_value: "38255",
      total_value: "148285.89",
      cumulative_return: "0.483",
      positions: [{
        symbol: "601888", shares_total: 700, shares_available: 700,
        avg_cost: "52.87", current_price: "54.65", market_value: "38255",
        profit_total: "1246", profit_total_rate: "0.0337",
      }],
    });
    expect(view.cash).toBeCloseTo(110030.89, 2);
    expect(view.total_assets).toBeCloseTo(148285.89, 2);
    expect(view.total_market_value).toBeCloseTo(38255, 2);
    expect(view.holdings[0].shares).toBe(700);
    expect(view.holdings[0].cost_price).toBeCloseTo(52.87, 2);
    expect(view.holdings[0].pnl).toBeCloseTo(1246, 2);
  });
});

describe("computePortfolioView 数据契约（A线）", () => {
  test("days_held 真实透传，缺失时为 undefined 而非假 0", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "100000",
      positions: [
        { symbol: "600519", shares: 40, market_value: "60000", profit: "0", days_held: 3 },
        { symbol: "000001", shares: 100, market_value: "0", profit: "0" },
      ],
    });
    expect(view.holdings[0].days_held).toBe(3);
    expect(view.holdings[1].days_held).toBeUndefined();
  });

  test("pnl_pct 统一为百分数：profit_total_rate=0.0122 → 1.22", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "100000",
      positions: [{
        symbol: "600519", shares: 40, market_value: "60000",
        profit: "732", profit_total_rate: "0.0122",
      }],
    });
    // 个仓 pnl_pct 与组合 total_pnl_pct 必须同单位（百分数）
    expect(view.holdings[0].pnl_pct).toBeCloseTo(1.22, 2);
    expect(view.holdings[0].pnl_pct).toBeGreaterThan(0.1); // 不是 0.0122 小数形式
    expect(Math.abs(view.holdings[0].pnl_pct - view.total_pnl_pct)).toBeLessThan(5);
  });

  test("last_updated 优先用后端响应生成时间，不回退到 last_rebalance_date", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "40000",
      positions: [],
      last_updated: "2026-07-28T09:31:00",
      last_rebalance_date: "2026-07-17",
    });
    expect(view.last_updated).toBe("2026-07-28T09:31:00");
  });

  test("price_stale 标志透传：行情获取失败时调用方必须可见", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "40000",
      positions: [],
      price_stale: true,
    });
    expect(view.price_stale).toBe(true);
  });

  test("benchmark 块透传并写入 summary：跑赢/跑输基准一眼可见", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "100000",
      positions: [],
      benchmark: {
        symbol: "sh000300",
        benchmark_name: "沪深300",
        benchmark_return_1m: 0.023,
        account_return_1m: 0.0125,
        excess_return_1m: -0.0105,
        sharpe: 0.8,
        aligned_days: 20,
      },
    });
    expect(view.benchmark?.benchmark_return_1m).toBeCloseTo(0.023);
    expect(view.summary).toContain("沪深300");
    expect(view.summary).toContain("2.30%");
    expect(view.summary).toContain("1.25%");
  });
});

describe("computePortfolioView T+1 可卖数量", () => {
  test("透出 shares_available（持仓总数与可卖数成对出现）", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "51000",
      positions: [
        {
          symbol: "600519",
          shares_total: 1000,
          shares_available: 600,
          avg_cost: "10",
          current_price: "11",
          market_value: "11000",
          profit_total: "1000",
          profit_total_rate: 0.1,
        },
      ],
    });
    expect(view.holdings[0].shares).toBe(1000);
    expect(view.holdings[0].shares_available).toBe(600);
  });

  test("shares_available 缺失时保持 undefined，绝不回退总持仓造假", () => {
    const view = computePortfolioView({
      cash: "40000",
      positions: [
        { symbol: "600519", shares: 40, market_value: "60000", profit: "0" },
      ],
    });
    expect(view.holdings[0].shares_available).toBeUndefined();
  });
});
