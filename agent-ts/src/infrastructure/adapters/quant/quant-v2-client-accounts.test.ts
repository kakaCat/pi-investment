import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import {
  listAccounts,
  getAccount,
  createAccount,
  executeAccountTrade,
  getAccountTrades,
} from "./quant-v2-client.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = mockFetch as any;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("QuantV2Client 账户方法", () => {
  beforeEach(() => { mockFetch.mockReset(); });

  test("listAccounts 调用账户发现端点", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { accounts: [], total: 0 } }));
    await listAccounts();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/accounts"),
      expect.anything(),
    );
  });

  test("getAccount 按账户名查询", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: {} }));
    await getAccount("v13_simulation");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/accounts/v13_simulation"),
      expect.anything(),
    );
  });

  test("createAccount POST 开户参数", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { account_name: "x" } }));
    await createAccount({ account_name: "x", initial_capital: 50000, display_name: "X" });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts");
    expect(opts?.method).toBe("POST");
    expect(JSON.parse(String(opts?.body))).toMatchObject({ account_name: "x", initial_capital: 50000 });
  });

  test("executeAccountTrade POST 到账户交易端点", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { order_id: 1 } }));
    await executeAccountTrade("v13_simulation", {
      action: "buy", symbol: "600519", shares: 100, reason: "测试买入理由：不少于十个字",
    });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts/v13_simulation/trade");
    expect(opts?.method).toBe("POST");
  });

  test("getAccountTrades 携带 account_name", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: [] }));
    await getAccountTrades("v13_simulation", 50);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/trades?account_name=v13_simulation"),
      expect.anything(),
    );
  });

  test("v2 错误响应（400/404）透传 available_accounts", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: false, error: "account_name is required", available_accounts: ["v13_simulation"] }, 400));
    await expect(getAccountTrades("", 50)).rejects.toThrow(/account_name is required/);
  });
});
