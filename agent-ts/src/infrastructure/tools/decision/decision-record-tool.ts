/**
 * Decision Record Tool - 决策记录工具
 *
 * 将Agent的决策记录到 quantsys-v2（POST /api/decisions/record），
 * 形成审计轨迹，供 web-frontend 决策历史/报告页面展示和后续学习。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { getSessionContext } from "../../../api/gateway/session-events.js";

const V2_API_BASE = process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001";

interface DecisionRecordParams {
  decision_type: string;
  reasoning: string;
  context?: Record<string, any>;
  parameters?: Record<string, any>;
  related_entity_type?: string;
  related_entity_id?: string;
}

export const decisionRecordTool: ToolDefinition = {
  name: "decision_record",
  description: `记录Agent的投资决策到后端审计系统

用途：
- 每次做出重要决策（建池、调仓、选股、风控）后记录决策上下文
- 形成完整的决策审计轨迹，供复盘和学习
- web 监控端可展示决策历史和推理过程

何时使用：
- 创建/刷新/删除股票池后
- 做出买入/卖出决策后
- 执行风控操作后
- 任何值得复盘的重要判断

参数说明：
- decision_type: 决策类型（create_pool/update_pool/refresh_pool/add_stock/remove_stock/select_strategy/screening/auto_risk_control/auto_capture_opportunity 等）
- reasoning: 决策理由（为什么这么做，必填）
- context: 决策上下文（市场环境、触发原因等）
- parameters: 决策参数（具体操作内容）
- related_entity_type/related_entity_id: 关联实体（如 pool/5）

返回内容：
- 决策ID（decision_id）
- 记录状态`,

  parameters: Type.Object({
    decision_type: Type.String({
      description: "决策类型（如 create_pool、refresh_pool、add_stock、remove_stock、auto_risk_control）"
    }),
    reasoning: Type.String({
      description: "决策理由：为什么做这个决策"
    }),
    context: Type.Optional(Type.Record(Type.String(), Type.Any(), {
      description: "决策上下文（市场阶段、触发原因等）"
    })),
    parameters: Type.Optional(Type.Record(Type.String(), Type.Any(), {
      description: "决策参数（具体操作内容）"
    })),
    related_entity_type: Type.Optional(Type.String({
      description: "关联实体类型（如 pool、stock）"
    })),
    related_entity_id: Type.Optional(Type.String({
      description: "关联实体ID"
    }))
  }),

  execute: async (_toolCallId: string, params: DecisionRecordParams) => {
    try {
      const body: Record<string, any> = {
        decision_type: params.decision_type,
        reasoning: params.reasoning,
      };
      const sessionCtx = getSessionContext();
      if (sessionCtx) body.session_key = sessionCtx.sessionKey;
      if (params.context) body.context = params.context;
      if (params.parameters) body.parameters = params.parameters;
      if (params.related_entity_type) body.related_entity_type = params.related_entity_type;
      if (params.related_entity_id) body.related_entity_id = params.related_entity_id;

      const resp = await fetch(`${V2_API_BASE}/api/decisions/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = (await resp.json()) as any;

      if (!result.success) {
        throw new Error(result.error || "记录决策失败");
      }

      const decision = result.data || {};
      const decisionId = decision.decision_id ?? "unknown";

      return {
        content: [{
          type: "text" as const,
          text: `✅ 决策已记录\n\n**决策ID**: ${decisionId}\n**类型**: ${params.decision_type}\n**理由**: ${params.reasoning}`
        }],
        details: { decision_id: decisionId, decision }
      };

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 记录决策失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};
