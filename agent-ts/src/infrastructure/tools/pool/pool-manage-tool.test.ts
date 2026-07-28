import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockAddPoolMembers = jest.fn<(...args: any[]) => Promise<any>>();
const mockRemovePoolMembers = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  createPool: jest.fn(),
  listPools: jest.fn(),
  getPool: jest.fn(),
  updatePool: jest.fn(),
  deletePool: jest.fn(),
  refreshPool: jest.fn(),
  scanAndCreatePool: jest.fn(),
  updatePoolMember: jest.fn(),
  scanPoolSignals: jest.fn(),
  addPoolMembers: mockAddPoolMembers,
  removePoolMembers: mockRemovePoolMembers,
}));

const { poolManageTool } = await import("./pool-manage-tool.js");

beforeEach(() => {
  mockAddPoolMembers.mockReset();
  mockRemovePoolMembers.mockReset();
});

const exec = (params: any) => poolManageTool.execute("test-id", params);

describe("pool_manage add_member", () => {
  it("缺 pool_id 报错且不调用 client", async () => {
    const result = await exec({ action: "add_member", symbols: ["600519.SH"] });
    expect((result.content[0] as any).text).toContain("add_member 需要 pool_id");
    expect(mockAddPoolMembers).not.toHaveBeenCalled();
  });

  it("空 symbols 报错且不调用 client", async () => {
    const result = await exec({ action: "add_member", pool_id: 1, symbols: [] });
    expect((result.content[0] as any).text).toContain("symbols");
    expect(mockAddPoolMembers).not.toHaveBeenCalled();
  });

  it("映射到 addPoolMembers 并传元数据", async () => {
    mockAddPoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "测试池", members: [{ symbol: "600519.SH" }] },
        added: ["600519.SH"],
        skipped: [],
      },
    });
    const result = await exec({
      action: "add_member", pool_id: 1, symbols: ["600519.SH"],
      member_description: "关注", tags: ["白酒"],
    });
    expect(mockAddPoolMembers).toHaveBeenCalledWith(1, {
      symbols: ["600519.SH"],
      description: "关注",
      buy_point: undefined,
      sell_point: undefined,
      tags: ["白酒"],
    });
    expect((result.content[0] as any).text).toContain("600519.SH");
  });

  it("输出包含 skipped 与动态池 warning", async () => {
    mockAddPoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "动态池", members: [{ symbol: "600519.SH" }] },
        added: [],
        skipped: ["600519.SH"],
        warning: "动态池 refresh 将按筛选条件重建成员，手动增删的成员可能被覆盖",
      },
    });
    const result = await exec({ action: "add_member", pool_id: 1, symbols: ["600519.SH"] });
    const text = (result.content[0] as any).text;
    expect(text).toContain("跳过");
    expect(text).toContain("600519.SH");
    expect(text).toContain("⚠️");
    expect(text).toContain("refresh");
  });
});

describe("pool_manage remove_member", () => {
  it("缺 symbols 报错且不调用 client", async () => {
    const result = await exec({ action: "remove_member", pool_id: 1 });
    expect((result.content[0] as any).text).toContain("symbols");
    expect(mockRemovePoolMembers).not.toHaveBeenCalled();
  });

  it("映射到 removePoolMembers 并格式化输出", async () => {
    mockRemovePoolMembers.mockResolvedValue({
      success: true,
      data: {
        pool: { id: 1, name: "测试池", members: [] },
        removed: ["000858.SZ"],
        skipped: ["999999.SH"],
      },
    });
    const result = await exec({
      action: "remove_member", pool_id: 1, symbols: ["000858.SZ", "999999.SH"],
    });
    expect(mockRemovePoolMembers).toHaveBeenCalledWith(1, ["000858.SZ", "999999.SH"]);
    const text = (result.content[0] as any).text;
    expect(text).toContain("000858.SZ");
    expect(text).toContain("999999.SH");
  });
});
