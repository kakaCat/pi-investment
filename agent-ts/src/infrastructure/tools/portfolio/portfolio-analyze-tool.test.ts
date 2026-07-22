import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { analyzePortfolio } from "./portfolio-analyze-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch as any;

describe("portfolio_analyze 账户显式化", () => {
  beforeEach(() => { mockFetch.mockReset(); });

  test("缺 account 直接拒绝", async () => {
    const result = await analyzePortfolio({} as any) as any;
    expect(result.success).toBe(false);
    expect(result.error).toMatch(/account/);
  });

  test("按 account 查询持仓并给出止盈建议（新域模型字段）", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: {
        account_name: "v13_simulation", cash_available: 50000, position_value: 60000,
        total_value: 110000, cumulative_return: 0.1,
        positions: [{
          symbol: "600519", shares_total: 40, shares_available: 40,
          avg_cost: 1000, current_price: 1150, market_value: 46000,
          profit_total: 6000, profit_total_rate: 0.15,
        }],
      },
    }), { status: 200 }));
    const result = await analyzePortfolio({ account: "v13_simulation" } as any) as any;
    expect(result.success).toBe(true);
    expect(String(mockFetch.mock.calls[0][0])).toContain("/api/simulation/accounts/v13_simulation");
    expect(result.analysis[0].action).toBe("take_profit");
  });
});
