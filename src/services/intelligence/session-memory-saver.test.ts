/**
 * Session Memory Saver Tests
 */
import { describe, test, expect, jest, beforeEach } from "@jest/globals";
import type { AgentSession } from "@mariozechner/pi-coding-agent";

// Mock dependencies
const mockMessages = [
  {
    role: "user",
    content: "我想重构 akshare-ts 模块，它现在有 1248 行太大了"
  },
  {
    role: "assistant",
    content: "好的，我建议将它拆分成多个模块：market.ts, financial.ts, technical.ts 等"
  },
  {
    role: "user",
    content: "我喜欢用 TypeScript strict mode"
  },
  {
    role: "assistant",
    content: "明白了，我会确保所有新文件都使用 strict mode"
  }
];

const mockGetMessages = jest.fn(() => mockMessages);

jest.unstable_mockModule("../../core/agent/session-adapter.js", () => ({
  getMessages: mockGetMessages
}));

const mockCreateAgentSession = jest.fn();
const mockPrompt = jest.fn();

jest.unstable_mockModule("@mariozechner/pi-coding-agent", () => ({
  createAgentSession: mockCreateAgentSession
}));

jest.unstable_mockModule("../../config/config.js", () => ({
  createDeepSeekModel: jest.fn(() => ({ model: "deepseek-chat" }))
}));

jest.unstable_mockModule("../../infrastructure/tools/memory-tool.js", () => ({
  memoryWriteTool: { name: "memory_write" },
  memorySearchTool: { name: "memory_search" }
}));

const { saveSessionMemoryAsync, saveSessionMemorySync, extractSessionSummary } = await import("./session-memory-saver.js");

describe("SessionMemorySaver", () => {
  let mockSession: AgentSession;

  beforeEach(() => {
    jest.clearAllMocks();
    mockSession = {} as AgentSession;
    mockPrompt.mockResolvedValue(undefined);
    mockCreateAgentSession.mockResolvedValue({
      prompt: mockPrompt
    });
  });

  describe("saveSessionMemoryAsync", () => {
    test("should save memory asynchronously without blocking", async () => {
      const startTime = Date.now();

      // 调用异步保存（不等待）
      saveSessionMemoryAsync(mockSession, { verbose: false });

      const elapsed = Date.now() - startTime;

      // 应该立即返回（不阻塞）
      expect(elapsed).toBeLessThan(100);
    });

    test("should handle timeout gracefully", async () => {
      mockPrompt.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 5000)));

      // 不应该抛出错误
      await expect(
        saveSessionMemoryAsync(mockSession, { timeout: 100, verbose: false })
      ).resolves.toBeUndefined();
    });
  });

  describe("saveSessionMemorySync", () => {
    test("should create memory saver agent with correct config", async () => {
      await saveSessionMemorySync(mockSession, { verbose: false });

      expect(mockCreateAgentSession).toHaveBeenCalledWith(
        expect.objectContaining({
          cwd: process.cwd(),
          customTools: expect.arrayContaining([
            expect.objectContaining({ name: "memory_write" }),
            expect.objectContaining({ name: "memory_search" })
          ])
        })
      );
    });

    test("should pass conversation history to agent", async () => {
      await saveSessionMemorySync(mockSession, { verbose: false });

      expect(mockPrompt).toHaveBeenCalledWith(
        expect.stringContaining("User: 我想重构 akshare-ts 模块")
      );
      expect(mockPrompt).toHaveBeenCalledWith(
        expect.stringContaining("Assistant: 好的，我建议将它拆分成多个模块")
      );
    });

    test("should skip if no conversation history", async () => {
      mockGetMessages.mockReturnValueOnce([]);

      await saveSessionMemorySync(mockSession, { verbose: false });

      expect(mockCreateAgentSession).not.toHaveBeenCalled();
      expect(mockPrompt).not.toHaveBeenCalled();
    });

    test("should handle agent errors gracefully", async () => {
      mockPrompt.mockRejectedValueOnce(new Error("Agent failed"));

      await expect(
        saveSessionMemorySync(mockSession, { verbose: false })
      ).rejects.toThrow("Agent failed");
    });

    test("should timeout if agent takes too long", async () => {
      mockPrompt.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 5000)));

      await expect(
        saveSessionMemorySync(mockSession, { timeout: 100, verbose: false })
      ).rejects.toThrow("Memory save timeout");
    });
  });

  describe("extractSessionSummary", () => {
    test("should extract key decisions from messages", async () => {
      const summary = await extractSessionSummary(mockSession);

      expect(summary.keyDecisions.length).toBeGreaterThan(0);
    });

    test("should extract user preferences", async () => {
      const summary = await extractSessionSummary(mockSession);

      expect(summary.userPreferences.length).toBeGreaterThan(0);
    });

    test("should return empty summary for empty messages", async () => {
      mockGetMessages.mockReturnValueOnce([]);

      const summary = await extractSessionSummary(mockSession);

      expect(summary.keyDecisions).toEqual([]);
      expect(summary.importantFacts).toEqual([]);
      expect(summary.userPreferences).toEqual([]);
      expect(summary.unfinishedTasks).toEqual([]);
      expect(summary.lessonsLearned).toEqual([]);
    });
  });
});
