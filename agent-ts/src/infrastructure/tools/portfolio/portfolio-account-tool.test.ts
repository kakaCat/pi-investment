import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { manageAccount } from "./portfolio-account-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch as any;

describe("portfolio_account 开户", () => {
  beforeEach(() => { mockFetch.mockReset(); });

  test("create 提交开户参数", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true, data: { account_name: "manual_test" },
    }), { status: 201 }));
    const result = await manageAccount({
      action: "create", account_name: "manual_test", initial_capital: 100000,
      display_name: "手工测试仓",
    } as any) as any;
    expect(result.success).toBe(true);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts");
    expect(opts?.method).toBe("POST");
  });

  test("禁止创建名为 default 的账户", async () => {
    const result = await manageAccount({
      action: "create", account_name: "default", initial_capital: 100000,
    } as any) as any;
    expect(result.success).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
