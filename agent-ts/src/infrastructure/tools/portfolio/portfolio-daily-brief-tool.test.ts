// src/infrastructure/tools/portfolio/portfolio-daily-brief-tool.test.ts
import { describe, expect, test } from "@jest/globals";
import { buildDailyBrief } from "./portfolio-daily-brief-tool.js";
import { computePortfolioView } from "./portfolio-status-tool.js";

const baseView = computePortfolioView({
  cash: "40000",
  total_value: "100000",
  positions: [{
    symbol: "600519", shares: 40, market_value: "60000",
    profit: "732", profit_total_rate: "0.0122", days_held: 1,
  }],
  benchmark: {
    symbol: "sh000300", benchmark_name: "沪深300",
    benchmark_return_1m: 0.023, account_return_1m: 0.0125, excess_return_1m: -0.0105,
  },
});

describe("buildDailyBrief 每日对账单", () => {
  test("包含昨日操作、持仓健康度、基准标尺、一句话结论", () => {
    const brief = buildDailyBrief({
      account: "agent_virtual",
      today: "2026-07-28",
      view: baseView,
      decisions: [{ created_at: "2026-07-27T10:00:00", decision_type: "buy", reasoning: "MACD金叉" }],
      trades: [{ trade_date: "2026-07-27", action: "BUY", symbol: "600519", shares: 40, price: 1500, reason: "MACD金叉" }],
    });
    expect(brief.summary).toContain("昨日操作");
    expect(brief.summary).toContain("600519");
    expect(brief.summary).toContain("持仓健康度");
    expect(brief.summary).toContain("沪深300");
    expect(brief.one_liner.length).toBeGreaterThan(0);
  });

  test("昨日买入今日浮盈 → 结论肯定方向", () => {
    const brief = buildDailyBrief({
      account: "agent_virtual",
      today: "2026-07-28",
      view: baseView,
      decisions: [],
      trades: [{ trade_date: "2026-07-27", action: "BUY", symbol: "600519", shares: 40, price: 1500 }],
    });
    expect(brief.one_liner).toMatch(/正确|浮盈/);
  });

  test("空仓无交易 → 不交易是合法决策的提示存在", () => {
    const emptyView = computePortfolioView({ cash: "100000", total_value: "100000", positions: [] });
    const brief = buildDailyBrief({
      account: "agent_virtual",
      today: "2026-07-28",
      view: emptyView,
      decisions: [],
      trades: [],
    });
    expect(brief.summary).toContain("不交易");
    expect(brief.no_trade_hint).toContain("decision_record");
  });

  test("跑输基准时一句话结论要点出来", () => {
    const brief = buildDailyBrief({
      account: "agent_virtual",
      today: "2026-07-28",
      view: baseView, // excess = -1.05%
      decisions: [],
      trades: [],
    });
    expect(brief.one_liner).toMatch(/跑输|落后/);
  });
});
