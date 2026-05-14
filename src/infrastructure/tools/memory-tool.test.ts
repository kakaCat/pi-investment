import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const writeMemoryMock = jest.fn<(content: string, category: string) => string>();
const hybridSearchMock = jest.fn<(query: string, topK: number) => Array<{ path: string; score: number; snippet: string }>>();
const initMemoryStoreMock = jest.fn();

jest.unstable_mockModule("../../services/intelligence/memory-store.js", () => ({
  getMemoryStore: () => ({
    writeMemory: writeMemoryMock,
    hybridSearch: hybridSearchMock,
  }),
  initMemoryStore: initMemoryStoreMock,
}));

const { memoryWriteTool, memorySearchTool } = await import("./memory-tool.js");

describe("memory tools", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("writes to general memory with category", async () => {
    writeMemoryMock.mockReturnValueOnce("Memory stored");

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "Project uses strict TypeScript",
      category: "fact",
    });

    expect(writeMemoryMock).toHaveBeenCalledWith("Project uses strict TypeScript", "fact");
    expect(result.content[0].text).toBe("Memory stored");
  });

  test("writes to general memory with default category", async () => {
    writeMemoryMock.mockReturnValueOnce("Memory stored");

    const result = await (memoryWriteTool.execute as any)("test-call", {
      content: "User prefers dark mode",
    });

    expect(writeMemoryMock).toHaveBeenCalledWith("User prefers dark mode", "general");
    expect(result.content[0].text).toBe("Memory stored");
  });

  test("searches memory with hybrid search", async () => {
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
    expect(result.content[0].text).toBe("[memory/2026-03-30.jsonl] (score: 0.91) User prefers pnpm over npm");
  });

  test("uses default top_k when not provided", async () => {
    hybridSearchMock.mockReturnValueOnce([]);

    const result = await (memorySearchTool.execute as any)("test-call", {
      query: "test query",
    });

    expect(hybridSearchMock).toHaveBeenCalledWith("test query", 5);
    expect(result.content[0].text).toBe("No relevant memories found.");
  });

  test("returns no results message when search is empty", async () => {
    hybridSearchMock.mockReturnValueOnce([]);

    const result = await (memorySearchTool.execute as any)("test-call", {
      query: "nonexistent",
      top_k: 10,
    });

    expect(result.content[0].text).toBe("No relevant memories found.");
  });
});

