/**
 * Rotation Simulate Tool - 模拟轮动执行
 *
 * 轮动决策链第二步：不真正执行，返回模拟交易、组合变化、风险提示。
 * Agent 可以修改 actions 后重新模拟。
 *
 * 反馈节点设计：
 * - 返回模拟交易明细（卖什么、买什么、多少钱）
 * - 返回组合前后对比（现金、持仓数、总值）
 * - 返回风险指标变化
 * - 返回警告信息（如实现亏损）
 * - 包含"下一步建议"引导 Agent 确认或修改
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const rotationSimulateTool: ToolDefinition = {
  name: "rotation_simulate",
  label: "轮动模拟",
  description:
    "模拟执行轮动方案（不真正执行）— 轮动决策链第二步。\n\n" +
    "返回：\n" +
    "  • 模拟交易明细（卖出/买入、股数、价格）\n" +
    "  • 组合前后对比（现金、持仓数、总值）\n" +
    "  • 风险指标变化（集中度、最大仓位）\n" +
    "  • 警告信息（如实现亏损）\n\n" +
    "使用场景：\n" +
    "  • 调用 rotation_proposal 后，模拟执行查看影响\n" +
    "  • 修改 actions 后重新模拟（部分执行）\n\n" +
    "下一步：确认模拟结果后，调用 rotation_execute 真正执行。",

  parameters: Type.Object({
    actions: Type.Array(
      Type.Object({
        type: Type.String({ description: "动作类型: activate/deactivate/adjust_weight" }),
        strategy_id: Type.Number({ description: "策略ID" }),
        reason: Type.Optional(Type.String({ description: "原因" })),
        new_weight: Type.Optional(Type.Number({ description: "新权重（adjust_weight时必填）" })),
      }),
      { description: "轮动动作列表（来自 rotation_proposal 的建议，可修改）" }
    ),
  }),

  execute: async (_toolCallId: string, params: Record<string, unknown>) => {
    try {
      const actions = params.actions as Array<Record<string, unknown>>;

      if (!actions || actions.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: "❌ 请提供至少一个轮动动作。\n\n提示: 先调用 rotation_proposal 获取建议的 actions。"
          }],
          details: null
        };
      }

      const result = await runQuantV2("agent.rotation_simulate", { actions });

      if (!result.ok || !result.data) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 模拟执行失败: ${result.error?.message || "未知错误"}`
          }],
          details: null
        };
      }

      const data = result.data as any;
      const formattedOutput = formatSimulateResult(data, actions);

      return {
        content: [{ type: "text" as const, text: formattedOutput }],
        details: data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 模拟执行失败: ${errorMsg}\n\n提示: 请检查 quantsys-v2 服务是否运行`
        }],
        details: null
      };
    }
  }
};

function formatSimulateResult(data: any, actions: Array<Record<string, unknown>>): string {
  let output = "## 🧪 轮动模拟结果\n\n";

  // 模拟交易
  output += `### 📋 模拟交易\n\n`;
  if (data.simulated_trades?.length > 0) {
    output += "| 股票 | 操作 | 股数 | 价格 | 原因 |\n";
    output += "|------|------|------|------|------|\n";
    for (const t of data.simulated_trades) {
      const icon = t.action === "sell" ? "🔴卖" : "🟢买";
      output += `| ${t.symbol} | ${icon} | ${t.shares} | ¥${t.price} | ${t.reason || "-"} |\n`;
    }
  } else {
    output += "无模拟交易（可能只是权重调整）\n";
  }
  output += "\n";

  // 组合对比
  output += `### 📊 组合变化\n\n`;
  const before = data.portfolio_before;
  const after = data.portfolio_after;
  if (before && after) {
    output += "| 指标 | 执行前 | 执行后 | 变化 |\n";
    output += "|------|--------|--------|------|\n";
    output += `| 现金 | ¥${fmt(before.cash)} | ¥${fmt(after.cash)} | ${delta(after.cash - before.cash)} |\n`;
    output += `| 持仓数 | ${before.positions} | ${after.positions} | ${delta(after.positions - before.positions)} |\n`;
    output += `| 总值 | ¥${fmt(before.total)} | ¥${fmt(after.total)} | ${delta(after.total - before.total)} |\n`;
  }
  output += "\n";

  // 成本
  if (data.estimated_cost) {
    output += `**预估交易成本**: ¥${fmt(data.estimated_cost)}\n\n`;
  }

  // 风险变化
  if (data.risk_metrics_change) {
    output += `### ⚖️ 风险变化\n\n`;
    const risk = data.risk_metrics_change;
    for (const [key, val] of Object.entries(risk)) {
      const v = val as any;
      if (v.before !== undefined && v.after !== undefined) {
        const arrow = v.after > v.before ? "📈" : v.after < v.before ? "📉" : "➡️";
        output += `- ${key}: ${(v.before * 100).toFixed(1)}% → ${(v.after * 100).toFixed(1)}% ${arrow}\n`;
      }
    }
    output += "\n";
  }

  // 警告
  if (data.warnings?.length > 0) {
    output += `### ⚠️ 警告\n\n`;
    for (const w of data.warnings) {
      output += `- ⚠️ ${w}\n`;
    }
    output += "\n";
  }

  // 下一步
  output += `### 👉 建议下一步\n\n`;
  if (data.warnings?.length > 0) {
    output += "1. ⚠️ 存在警告，请仔细评估是否接受\n";
    output += "2. 可修改 actions 后重新调用 `rotation_simulate`\n";
    output += "3. 确认无误后调用 `rotation_execute` 真正执行\n";
  } else {
    output += "1. 模拟结果正常，调用 `rotation_execute` 真正执行\n";
    output += "2. 或修改 actions 后重新模拟\n";
  }

  return output;
}

function fmt(n: number): string {
  return n?.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) || "0";
}

function delta(n: number): string {
  if (n > 0) return `+${fmt(n)}`;
  if (n < 0) return `${fmt(n)}`;
  return "0";
}
