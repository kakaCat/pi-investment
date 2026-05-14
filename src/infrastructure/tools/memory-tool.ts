/**
 * Memory Tool Adapter - memory_write / memory_search 工具定义
 *
 * 真实实现位于 services/intelligence/memory-store.ts
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { getMemoryStore } from "../../services/intelligence/memory-store.js";
import { stockDecisionMemoryService } from "../../services/data/stock-decision-memory-service.js";

export { initMemoryStore as initMemoryTools } from "../../services/intelligence/memory-store.js";

export const memoryWriteTool: ToolDefinition = {
  name: "memory_write",
  label: "写入记忆",
  description: "Save a specific fact, preference, or decision to long-term memory (persists across sessions). " +
    "Use when you learn something worth recalling in future conversations: user preferences, project conventions, key decisions, recurring context. " +
    "For stock-specific decisions, provide 'symbol' parameter to save to stock decision memory. " +
    "Not for temporary task state or in-progress notes — use task tools instead. " +
    "Write self-contained statements, not conversation summaries.",
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
    symbol: Type.Optional(Type.String({
      description: "Stock symbol (e.g., '600519'). If provided, saves to stock decision memory instead of general memory.",
    })),
    action: Type.Optional(Type.Union([
      Type.Literal("save"),
      Type.Literal("append"),
    ], {
      description: "For stock memory: 'save' (overwrite) or 'append' (add to existing). Default: 'append'.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      // 股票决策记忆
      if (params.symbol) {
        const action = params.action || "append";
        if (action === "save") {
          stockDecisionMemoryService.save(params.symbol, params.content);
          return {
            content: [{ type: "text" as const, text: `已保存 ${params.symbol} 的决策记忆` }],
            details: undefined,
          };
        } else {
          stockDecisionMemoryService.append(params.symbol, params.content);
          return {
            content: [{ type: "text" as const, text: `已追加 ${params.symbol} 的决策记录` }],
            details: undefined,
          };
        }
      }

      // 通用记忆
      const store = getMemoryStore();
      const result = store.writeMemory(params.content, params.category || "general");
      return {
        content: [{ type: "text" as const, text: result }],
        details: undefined,
      };
    } catch (e) {
      return {
        content: [{ type: "text" as const, text: `Error writing memory: ${e}` }],
        details: undefined,
      };
    }
  },
};

export const memorySearchTool: ToolDefinition = {
  name: "memory_search",
  label: "搜索记忆",
  description: "Search long-term memory for stored facts and preferences, ranked by semantic similarity. " +
    "Returns entries saved across sessions by memory_write. " +
    "For stock-specific decisions, provide 'symbol' parameter to retrieve stock decision memory. " +
    "Use for explicit recall when you need specific context not surfaced by auto-recall (which runs automatically each turn). " +
    "Not a substitute for auto-recall — only call this when you have a specific topic to look up.",
  parameters: Type.Object({
    query: Type.Optional(Type.String({
      description:
        "Natural language description of what you're looking for " +
        "(e.g., 'user code style preferences', 'project database setup'). Required when 'symbol' is omitted; otherwise optional.",
    })),
    top_k: Type.Optional(Type.Integer({
      description: "Maximum results to return. Default: 5. Use 1–3 for targeted lookups; increase to 10–15 for broad recall.",
    })),
    symbol: Type.Optional(Type.String({
      description: "Stock symbol (e.g., '600519'). If provided, retrieves stock decision memory instead of searching general memory.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      // 股票决策记忆
      if (params.symbol) {
        const memory = stockDecisionMemoryService.get(params.symbol);
        if (!memory) {
          return {
            content: [{ type: "text" as const, text: `暂无 ${params.symbol} 的决策记忆` }],
            details: undefined,
          };
        }
        return {
          content: [{ type: "text" as const, text: memory }],
          details: undefined,
        };
      }

      // 通用记忆搜索
      if (!params.query) {
        return {
          content: [{ type: "text" as const, text: "Error searching memory: query is required when symbol is not provided." }],
          details: undefined,
        };
      }

      const store = getMemoryStore();
      const results = store.hybridSearch(params.query, params.top_k || 5);
      if (!results.length) {
        return {
          content: [{ type: "text" as const, text: "No relevant memories found." }],
          details: undefined,
        };
      }
      const text = results
        .map(r => `[${r.path}] (score: ${r.score}) ${r.snippet}`)
        .join("\n");
      return {
        content: [{ type: "text" as const, text: text }],
        details: undefined,
      };
    } catch (e) {
      return {
        content: [{ type: "text" as const, text: `Error searching memory: ${e}` }],
        details: undefined,
      };
    }
  },
};
