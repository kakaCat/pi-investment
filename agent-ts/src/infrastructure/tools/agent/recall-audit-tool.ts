/**
 * Recall Audit Tool - 召回审计工具
 *
 * 供记忆 Agent 查询召回日志、统计质量指标、标注反馈。
 * API 契约见 quantsys-v2/tests/domain/memory/test_recall_audit_routes.py
 */

import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

const V2_API_BASE = process.env.QUANTSYS_V2_API_URL || "http://127.0.0.1:5001";

export const recallAuditTool: ToolDefinition = {
  name: "recall_audit",
  label: "召回审计",
  description:
    "Query recall audit logs, view quality statistics, and provide feedback on recalled memories. " +
    "Use 'list' to view recent recall events, 'stats' to analyze injection rates and quality metrics, " +
    "'feedback' to annotate whether a recalled memory was relevant (agent feedback only).",
  promptSnippet: "需要查看召回日志或质量统计时",
  promptGuidelines: [
    "用于审计记忆召回质量",
    "查看注入率、分流统计、抑制原因",
    "标注召回内容的相关性（仅限 agent 反馈）",
  ],
  parameters: Type.Object({
    action: Type.Union(
      [Type.Literal("list"), Type.Literal("stats"), Type.Literal("feedback")],
      {
        description:
          "Action to perform: 'list' (query audit logs), 'stats' (view aggregated metrics), 'feedback' (annotate relevance).",
      }
    ),
    // list action 参数
    flow: Type.Optional(
      Type.String({
        description: "Filter by flow type (e.g., 'chat', 'watch'). Only for 'list' action.",
      })
    ),
    gate_result: Type.Optional(
      Type.String({
        description:
          "Filter by gate result ('passed' = 已注入放行, 'suppressed' = 已抑制). Only for 'list' action.",
      })
    ),
    suppressed_only: Type.Optional(
      Type.Boolean({
        description: "Show only suppressed recalls. Only for 'list' action.",
      })
    ),
    page: Type.Optional(
      Type.Integer({
        description: "Page number for pagination (default: 1). Only for 'list' action.",
        minimum: 1,
      })
    ),
    page_size: Type.Optional(
      Type.Integer({
        description: "Items per page (default: 20, max: 100). Only for 'list' action.",
        minimum: 1,
        maximum: 100,
      })
    ),
    date_from: Type.Optional(
      Type.String({
        description: "Start date filter (YYYY-MM-DD format). For 'list' and 'stats' actions.",
      })
    ),
    date_to: Type.Optional(
      Type.String({
        description: "End date filter (YYYY-MM-DD format). For 'list' and 'stats' actions.",
      })
    ),
    // feedback action 参数
    audit_id: Type.Optional(
      Type.Integer({
        description: "Audit record ID to provide feedback on. Required for 'feedback' action.",
      })
    ),
    memory_id: Type.Optional(
      Type.Integer({
        description: "Memory ID within the audit record. Required for 'feedback' action.",
      })
    ),
    feedback: Type.Optional(
      Type.Union([Type.Literal("relevant"), Type.Literal("irrelevant")], {
        description: "Feedback value: 'relevant' or 'irrelevant'. Required for 'feedback' action.",
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
          content: [
            {
              type: "text" as const,
              text: `Unknown action: ${action}`,
            },
          ],
          details: null,
        };
      }
    } catch (error: any) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Error: ${error.message || String(error)}`,
          },
        ],
        details: { error: error.message },
      };
    }
  },
};

async function handleList(params: any) {
  const queryParams = new URLSearchParams();
  if (params.flow) queryParams.set("flow", params.flow);
  if (params.gate_result) {
    // DB 规范值为 passed/suppressed；'injected' 作为别名防御性映射到 passed
    const gate = params.gate_result === "injected" ? "passed" : params.gate_result;
    queryParams.set("gate_result", gate);
  }
  if (params.suppressed_only) queryParams.set("suppressed_only", "true");
  if (params.page) queryParams.set("page", String(params.page));
  if (params.page_size) queryParams.set("page_size", String(params.page_size));
  if (params.date_from) queryParams.set("date_from", params.date_from);
  if (params.date_to) queryParams.set("date_to", params.date_to);

  const url = `${V2_API_BASE}/api/memory/recall-audit?${queryParams.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  const result = await response.json();
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(result, null, 2),
      },
    ],
    details: result,
  };
}

async function handleStats(params: any) {
  const queryParams = new URLSearchParams();
  if (params.date_from) queryParams.set("date_from", params.date_from);
  if (params.date_to) queryParams.set("date_to", params.date_to);

  const url = `${V2_API_BASE}/api/memory/recall-audit/stats?${queryParams.toString()}`;
  const response = await fetch(url);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  const result = await response.json();
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(result, null, 2),
      },
    ],
    details: result,
  };
}

async function handleFeedback(params: any) {
  if (!params.audit_id) {
    throw new Error("audit_id is required for feedback action");
  }
  if (!params.memory_id) {
    throw new Error("memory_id is required for feedback action");
  }
  if (!params.feedback) {
    throw new Error("feedback is required for feedback action");
  }

  const url = `${V2_API_BASE}/api/memory/recall-audit/${params.audit_id}/feedback`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      memory_id: params.memory_id,
      feedback: params.feedback,
      feedback_by: "agent", // 硬编码 agent 标注
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }

  const result = await response.json();
  return {
    content: [
      {
        type: "text" as const,
        text: `Feedback recorded: ${params.feedback} for memory ${params.memory_id}`,
      },
    ],
    details: result,
  };
}
