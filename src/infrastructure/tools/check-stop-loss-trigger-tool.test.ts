import { describe, expect, test, jest } from "@jest/globals";

// ── Mock PortfolioService BEFORE importing the module under test ──
const mockLoad = jest.fn<() => any>();
const mockGetWithPnL = jest.fn<() => any>();

jest.mock("../../services/portfolio/portfolio-service.js", () => ({
  PortfolioService: jest.fn().mockImplementation(() => ({
    load: mockLoad,
    getWithPnL: mockGetWithPnL,
  })),
}));

import type { AgentToolResult } from "@mariozechner/pi-coding-agent";
type AnyAgentToolResult = AgentToolResult<any>;
import { checkStopLossTriggerTool } from "./check-stop-loss-trigger-tool.js";

// ── Helpers ────────────────────────────────────────────────────────────────

function callTool(
  params: Record<string, unknown> = {},
): Promise<AnyAgentToolResult> {
  return checkStopLossTriggerTool.execute(
    "test-call-id",
    params,
    undefined as any,
    undefined as any,
    undefined as any,
  ) as Promise<AnyAgentToolResult>;
}

/** Build a holding with explicit stop_loss in portfolio.json */
function makeHolding(
  symbol: string,
  name: string,
  avgCost: number,
  quantity: number,
  currentPrice: number,
  pnlPct: number,
  marketValue: number,
  stopLoss: number | null = null,
): { snapshot: any; raw: any } {
  return {
    snapshot: {
      symbol,
      name,
      quantity,
      avg_cost: avgCost,
      current_price: currentPrice,
      change_pct: 0,
      pnl_pct: pnlPct,
      pnl_amount: (currentPrice - avgCost) * quantity,
      market_value: marketValue,
      market: "A",
      notes: "",
      added_date: "2026-01-01",
    },
    raw: {
      symbol,
      name,
      quantity,
      avg_cost: avgCost,
      market: "A",
      notes: "",
      added_date: "2026-01-01",
      ...(stopLoss !== null ? { stop_loss: stopLoss } : {}),
    },
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("checkStopLossTriggerTool", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── Test 1: Empty portfolio ──────────────────────────────────────────────
  test("returns no-holdings message when portfolio is empty", async () => {
    mockGetWithPnL.mockResolvedValue({
      holdings: [],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });
    // load() won't be called if holdings is empty, but just in case
    mockLoad.mockReturnValue({ holdings: [] });

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("当前无持仓");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.totalHoldings).toBe(0);
  });

  // ── Test 2: Triggered positions with explicit stop_loss ──────────────────
  test("detects triggered positions with explicit stop_loss", async () => {
    const h1 = makeHolding("600519", "贵州茅台", 2200, 200, 1850, -15.91, 370000, 1900);
    const h2 = makeHolding("000001", "平安银行", 12, 5000, 11.2, -6.67, 56000, 11.5);
    const h3 = makeHolding("300750", "宁德时代", 250, 1000, 260, 4.0, 260000, 230);

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot, h2.snapshot, h3.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw, h2.raw, h3.raw],
    });

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    // Header and summary
    expect(text).toContain("止损检查报告");
    expect(text).toContain("已触发=2");
    expect(text).toContain("安全=1");

    // Triggered positions
    expect(text).toContain("贵州茅台");
    expect(text).toContain("平安银行");
    expect(text).toContain("已触发止损");

    // Safe position
    expect(text).toContain("宁德时代");
    expect(text).toContain("安全持仓");

    // Advice
    expect(text).toContain("总体建议");
    expect(text).toContain("立即执行止损");

    // Details structure
    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.totalHoldings).toBe(3);
    expect(details.triggered).toHaveLength(2);
    expect(details.warnings).toHaveLength(0);
    expect(details.safe).toHaveLength(1);
    expect(details.noStopLossConfigured).toHaveLength(0);

    // Verify triggered details
    expect(details.triggered[0].symbol).toBe("600519");
    expect(details.triggered[0].stopLoss).toBe(1900);
    expect(details.triggered[0].stopLossSource).toBe("explicit");

    // Verify safe details
    expect(details.safe[0].symbol).toBe("300750");
    expect(details.safe[0].stopLoss).toBe(230);
    expect(details.safe[0].distanceToStopLoss).toBeGreaterThan(3);
  });

  // ── Test 3: Default stop-loss with positions that have no explicit config ──
  test("applies default stop-loss percentage when no explicit stop_loss set", async () => {
    const h1 = makeHolding("600519", "贵州茅台", 100, 100, 88, -12.0, 8800, null);
    // 88/100 = -12%, default -8% would be 92 — so triggered
    const h2 = makeHolding("000001", "平安银行", 12, 5000, 11.2, -6.67, 56000, null);
    // 11.2/12 = -6.67%, default -8% would be 11.04 — so not triggered, 11.2 > 11.04
    // distance = (11.2-11.04)/11.04 = 1.45% → warning zone
    const h3 = makeHolding("300750", "宁德时代", 250, 1000, 280, 12.0, 280000, null);
    // 280/250 = +12%, default -8% would be 230 — safe

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot, h2.snapshot, h3.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw, h2.raw, h3.raw],
    });

    const result = await callTool({ default_stop_loss_pct: -8 });

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    expect(text).toContain("默认 -8% 回撤止损");
    expect(text).toContain("已触发=1");
    expect(text).toContain("接近=1");
    expect(text).toContain("安全=1");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.defaultStopLossPct).toBe(-8);
    expect(details.triggered).toHaveLength(1);
    expect(details.warnings).toHaveLength(1);
    expect(details.safe).toHaveLength(1);

    // H1: default stop = 100 * 0.92 = 92, current 88 → triggered
    expect(details.triggered[0].symbol).toBe("600519");
    expect(details.triggered[0].stopLoss).toBeCloseTo(92, 1);
    expect(details.triggered[0].stopLossSource).toBe("default");

    // H2: default stop = 12 * 0.92 = 11.04, current 11.2
    // distance = (11.2-11.04)/11.04 = 1.45% < 3% → warning
    expect(details.warnings[0].symbol).toBe("000001");
    expect(details.warnings[0].stopLoss).toBeCloseTo(11.04, 2);
    expect(details.warnings[0].distanceToStopLoss).toBeLessThan(3);

    // H3: default stop = 250 * 0.92 = 230, current 280 → safe
    expect(details.safe[0].symbol).toBe("300750");
    expect(details.safe[0].stopLoss).toBeCloseTo(230, 1);
    expect(details.safe[0].distanceToStopLoss).toBeGreaterThan(3);
  });

  // ── Test 4: Warning positions (approaching stop-loss) ────────────────────
  test("flags positions approaching stop-loss as warnings", async () => {
    const h1 = makeHolding("000333", "美的集团", 70, 2000, 65.8, -6.0, 131600, 64);
    // current 65.8, stop 64 → distance = (65.8-64)/64 = 2.81% < 3% → warning

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw],
    });

    const result = await callTool({});

    const text = (result.content[0] as any).text;
    expect(text).toContain("接近止损");

    const details = result.details as any;
    expect(details.warnings).toHaveLength(1);
    expect(details.triggered).toHaveLength(0);
    expect(details.warnings[0].symbol).toBe("000333");
    expect(details.warnings[0].distanceToStopLoss).toBeLessThan(3);
  });

  // ── Test 5: All safe positions ──────────────────────────────────────────
  test("shows all safe when no positions are near stop-loss", async () => {
    const h1 = makeHolding("600519", "贵州茅台", 1800, 100, 2100, 16.67, 210000, 1500);
    const h2 = makeHolding("300750", "宁德时代", 230, 200, 280, 21.74, 56000, 200);

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot, h2.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw, h2.raw],
    });

    const result = await callTool({});

    const text = (result.content[0] as any).text;
    expect(text).toContain("所有持仓运行正常");
    expect(text).not.toContain("已触发止损");
    expect(text).not.toContain("接近止损");

    const details = result.details as any;
    expect(details.triggered).toHaveLength(0);
    expect(details.warnings).toHaveLength(0);
    expect(details.safe).toHaveLength(2);
  });

  // ── Test 6: Positions without any stop_loss configured and default disabled ──
  test("reports positions without stop_loss when default is disabled (0)", async () => {
    const h1 = makeHolding("600519", "贵州茅台", 2000, 100, 1950, -2.5, 195000, null);

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw],
    });

    // default_stop_loss_pct = 0 disables auto stop-loss
    const result = await callTool({ default_stop_loss_pct: 0 });

    const text = (result.content[0] as any).text;
    expect(text).toContain("未设置止损");
    expect(text).toContain("已关闭");

    const details = result.details as any;
    expect(details.noStopLossConfigured).toHaveLength(1);
    expect(details.triggered).toHaveLength(0);
    expect(details.warnings).toHaveLength(0);
    expect(details.safe).toHaveLength(0);
  });

  // ── Test 7: Mixed scenario ──────────────────────────────────────────────
  test("correctly handles mixed triggered, warning, safe, and no-stop-loss positions", async () => {
    const h1 = makeHolding("600519", "贵州茅台", 2000, 100, 1780, -11.0, 178000, 1800);
    // 1780 <= 1800 → triggered
    const h2 = makeHolding("000001", "平安银行", 12, 5000, 11.4, -5.0, 57000, 11.1);
    // 11.4 > 11.1, distance=(11.4-11.1)/11.1=2.7% < 3% → warning
    const h3 = makeHolding("300750", "宁德时代", 250, 1000, 275, 10.0, 275000, null);
    // default stop = 250*0.92=230, 275 > 230, distance=19.6% → safe
    const h4 = makeHolding("002415", "海康威视", 35, 3000, 33.2, -5.14, 99600, null);
    // default stop = 35*0.92=32.2, 33.2 > 32.2, distance=3.1% → safe

    mockGetWithPnL.mockResolvedValue({
      holdings: [h1.snapshot, h2.snapshot, h3.snapshot, h4.snapshot],
      total_cost: 0,
      total_value: 0,
      total_pnl: 0,
      total_pnl_pct: 0,
      as_of: "2026-05-15",
    });

    mockLoad.mockReturnValue({
      holdings: [h1.raw, h2.raw, h3.raw, h4.raw],
    });

    const result = await callTool({});

    const details = result.details as any;
    expect(details.totalHoldings).toBe(4);
    expect(details.triggered).toHaveLength(1);
    expect(details.warnings).toHaveLength(1);
    expect(details.safe).toHaveLength(2);
    expect(details.noStopLossConfigured).toHaveLength(0);
  });
});
