/**
 * Memory Tool Adapter - memory_write / memory_search 工具定义
 *
 * 真实实现位于 services/intelligence/memory-store.ts
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { getMemoryStore } from "../../../services/intelligence/memory-store.js";

export { initMemoryStore as initMemoryTools } from "../../../services/intelligence/memory-store.js";

export const memoryWriteTool: ToolDefinition = {
  name: "memory_write",
  label: "写入记忆",
  description: "Save a specific fact, preference, or decision to long-term memory (persists across sessions). " +
    "Use when you learn something worth recalling in future conversations: user preferences, project conventions, key decisions, recurring context. " +
    "For stock-specific decisions, provide 'symbol' parameter to save to stock decision memory. " +
    "Not for temporary task state or in-progress notes — use task tools instead. " +
    "Write self-contained statements, not conversation summaries.",
  promptSnippet: '需要保存重要信息到记忆库时',
  promptGuidelines: [
    '用于保存用户偏好、投资策略、历史决策',
    '记忆会在后续对话中自动加载',
    '避免保存临时数据或过期信息'
  ],
  parameters: Type.Object({
    content: Type.String({
      description:
        "Self-contained statement to store (e.g., 'User prefers pnpm over npm', 'Project uses strict TypeScript'). " +
        "Keep specific and factual; avoid references to 'this session' or 'today'.",
    }),
    category: Type.Optional(Type.String({
      description:
        "Category for grouping and retrieval. " +
        "Use 'preference' (user likes/dislikes), 'fact' (project/tech conventions), 'context' (background info), 'task' (completed milestones). " +
        "Omit to default to 'general'.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const store = getMemoryStore();
      const result = store.writeMemory(params.content, params.category || "general");
      return {
        content: [{ type: "text" as const, text: result }],
        details: null,
      };
    } catch (e) {
      return {
        content: [{ type: "text" as const, text: `Error writing memory: ${e}` }],
        details: null,
      };
    }
  },
};

export const memorySearchTool: ToolDefinition = {
  name: "memory_search",
  label: "搜索记忆",
  description: "Search long-term memory for stored facts and preferences, ranked by semantic similarity. " +
    "Returns entries saved across sessions by memory_write. " +
    "Use for explicit recall when you need specific context not surfaced by auto-recall (which runs automatically each turn). " +
    "Not a substitute for auto-recall — only call this when you have a specific topic to look up.",
  promptSnippet: '需要查询历史记忆时',
  promptGuidelines: [
    '用于检索用户偏好、历史决策、投资策略',
    '支持关键词搜索和语义搜索',
    '返回相关记忆的内容和时间戳'
  ],
  parameters: Type.Object({
    query: Type.String({
      description:
        "Natural language description of what you're looking for " +
        "(e.g., 'user code style preferences', 'project database setup').",
    }),
    top_k: Type.Optional(Type.Integer({
      description: "Maximum results to return. Default: 5. Use 1–3 for targeted lookups; increase to 10–15 for broad recall.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const store = getMemoryStore();
      const results = store.hybridSearch(params.query, params.top_k || 5);
      if (!results.length) {
        return {
          content: [{ type: "text" as const, text: "No relevant memories found." }],
          details: null,
        };
      }
      const text = results
        .map(r => `[${r.path}] (score: ${r.score}) ${r.snippet}`)
        .join("\n");
      return {
        content: [{ type: "text" as const, text: text }],
        details: null,
      };
    } catch (e) {
      return {
        content: [{ type: "text" as const, text: `Error searching memory: ${e}` }],
        details: null,
      };
    }
  },
};
