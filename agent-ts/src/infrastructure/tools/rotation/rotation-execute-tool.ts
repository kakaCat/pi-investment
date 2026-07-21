/**
 * Rotation Execute Tool - 执行策略轮动
 *
 * 轮动决策链第三步：真正执行轮动操作。
 * 执行后返回新策略组合、持仓状态、决策ID。
 *
 * 反馈节点设计：
 * - 返回执行成功/失败的动作明细
 * - 返回执行后的新策略组合
 * - 返回执行后的持仓状态
 * - 返回 decision_id 用于后续追踪
 * - 包含"下一步建议"引导 Agent 记录决策
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const rotationExecuteTool: ToolDefinition = {
  name: "rotation_execute",
  label: "轮动执行",
  description:
    "真正执行策略轮动 — 轮动决策链第三步。\n\n" +
    "执行后返回：\n" +
    "  • 成功/失败的动作明细\n" +
    "  • 新的活跃策略组合\n" +
    "  • 执行后的持仓状态\n" +
    "  • decision_id（用于后续追踪）\n\n" +
    "使用场景：\n" +
    "  • 确认 rotation_simulate 结果后执行\n" +
    "  • 否决轮动（decision='reject'）\n\n" +
    "下一步：执行后调用 decision_record 记录决策原因。",

  parameters: Type.Object({
    actions: Type.Array(
      Type.Object({
        type: Type.String({ description: "动作类型: activate/deactivate/adjust_weight" }),
        strategy_id: Type.Number({ description: "策略ID" }),
        reason: Type.Optional(Type.String({ description: "原因" })),
        new_weight: Type.Optional(Type.Number({ description: "新权重" })),
      }),
      { description: "轮动动作列表" }
    ),
    decision: Type.Union(
      [Type.Literal("approve"), Type.Literal("partial"), Type.Literal("reject")],
      { description: "决策: approve=全部执行, partial=部分执行, reject=否决" }
    ),
    reason: Type.String({ description: "决策原因（记录到审计日志）" }),
  }),

  execute: async (_toolCallId: string, params: Record<string, unknown>) => {
    try {
      const actions = params.actions as Array<Record<string, unknown>>;
      const decision = params.decision as string;
      const reason = params.reason as string;

      if (!decision) {
        return {
          content: [{
            type: "text" as const,
            text: "❌ 请提供 decision 参数（approve/partial/reject）"
          }],
          details: null
        };
      }

      const result = await runQuantV2("agent.rotation_execute", {
        actions: actions || [],
        decision,
        reason: reason || "",
      });

      if (!result.ok || !result.data) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 轮动执行失败: ${result.error?.message || "未知错误"}`
          }],
          details: null
        };
      }

      const data = result.data as any;
      const formattedOutput = formatExecuteResult(data, decision);

      return {
        content: [{ type: "text" as const, text: formattedOutput }],
        details: data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 轮动执行失败: ${errorMsg}\n\n提示: 请检查 quantsys-v2 服务是否运行`
        }],
        details: null
      };
    }
  }
};

function formatExecuteResult(data: any, decision: string): string {
  let output = "";

  // 否决情况
  if (decision === "reject") {
    output += "## 🚫 轮动已否决\n\n";
    output += `**否决原因**: ${data.reason || "未提供"}\n`;
    output += `**决策ID**: ${data.decision_id}\n\n`;
    output += `### 👉 建议下一步\n\n`;
    output += "1. 调用 `decision_record` 记录否决原因\n";
    output += "2. 持续观察市场，等待下次轮动信号\n";
    return output;
  }

  output += "## ✅ 轮动执行完成\n\n";
  output += `**决策ID**: ${data.decision_id}\n`;
  output += `**决策类型**: ${decision === "approve" ? "全部执行" : "部分执行"}\n`;
  output += `**原因**: ${data.reason || "-"}\n\n`;

  // 执行结果
  output += `### 📋 执行明细\n\n`;
  if (data.executed_actions?.length > 0) {
    output += `**成功执行** (${data.executed_actions.length} 个):\n`;
    for (const a of data.executed_actions) {
      const icon = a.type === "activate" ? "🟢" : a.type === "deactivate" ? "🔴" : "🟡";
      output += `- ${icon} ${a.type}: 策略 ${a.strategy_id}${a.reason ? ` — ${a.reason}` : ""}\n`;
    }
  }
  if (data.failed_actions?.length > 0) {
    output += `\n**执行失败** (${data.failed_actions.length} 个):\n`;
    for (const f of data.failed_actions) {
      output += `- ❌ ${f.action || f.type}: ${f.error || f.reason || "未知错误"}\n`;
    }
  }
  output += "\n";

  // 新策略组合
  if (data.new_active_strategies?.length > 0) {
    output += `### 📈 新策略组合\n\n`;
    output += "| ID | 名称 | 类型 |\n";
    output += "|-----|------|------|\n";
    for (const s of data.new_active_strategies) {
      output += `| ${s.id} | ${s.name} | ${s.type} |\n`;
    }
    output += "\n";
  }

  // 持仓状态
  if (data.portfolio_state) {
    output += `### 💰 持仓状态\n\n`;
    output += `- 现金: ¥${data.portfolio_state.cash?.toLocaleString() || "N/A"}\n`;
    output += `- 总值: ¥${data.portfolio_state.total_value?.toLocaleString() || "N/A"}\n`;
    output += `- 持仓数: ${data.portfolio_state.positions_count ?? "N/A"}\n\n`;
  }

  // 下一步
  output += `### 👉 建议下一步\n\n`;
  output += "1. 调用 `decision_record` 记录决策原因和预期\n";
  output += "2. 通过 `feishu_notify` 通知用户轮动结果\n";
  output += "3. 明日调用 `rotation_verify` 验证执行效果\n";

  return output;
}
