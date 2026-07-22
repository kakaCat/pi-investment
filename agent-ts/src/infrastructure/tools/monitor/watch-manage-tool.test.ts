import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockRun = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: mockRun,
}));

const { watchManageTool } = await import("./watch-manage-tool.js");

beforeEach(() => { mockRun.mockReset(); });

const exec = (params: any) => watchManageTool.execute("test-id", params);

describe("watch_manage", () => {
  it("add 映射到 watch.rules.create", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.create", data: { rule: { id: 1 } } } as any);
    await exec({
      action: "add", symbol: "600519.SH",
      conditions: [{ type: "price_break", params: { direction: "above", price: 1800 } }],
      context: "突破平台考虑加仓",
    });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.create", expect.objectContaining({
      symbol: "600519.SH", context: "突破平台考虑加仓",
    }));
  });

  it("list 映射到 watch.rules.list 并传 symbol", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.list", data: { rules: [] } } as any);
    await exec({ action: "list", symbol: "600519.SH" });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.list", { symbol: "600519.SH" });
  });

  it("update 需要 rule_id", async () => {
    const result = await exec({ action: "update", enabled: false });
    expect(result.details).toMatchObject({ success: false, error: "MISSING_RULE_ID" });
    expect(mockRun).not.toHaveBeenCalled();
  });

  it("update 映射到 watch.rules.update", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.update", data: { rule: { id: 3 } } } as any);
    await exec({ action: "update", rule_id: 3, enabled: false });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.update", { id: 3, enabled: false });
  });

  it("remove 映射到 watch.rules.remove", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.rules.remove", data: {} } as any);
    await exec({ action: "remove", rule_id: 3 });
    expect(mockRun).toHaveBeenCalledWith("watch.rules.remove", { id: 3 });
  });

  it("triggers 映射到 watch.triggers.list", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "watch.triggers.list", data: { triggers: [] } } as any);
    await exec({ action: "triggers", symbol: "600519.SH", limit: 10 });
    expect(mockRun).toHaveBeenCalledWith("watch.triggers.list", { symbol: "600519.SH", limit: 10 });
  });

  it("add 缺少 conditions 报错", async () => {
    const result = await exec({ action: "add", symbol: "600519.SH" });
    expect(result.details).toMatchObject({ success: false, error: "MISSING_CONDITIONS" });
  });

  it("未知 action 报错", async () => {
    const result = await exec({ action: "explode" });
    expect(result.details).toMatchObject({ success: false });
  });
});
