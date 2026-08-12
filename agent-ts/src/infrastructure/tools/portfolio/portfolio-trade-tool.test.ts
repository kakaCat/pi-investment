import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { executePortfolioTrade } from "./portfolio-trade-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch as any;

describe("portfolio_trade 账户显式化", () => {
  beforeEach(() => { mockFetch.mockReset(); });

  test("缺 account 直接拒绝", async () => {
    const result = await executePortfolioTrade({
      action: "buy", symbol: "600519", reason: "测试买入理由：不少于十个字",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.error).toMatch(/account/);
  });

  test("交易提交到 simulation 账户端点（不再调 /api/portfolio/trade）", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: { order_id: 1, order_status: "filled", price: 10, shares: 100, amount: 1000 },
    }), { status: 200 }));
    const result = await executePortfolioTrade({
      action: "buy", symbol: "600519", account: "v13_simulation",
      shares: 100, reason: "测试买入理由：不少于十个字",
    } as any) as any;
    expect(result.success).toBe(true);
    const [url] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts/v13_simulation/trade");
    expect(String(url)).not.toContain("/api/portfolio/trade");
  });

  test("T+1 超额卖出被拦截时返回结构化可卖数量", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      success: false,
      error: "T+1 可卖数量不足: 可卖 600 股，委托 1000 股",
      details: { sellable_shares: 600, symbol: "600519" },
    }), { status: 422, headers: { "Content-Type": "application/json" } }));
    const result = await executePortfolioTrade({
      action: "sell", symbol: "600519", account: "agent_virtual",
      shares: 1000, reason: "测试卖出理由：止盈离场不少于十个字",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.sellable_shares).toBe(600);
    expect(result.hint).toContain("600");
    expect(result.hint).toContain("shares_available");
  });

  test("非 T+1 的 422 走原有兜底格式（无 sellable_shares）", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      success: false,
      error: "可用资金不足: 需要 ¥100,005.00，可用 ¥1,000.00",
    }), { status: 422, headers: { "Content-Type": "application/json" } }));
    const result = await executePortfolioTrade({
      action: "buy", symbol: "600519", account: "agent_virtual",
      shares: 1000, reason: "测试买入理由：资金不足应被拒绝",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.sellable_shares).toBeUndefined();
    expect(result.error).toContain("交易执行失败");
  });
});
