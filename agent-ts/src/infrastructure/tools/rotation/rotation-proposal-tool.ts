/**
 * Rotation Proposal Tool - 获取策略轮动方案
 *
 * 轮动决策链第一步：获取完整上下文供 Agent 多步推理。
 * 返回市场风格、策略表现、轮动建议、约束条件。
 *
 * 反馈节点设计：
 * - 返回结构化上下文（不是 success/fail）
 * - 包含"下一步建议"引导 Agent 调用链
 * - 包含策略表现对比数据
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const rotationProposalTool: ToolDefinition = {
  name: "rotation_proposal",
  label: "轮动方案",
  description:
    "获取策略轮动方案 — 轮动决策链第一步。\n\n" +
    "返回完整上下文：\n" +
    "  • 市场风格 + 置信度 + 历史变化\n" +
    "  • 当前策略组合 + 近期表现\n" +
    "  • 轮动建议 + 预期影响\n" +
    "  • 约束条件（冷却期等）\n\n" +
    "使用场景：\n" +
    "  • 收到 strategy_rotation 事件后首先调用\n" +
    "  • 盘前分析时检查是否需要轮动\n\n" +
    "下一步：看到结果后，调用 rotation_simulate 模拟执行。",

  parameters: Type.Object({}),

  execute: async (_toolCallId: string, _params: Record<string, unknown>) => {
    try {
      const result = await runQuantV2("agent.rotation_proposal");

      if (!result.ok || !result.data) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 获取轮动方案失败: ${result.error?.message || "未知错误"}`
          }],
          details: null
        };
      }

      const data = result.data as any;
      const formattedOutput = formatProposalResult(data);

      return {
        content: [{ type: "text" as const, text: formattedOutput }],
        details: data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 获取轮动方案失败: ${errorMsg}\n\n提示: 请检查 quantsys-v2 服务是否运行`
        }],
        details: null
      };
    }
  }
};

function formatProposalResult(data: any): string {
  let output = "## 📊 策略轮动方案\n\n";

  // 市场风格
  const style = data.market_style || "unknown";
  const confidence = ((data.style_confidence || 0) * 100).toFixed(1);
  const duration = data.style_duration_days || 0;

  output += `### 🎯 市场风格\n\n`;
  output += `- **当前风格**: ${getStyleEmoji(style)} ${style}\n`;
  output += `- **置信度**: ${confidence}%\n`;
  output += `- **持续天数**: ${duration} 天\n`;

  // 风格历史
  if (data.style_history?.length > 0) {
    output += `- **近期变化**: `;
    output += data.style_history.slice(0, 3).map((h: any) =>
      `${h.date?.split("T")[0] || h.date}: ${h.style}`
    ).join(" → ");
    output += "\n";
  }
  output += "\n";

  // 当前策略组合
  output += `### 📈 当前策略组合\n\n`;
  if (data.active_strategies?.length > 0) {
    output += "| 策略 | 类型 | 权重 | 7日收益 | 30日收益 | 胜率 |\n";
    output += "|------|------|------|---------|----------|------|\n";
    for (const s of data.active_strategies) {
      const r7d = ((s.recent_return_7d || 0) * 100).toFixed(2);
      const r30d = ((s.recent_return_30d || 0) * 100).toFixed(2);
      const wr = ((s.win_rate || 0) * 100).toFixed(1);
      output += `| ${s.name} | ${s.type} | ${s.weight?.toFixed(2)} | ${r7d}% | ${r30d}% | ${wr}% |\n`;
    }
  } else {
    output += "暂无活跃策略\n";
  }
  output += "\n";

  // 轮动建议
  const proposal = data.proposal;
  output += `### 💡 轮动建议\n\n`;
  if (proposal?.needs_rotation) {
    output += `**需要轮动**: ✅ 是\n`;
    output += `**触发原因**: ${proposal.trigger}\n`;
    output += `**摘要**: ${proposal.summary}\n\n`;

    if (proposal.actions?.length > 0) {
      output += "**建议动作**:\n";
      for (const action of proposal.actions) {
        const icon = action.action === "activate" ? "🟢" :
                     action.action === "deactivate" ? "🔴" : "🟡";
        output += `- ${icon} ${action.action}: ${action.strategy_name || action.strategy_id} — ${action.reason}\n`;
      }
      output += "\n";
    }

    if (proposal.expected_impact) {
      output += `**预期影响**: 换仓 ${proposal.expected_impact.position_change_count} 个，`;
      output += `成本约 ¥${proposal.expected_impact.estimated_cost}，`;
      output += `风险变化: ${proposal.expected_impact.risk_change}\n\n`;
    }
  } else {
    output += `**需要轮动**: ❌ 否\n`;
    output += `**原因**: ${proposal?.summary || "市场稳定"}\n\n`;
  }

  // 约束条件
  const constraints = data.constraints;
  if (constraints) {
    output += `### ⚠️ 约束条件\n\n`;
    output += `- 冷却期: ${constraints.in_cooldown ? "🔒 冷却中" : "✅ 可操作"}\n`;
    output += `- 最大活跃策略: ${constraints.max_active}\n`;
    if (constraints.last_rotation_date) {
      output += `- 上次轮动: ${constraints.last_rotation_date}\n`;
    }
    output += "\n";

    // 近期被否决的方案（反馈闭环）
    if (constraints.recent_rejects?.length > 0) {
      output += `### 🚫 近期被否决的方案\n\n`;
      output += `以下方案在 14 天内被否决，不要重复推荐：\n`;
      for (const r of constraints.recent_rejects) {
        const actions = (r.rejected_actions || []).map((a: any) =>
          `${a.action || a.type} 策略${a.strategy_id}`
        ).join(", ");
        output += `- ${r.date}: ${actions} — 否决原因: "${r.reason || '未提供'}"\n`;
      }
      output += "\n";
    }
  }

  // 下一步建议
  output += `### 👉 建议下一步\n\n`;
  if (proposal?.needs_rotation) {
    output += "1. 调用 `rotation_simulate` 模拟执行，查看具体交易和风险变化\n";
    output += "2. 调用 `market_style_detect` 独立验证市场风格判断\n";
    output += "3. 调用 `portfolio_status` 确认当前持仓\n";
    output += "4. 综合判断后调用 `rotation_execute` 执行或否决\n";
  } else {
    output += "当前无需轮动，可继续观察市场变化。\n";
  }

  return output;
}

function getStyleEmoji(style: string): string {
  const map: Record<string, string> = {
    bull: "🐂",
    bear: "🐻",
    oscillation: "↔️",
    value: "💎",
    growth: "🌱",
    cycle: "🔄",
  };
  return map[style] || "❓";
}
