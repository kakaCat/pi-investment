import { describe, expect, test, jest } from "@jest/globals";
import {
  checkHolding,
  buildOutput,
  CheckStatus,
} from "./check-stop-loss-trigger-tool.js";
import type {
  HoldingCheckData,
  CheckResult,
} from "./check-stop-loss-trigger-tool.js";

// ── Mock PortfolioService using ESM-compatible pattern ──
const mockLoad = jest.fn<() => any>();
const mockGetWithPnL = jest.fn<() => any>();

await jest.unstable_mockModule(
  "../../services/portfolio/portfolio-service.js",
  () => ({
    PortfolioService: jest.fn().mockImplementation(() => ({
      load: mockLoad,
      getWithPnL: mockGetWithPnL,
    })),
  }),
);

const { checkStopLossTriggerTool } = await import(
  "./check-stop-loss-trigger-tool.js"
);

// ── Fixtures ───────────────────────────────────────────────────────────────

function makeHolding(overrides: Partial<HoldingCheckData> = {}): HoldingCheckData {
  return {
    symbol: "000001",
    name: "测试股票",
    quantity: 1000,
    avg_cost: 10.0,
    current_price: 9.5,
    market_value: 9500,
    pnl_pct: -5.0,
    pnl_amount: -500,
    ...overrides,
  };
}

// ── Tests: checkHolding (pure logic) ──────────────────────────────────────

describe("checkHolding", () => {
  test("returns triggered when currentPrice ≤ stopLoss (explicit)", () => {
    const holding = makeHolding({ current_price: 8.0, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [
      { symbol: "000001", stop_loss: 9.0 },
    ] as any;

    const result = checkHolding(holding, allHoldings, -8);

    expect(result.status).toBe(CheckStatus.Triggered);
    if (result.status === CheckStatus.Triggered) {
      expect(result.position.stopLoss).toBe(9.0);
      expect(result.position.stopLossSource).toBe("explicit");
      expect(result.position.currentPrice).toBe(8.0);
      expect(result.position.lossAmount).toBe(-2000);
    }
  });

  test("returns triggered when currentPrice ≤ stopLoss (default -8%)", () => {
    const holding = makeHolding({ current_price: 9.0, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [];

    const result = checkHolding(holding, allHoldings, -8);

    expect(result.status).toBe(CheckStatus.Triggered);
    if (result.status === CheckStatus.Triggered) {
      expect(result.position.stopLoss).toBeCloseTo(9.2, 2); // 10 * (1 - 0.08) = 9.2
      expect(result.position.stopLossSource).toBe("default");
      expect(result.position.lossAmount).toBe(-1000);
    }
  });

  test("returns no_stop_loss when defaultStopLossPct >= 0 and no explicit stop_loss", () => {
    const holding = makeHolding({ current_price: 9.5, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [
      { symbol: "000001", stop_loss: null },
    ] as any;

    const result = checkHolding(holding, allHoldings, 0);

    expect(result.status).toBe(CheckStatus.NoStopLoss);
    if (result.status === CheckStatus.NoStopLoss) {
      expect(result.position.symbol).toBe("000001");
      expect(result.position.avgCost).toBe(10.0);
    }
  });

  test("returns safe when price is well above stop-loss", () => {
    const holding = makeHolding({ current_price: 12.0, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [
      { symbol: "000001", stop_loss: 9.0 },
    ] as any;

    const result = checkHolding(holding, allHoldings, -8);

    expect(result.status).toBe(CheckStatus.Safe);
    if (result.status === CheckStatus.Safe) {
      // distance = (12 - 9) / 9 * 100 = 33.33%
      expect(result.position.distanceToStopLoss).toBeGreaterThan(20);
    }
  });

  test("returns warning when price is close to stop-loss (within 3%)", () => {
    const holding = makeHolding({ current_price: 9.25, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [
      { symbol: "000001", stop_loss: 9.0 },
    ] as any;

    const result = checkHolding(holding, allHoldings, -8);

    expect(result.status).toBe(CheckStatus.Warning);
    if (result.status === CheckStatus.Warning) {
      // distance = (9.25 - 9.0) / 9.0 * 100 = 2.78%
      expect(result.position.distanceToStopLoss).toBeLessThan(3);
      expect(result.position.distanceToStopLoss).toBeGreaterThan(0);
    }
  });

  test("uses default stop-loss when holding not found in portfolio data", () => {
    const holding = makeHolding({ current_price: 9.5, avg_cost: 10.0 });
    const allHoldings: HoldingCheckData[] = [];

    const result = checkHolding(holding, allHoldings, -8);

    expect(result.status).toBe(CheckStatus.Safe);
    if (result.status === CheckStatus.Safe) {
      expect(result.position.stopLoss).toBeCloseTo(9.2, 2);
      expect(result.position.stopLossSource).toBe("default");
    }
  });
});

// ── Tests: buildOutput ─────────────────────────────────────────────────────

describe("buildOutput", () => {
  test("returns all-clear message when no triggered/warning positions", () => {
    const safeResult: CheckResult = {
      status: CheckStatus.Safe,
      position: {
        symbol: "000001",
        name: "测试股票",
        currentPrice: 12.0,
        avgCost: 10.0,
        stopLoss: 9.0,
        stopLossSource: "explicit",
        pnlPct: 20,
        distanceToStopLoss: 33.33,
        quantity: 1000,
        marketValue: 12000,
      },
    };

    const { text, details } = buildOutput([safeResult], -8);

    expect(text).toContain("所有持仓运行正常");
    expect(text).toContain("安全持仓");
    expect(text).toContain("12.00");
    expect(text).not.toContain("已触发止损");
    expect(details.triggered).toHaveLength(0);
    expect(details.safe).toHaveLength(1);
  });

  test("includes triggered and warning sections when present", () => {
    const triggeredResult: CheckResult = {
      status: CheckStatus.Triggered,
      position: {
        symbol: "600001",
        name: "下跌股",
        currentPrice: 8.0,
        avgCost: 10.0,
        stopLoss: 9.0,
        stopLossSource: "explicit",
        pnlPct: -20,
        quantity: 500,
        marketValue: 4000,
        lossAmount: -1000,
      },
    };

    const warningResult: CheckResult = {
      status: CheckStatus.Warning,
      position: {
        symbol: "600002",
        name: "接近止损股",
        currentPrice: 9.2,
        avgCost: 10.0,
        stopLoss: 9.0,
        stopLossSource: "explicit",
        pnlPct: -8,
        distanceToStopLoss: 2.22,
        quantity: 300,
        marketValue: 2760,
      },
    };

    const safeResult: CheckResult = {
      status: CheckStatus.Safe,
      position: {
        symbol: "600003",
        name: "安全股",
        currentPrice: 15.0,
        avgCost: 10.0,
        stopLoss: 9.0,
        stopLossSource: "explicit",
        pnlPct: 50,
        distanceToStopLoss: 66.67,
        quantity: 200,
        marketValue: 3000,
      },
    };

    const { text, details } = buildOutput(
      [triggeredResult, warningResult, safeResult],
      -8,
    );

    expect(text).toContain("已触发=1");
    expect(text).toContain("接近=1");
    expect(text).toContain("安全=1");

    expect(text).toContain("下跌股");
    expect(text).toContain("接近止损股");
    expect(text).toContain("安全股");

    expect(text).toContain("立即执行止损");
    expect(text).toContain("密切关注");
    expect(text).toContain("总体建议");

    expect(details.totalHoldings).toBe(3);
    expect(details.triggered).toHaveLength(1);
    expect(details.warnings).toHaveLength(1);
    expect(details.safe).toHaveLength(1);
  });

  test("includes no_stop_loss section when positions have no stop loss", () => {
    const noSlResult: CheckResult = {
      status: CheckStatus.NoStopLoss,
      position: {
        symbol: "000001",
        name: "无止损股",
        currentPrice: 11.0,
        avgCost: 10.0,
        pnlPct: 10,
        quantity: 100,
        marketValue: 1100,
      },
    };

    const { text, details } = buildOutput([noSlResult], 0);

    expect(text).toContain("未设置止损");
    expect(text).toContain("无止损股");
    expect(text).toContain("默认止损已关闭");
    expect(details.noStopLossConfigured).toHaveLength(1);
  });
});

// ── Tests: full tool execution (with mocked PortfolioService) ──────────────

describe("checkStopLossTriggerTool (integration)", () => {
  beforeEach(() => {
    mockLoad.mockReset();
    mockGetWithPnL.mockReset();
  });

  function callTool(
    params: Record<string, unknown>,
  ): ReturnType<typeof checkStopLossTriggerTool.execute> {
    return checkStopLossTriggerTool.execute(
      "test-call-id",
      params,
      undefined as any,
      undefined as any,
      undefined as any,
    );
  }

  test("returns no-holdings message when portfolio is empty", async () => {
    mockGetWithPnL.mockResolvedValue({
      holdings: [],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2025-01-01",
    });
    mockLoad.mockReturnValue({ holdings: [], last_updated: "2025-01-01" });

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toBe("当前无持仓");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.totalHoldings).toBe(0);
    expect(details.triggered).toHaveLength(0);
  });

  test("detects triggered and safe positions correctly", async () => {
    mockGetWithPnL.mockResolvedValue({
      holdings: [
        {
          symbol: "600001",
          name: "下跌股",
          quantity: 500,
          avg_cost: 10.0,
          current_price: 8.0,
          market_value: 4000,
          pnl_pct: -20,
          pnl_amount: -1000,
          change_pct: -2,
        },
        {
          symbol: "600003",
          name: "安全股",
          quantity: 200,
          avg_cost: 10.0,
          current_price: 15.0,
          market_value: 3000,
          pnl_pct: 50,
          pnl_amount: 1000,
          change_pct: 1,
        },
      ],
      total_cost: 7000,
      total_value: 7000,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2025-01-01",
    });

    mockLoad.mockReturnValue({
      holdings: [
        { symbol: "600001", name: "下跌股", quantity: 500, avg_cost: 10.0, market: "A", notes: "", added_date: "2025-01-01", stop_loss: 9.0, target_price: null, sector: "", buy_reason: "" },
        { symbol: "600003", name: "安全股", quantity: 200, avg_cost: 10.0, market: "A", notes: "", added_date: "2025-01-01", stop_loss: 9.0, target_price: null, sector: "", buy_reason: "" },
      ],
      last_updated: "2025-01-01",
    });

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("已触发=1");
    expect(text).toContain("安全=1");
    expect(text).toContain("下跌股");
    expect(text).toContain("安全股");

    const details = result.details as any;
    expect(details.totalHoldings).toBe(2);
    expect(details.triggered).toHaveLength(1);
    expect(details.triggered[0].symbol).toBe("600001");
    expect(details.safe).toHaveLength(1);
    expect(details.safe[0].symbol).toBe("600003");
  });

  test("applies default stop-loss when no explicit stop_loss set", async () => {
    mockGetWithPnL.mockResolvedValue({
      holdings: [
        {
          symbol: "000001",
          name: "无止损股",
          quantity: 1000,
          avg_cost: 100,
          current_price: 88,
          market_value: 88000,
          pnl_pct: -12,
          pnl_amount: -12000,
          change_pct: -2,
        },
      ],
      total_cost: 100000,
      total_value: 88000,
      total_pnl: -12000,
      total_pnl_pct: -12,
      as_of: "2025-01-01",
    });

    mockLoad.mockReturnValue({
      holdings: [{ symbol: "000001", name: "无止损股", quantity: 1000, avg_cost: 100, market: "A", notes: "", added_date: "2025-01-01", stop_loss: null, target_price: null, sector: "", buy_reason: "" }],
      last_updated: "2025-01-01",
    });

    const result = await callTool({ default_stop_loss_pct: -10 });

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("默认 -10% 回撤止损");
    // default stop-loss = 100 * (1 - 0.10) = 90
    // current_price = 88 <= 90 → triggered
    expect(text).toContain("已触发=1");

    const details = result.details as any;
    expect(details.triggered).toHaveLength(1);
    expect(details.triggered[0].stopLoss).toBe(90);
    expect(details.triggered[0].stopLossSource).toBe("default");
  });

  test("reports error when PortfolioService throws", async () => {
    mockGetWithPnL.mockRejectedValue(new Error("Network error"));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("止损检查失败");
    expect(text).toContain("Network error");
    expect(result.details).toBeUndefined();
  });
});
