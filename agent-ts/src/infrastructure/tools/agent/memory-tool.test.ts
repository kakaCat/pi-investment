import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const writeMock = jest.fn<(params: any) => Promise<{ id?: number; path?: string }>>();
const searchMock = jest.fn<(query: string, topK?: number) => Promise<Array<{ title: string; content: string; score: number }>>>();

jest.unstable_mockModule("../../../services/memory/index.js", () => ({
  getMemoryProvider: () => ({
    write: writeMock,
    search: searchMock,
  }),
}));

const { memoryWriteTool, memorySearchTool } = await import("./memory-tool.js");

describe("memory tools (W1.4 provider 架构)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("memory_write 走 provider.write，落 episode（流水类免证据）", async () => {
    writeMock.mockResolvedValueOnce({ id: 42 });

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "Project uses strict TypeScript",
      category: "fact",
    });

    expect(writeMock).toHaveBeenCalledTimes(1);
    const arg = writeMock.mock.calls[0][0] as any;
    expect(arg.kind).toBe("episode");
    expect(arg.content).toBe("Project uses strict TypeScript");
    expect(arg.payload).toEqual({ category: "fact" });
    expect(arg.source).toBe("agent");
    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("v2 #42");
    }
  });

  test("memory_write 无 category 时不带 payload", async () => {
    writeMock.mockResolvedValueOnce({ path: "memory/daily (general)" });

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "User prefers dark mode",
    });

    const arg = writeMock.mock.calls[0][0] as any;
    expect(arg.payload).toBeUndefined();
    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("Memory saved");
    }
  });

  test("memory_write provider 抛错时返回错误文本", async () => {
    writeMock.mockRejectedValueOnce(new Error("v2 down"));

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "anything",
    });

    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("Error writing memory");
    }
  });

  test("memory_search 走 provider.search 并格式化结果", async () => {
    searchMock.mockResolvedValueOnce([
      { title: "MEMORY.md", content: "User prefers pnpm over npm", score: 0.91 },
    ]);

    const result = await (memorySearchTool.execute as any)("test-call", {
      query: "package manager preference",
      top_k: 3,
    });

    expect(searchMock).toHaveBeenCalledWith("package manager preference", 3);
    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("MEMORY.md");
      expect(content0.text).toContain("pnpm");
    }
  });

  test("memory_search 无结果时返回提示", async () => {
    searchMock.mockResolvedValueOnce([]);

    const result = await (memorySearchTool.execute as any)("test-call", {
      query: "nothing",
    });

    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("No relevant memories");
    }
  });
});
