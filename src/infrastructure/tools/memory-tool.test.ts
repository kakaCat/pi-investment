import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const writeMemoryMock = jest.fn<(content: string, category: string) => string>();
const hybridSearchMock = jest.fn<(query: string, topK: number) => Array<{ path: string; score: number; snippet: string }>>();
const saveStockMemoryMock = jest.fn<(symbol: string, content: string) => void>();
const appendStockMemoryMock = jest.fn<(symbol: string, section: string) => string>();
const getStockMemoryMock = jest.fn<(symbol: string) => string | null>();
const initMemoryStoreMock = jest.fn();

jest.unstable_mockModule("../../services/intelligence/memory-store.js", () => ({
  getMemoryStore: () => ({
    writeMemory: writeMemoryMock,
    hybridSearch: hybridSearchMock,
  }),
  initMemoryStore: initMemoryStoreMock,
}));

jest.unstable_mockModule("../../services/data/stock-decision-memory-service.js", () => ({
  stockDecisionMemoryService: {
    save: saveStockMemoryMock,
    append: appendStockMemoryMock,
    get: getStockMemoryMock,
  },
}));

const { memoryWriteTool, memorySearchTool } = await import("./memory-tool.js");

describe("memory tools", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("writes to stock decision memory with save when symbol and action=save are provided", async () => {
    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "## 2026-03-30\n- 首次建仓 10%",
      symbol: "600519",
      action: "save",
    });

    expect(saveStockMemoryMock).toHaveBeenCalledWith("600519", "## 2026-03-30\n- 首次建仓 10%");
    expect(appendStockMemoryMock).not.toHaveBeenCalled();
    expect(writeMemoryMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("已保存 600519 的决策记忆");
  });

  test("appends to stock decision memory by default when symbol is provided", async () => {
    appendStockMemoryMock.mockReturnValueOnce("# 600519\n\n## 2026-03-30\n- 继续持有\n");

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "## 2026-03-30\n- 继续持有",
      symbol: "600519",
    });

    expect(appendStockMemoryMock).toHaveBeenCalledWith("600519", "## 2026-03-30\n- 继续持有");
    expect(saveStockMemoryMock).not.toHaveBeenCalled();
    expect(writeMemoryMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("已追加 600519 的决策记录");
  });

  test("keeps the existing general memory write path when symbol is omitted", async () => {
    writeMemoryMock.mockReturnValueOnce("Memory stored");

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "Project uses strict TypeScript",
      category: "fact",
    });

    expect(writeMemoryMock).toHaveBeenCalledWith("Project uses strict TypeScript", "fact");
    expect(saveStockMemoryMock).not.toHaveBeenCalled();
    expect(appendStockMemoryMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("Memory stored");
  });

  test("reads stock decision memory when symbol is provided without requiring a query", async () => {
    getStockMemoryMock.mockReturnValueOnce("# 600519\n\n## 2026-03-30\n- 不追高\n");

    const result = await (memorySearchTool.execute as any)("test-call", {
      symbol: "600519",
    });

    expect(getStockMemoryMock).toHaveBeenCalledWith("600519");
    expect(hybridSearchMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("# 600519\n\n## 2026-03-30\n- 不追高\n");
  });

  test("returns a stock-specific miss message when symbol memory does not exist", async () => {
    getStockMemoryMock.mockReturnValueOnce(null);

    const result = await (memorySearchTool.execute as any)("test-call", {
      symbol: "000001",
    });

    expect(getStockMemoryMock).toHaveBeenCalledWith("000001");
    expect(hybridSearchMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("暂无 000001 的决策记忆");
  });

  test("keeps the existing hybrid search path when symbol is omitted", async () => {
    hybridSearchMock.mockReturnValueOnce([
      {
        path: "memory/2026-03-30.jsonl",
        score: 0.91,
        snippet: "User prefers pnpm over npm",
      },
    ]);

    const result = await (memorySearchTool.execute as any)("test-call", {
      query: "package manager preference",
      top_k: 3,
    });

    expect(hybridSearchMock).toHaveBeenCalledWith("package manager preference", 3);
    expect(getStockMemoryMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("[memory/2026-03-30.jsonl] (score: 0.91) User prefers pnpm over npm");
  });

  test("returns an explicit error when general memory search has neither query nor symbol", async () => {
    const result = await (memorySearchTool.execute as any)("test-call", {});

    expect(hybridSearchMock).not.toHaveBeenCalled();
    expect(getStockMemoryMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toBe("Error searching memory: query is required when symbol is not provided.");
  });
});
