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
});
