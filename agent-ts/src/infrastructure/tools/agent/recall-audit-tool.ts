/**
 * Recall Audit Tool - 召回审计工具
 *
 * 供记忆 Agent 查看召回日志与质量指标、标注反馈。
 *
 * 2026-10-05 · REQ-261004202231-bb99：原实现直连 quantsys-v2 的
 * v2 的 recall-audit 三个端点（list / stats / feedback）。
 * v2 记忆子系统下线后改走 agent-os：
 *   - `list`     → agent-os `memory recall-audit`（namespace + limit）
 *   - `stats`    → **客户端从 list 结果派生**（总数 / 注入数 / 抑制数 / 注入率）
 *   - `feedback` → **能力已退役**：agent-os 没有逐条标注端点 → 显式报错，不静默假装成功
 */

import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { agentOSMemoryRecallAudit } from "../../agent-os/cli.js";

const DEFAULT_NAMESPACE = "default";

export const recallAuditTool: ToolDefinition = {
  name: "recall_audit",
  label: "召回审计",
  description:
    "Query recall audit logs and derive quality statistics from the agent-os memory backend. " +
    "Use 'list' to view recent recall events, 'stats' to derive injection counts/rate from them. " +
    "'feedback' is retired (the per-record annotation endpoint went away with quantsys-v2 memory).",
  promptSnippet: "需要查看召回日志或质量统计时",
  promptGuidelines: [
    "用于审计记忆召回质量（数据源：agent-os）",
    "list 支持 namespace 与 limit；stats 由 list 结果派生注入率",
    "feedback 已随 v2 记忆子系统退役，不要调用",
  ],
  parameters: Type.Object({
    action: Type.Union(
      [Type.Literal("list"), Type.Literal("stats"), Type.Literal("feedback")],
      {
        description:
          "Action to perform: 'list' (query audit entries), 'stats' (derive metrics from entries), 'feedback' (retired).",
      }
    ),
    namespace: Type.Optional(
      Type.String({
        description: "agent-os memory namespace to read recall audit from (default: 'default').",
      })
    ),
    limit: Type.Optional(
      Type.Integer({
        description: "Max entries to fetch (1-100, default 20). Used by 'list' and 'stats'.",
        minimum: 1,
        maximum: 100,
      })
    ),
    // 以下为 v2 时代的过滤参数：agent-os 记录里没有这些维度 → 收到时明确告知不支持，
    // 而不是静默忽略（静默忽略会让调用方以为筛选生效）。
    flow: Type.Optional(
      Type.String({ description: "（已退役）v2 时代的 flow 过滤，agent-os 记录无此维度。" })
    ),
    gate_result: Type.Optional(
      Type.String({ description: "（已退役）v2 时代的门禁结果过滤。" })
    ),
    suppressed_only: Type.Optional(
      Type.Boolean({ description: "（已退役）v2 时代的仅看抑制。" })
    ),
    page: Type.Optional(Type.Integer({ description: "（已退役）v2 时代的分页参数。" })),
    page_size: Type.Optional(
      Type.Integer({ description: "（已退役）v2 时代的分页参数；请改用 limit。", minimum: 1, maximum: 100 })
    ),
    date_from: Type.Optional(Type.String({ description: "（已退役）v2 时代的日期过滤。" })),
    date_to: Type.Optional(Type.String({ description: "（已退役）v2 时代的日期过滤。" })),
    audit_id: Type.Optional(Type.Integer({ description: "（已退役）feedback 专用。" })),
    memory_id: Type.Optional(Type.Integer({ description: "（已退役）feedback 专用。" })),
    feedback: Type.Optional(
      Type.Union([Type.Literal("relevant"), Type.Literal("irrelevant")], {
        description: "（已退役）feedback 专用。",
      })
    ),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const action = params.action;

      if (action === "list") {
        return await handleList(params);
      } else if (action === "stats") {
        return await handleStats(params);
      } else if (action === "feedback") {
        return await handleFeedback(params);
      } else {
        return {
          content: [{ type: "text" as const, text: `未知 action: ${action}` }],
          details: { error: `unknown action: ${action}` },
        };
      }
    } catch (error: any) {
      return {
        content: [
          {
            type: "text" as const,
            text: `召回审计失败: ${error.message}`,
          },
        ],
        details: { error: error.message },
      };
    }
  },
};

/** 取 agent-os 的召回审计条目（两条 action 共用） */
async function fetchEntries(params: any) {
  const namespace = params.namespace || DEFAULT_NAMESPACE;
  const limit = params.limit || params.page_size || 20;

  const result = await agentOSMemoryRecallAudit(namespace, limit);
  if (!result.success) {
    throw new Error(result.error ?? 'agent-os memory recall-audit failed');
  }
  return { namespace, entries: result.data ?? [] };
}

const RETIRED_NOTE =
  '注意：以下 v2 时代的参数已退役、当前实现不生效 —— flow / gate_result / suppressed_only / page / date_from / date_to' +
  '（agent-os 的召回审计记录只含 id/namespace/query/resultsCount/timestamp）。';

async function handleList(params: any) {
  const { namespace, entries } = await fetchEntries(params);
  const payload = {
    namespace,
    entries,
    total: entries.length,
    note: RETIRED_NOTE,
  };
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
    details: payload,
  };
}

/**
 * 纯函数：从 agent-os 的召回审计条目派生统计量（导出以便单测，无需后端）。
 * 口径与 v2 保持同一意图（注入率），但维度更少（无 suppression 原因 / 分数直方图 / 分流策略）。
 */
export function deriveRecallStats(entries: Array<{ resultsCount?: number }>) {
  const total = entries.length;
  const injected = entries.filter((e) => (e?.resultsCount ?? 0) > 0).length;
  const suppressed = total - injected;
  const injectionRate = total > 0 ? injected / total : 0;
  return { total, injected, suppressed, injection_rate: Number(injectionRate.toFixed(4)) };
}

async function handleStats(params: any) {
  const { namespace, entries } = await fetchEntries(params);

  const { total, injected, suppressed, injection_rate } = deriveRecallStats(entries);

  const payload = {
    namespace,
    total,
    injected,
    suppressed,
    injection_rate,
    interpretation:
      'injection_rate 低且 suppressed 占多数时，先确认记忆库里到底有没有内容（agent-os：memory search），再怀疑检索。',
    note: '客户端派生（agent-os 无 stats 端点）；v2 时代的 suppression 原因 / 分数直方图等维度已随下线消失。',
  };
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
    details: payload,
  };
}

async function handleFeedback(_params: any): Promise<never> {
  // 不静默成功：能力真的没了就响亮报错。
  throw new Error(
    'feedback 能力已随 quantsys-v2 记忆子系统下线（REQ-261004202231-bb99）：' +
    'agent-os 不提供逐条召回标注端点。若确需该能力，请先在 agent-os 侧补端点再接线。'
  );
}
