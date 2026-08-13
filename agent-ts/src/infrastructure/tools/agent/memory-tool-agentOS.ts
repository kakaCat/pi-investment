/**
 * Memory Tool Adapter - Agent OS Version
 *
 * WP-4: 改用 agent-os CLI 实现 memory_write / memory_search
 * 直接调用 Agent OS 的 memory 命令，不再使用 MemoryProvider
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import * as AgentOS from "../../agent-os/agent-os-cli.js";

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
        "Use 'user' (preferences/habits), 'feedback' (corrections/guidance), 'project' (conventions/decisions), 'reference' (external resources). " +
        "Default: 'project'.",
    })),
    importance: Type.Optional(Type.Number({
      description: "Importance score (0.0-1.0). Higher = more likely to be recalled. Default: 0.5",
      minimum: 0.0,
      maximum: 1.0,
    })),
    tags: Type.Optional(Type.Array(Type.String(), {
      description: "Tags for categorization and filtering (e.g., ['typescript', 'code-style'])",
    })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const memoryId = await AgentOS.Memory.write({
        namespace: 'fin-agent',
        content: params.content,
        category: params.category || 'project',
        importance: params.importance ?? 0.5,
        tags: params.tags || [],
        metadata: {},
      });

      return {
        content: [{
          type: "text" as const,
          text: `✓ Memory saved (Agent OS #${memoryId}): ${params.content.slice(0, 60)}...`
        }],
        details: null,
      };
    } catch (e: any) {
      return {
        content: [{
          type: "text" as const,
          text: `✗ Error writing memory: ${e.message}`
        }],
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
    categories: Type.Optional(Type.Array(Type.String(), {
      description: "Filter by categories (e.g., ['user', 'project'])",
    })),
    min_importance: Type.Optional(Type.Number({
      description: "Minimum importance threshold (0.0-1.0). Default: 0.0",
      minimum: 0.0,
      maximum: 1.0,
    })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const results = await AgentOS.Memory.search({
        namespace: 'fin-agent',
        query: params.query,
        categories: params.categories,
        minImportance: params.min_importance || 0.0,
        limit: params.top_k || 5,
        hybrid: true,  // 使用混合搜索（BM25 + Vector）
      });

      if (!results.length) {
        return {
          content: [{ type: "text" as const, text: "No relevant memories found." }],
          details: null,
        };
      }

      const text = results
        .map((r, i) => {
          const mem = r.memory;
          const preview = mem.content.slice(0, 150).replace(/\n/g, ' ');
          return `${i + 1}. [${mem.category}] (score: ${r.score.toFixed(2)}, importance: ${mem.importance.toFixed(2)})\n   ${preview}...`;
        })
        .join("\n\n");

      return {
        content: [{ type: "text" as const, text: `Found ${results.length} memories:\n\n${text}` }],
        details: null,
      };
    } catch (e: any) {
      return {
        content: [{
          type: "text" as const,
          text: `✗ Error searching memory: ${e.message}`
        }],
        details: null,
      };
    }
  },
};

/**
 * 兼容导出：历史上的 initMemoryTools(piDir)。
 * WP-4: 不再需要初始化，直接使用 agent-os CLI
 */
export async function initMemoryTools(piDir: string): Promise<void> {
  // No-op: agent-os CLI 不需要初始化
  console.log('[Memory Tools] Using Agent OS CLI (no initialization needed)');
}
