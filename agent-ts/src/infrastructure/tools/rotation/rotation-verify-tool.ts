/**
 * Rotation Verify Tool - 验证轮动效果
 *
 * 轮动决策链第四步（复盘用）：对比轮动前后的实际表现 vs 预期。
 *
 * 反馈节点设计：
 * - 返回预期 vs 实际对比数据
 * - 返回判定（positive/neutral/negative）
 * - 返回新策略的单独表现
 * - 包含建议（保持/回滚/调整）
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

export const rotationVerifyTool: ToolDefinition = {
  name: "rotation_verify",
  label: "轮动验证",
  description:
    "验证之前轮动决策的效果 — 轮动决策链第四步（复盘用）。\n\n" +
    "返回：\n" +
    "  • 轮动日期 + 距今天数\n" +
    "  • 预期 vs 实际收益对比\n" +
    "  • 判定（positive/neutral/negative）\n" +
    "  • 新策略的单独表现\n" +
    "  • 建议（保持/回滚/调整）\n\n" +
    "使用场景：\n" +
    "  • 盘后复盘时检查近期轮动效果\n" +
    "  • 周度评估策略组合表现\n" +
    "  • daily_review 事件触发时调用",

  parameters: Type.Object({
    rotation_date: Type.Optional(
      Type.String({ description: "轮动日期（YYYY-MM-DD），不填则验证最近一次" })
    ),
  }),

  execute: async (_toolCallId: string, params: Record<string, unknown>) => {
    try {
      const rotationDate = params.rotation_date as string | undefined;

      const queryParams: Record<string, string> = {};
      if (rotationDate) {
        queryParams.rotation_date = rotationDate;
      }

      const result = await runQuantV2("agent.rotation_verify", queryParams);

      if (!result.ok || !result.data) {
        return {
          content: [{
            type: "text" as const,
            text: `❌ 验证轮动效果失败: ${result.error?.message || "未知错误"}\n\n` +
              "可能原因：近期没有轮动记录，或 quantsys-v2 服务未运行"
          }],
          details: null
        };
      }

      const data = result.data as any;
      const formattedOutput = formatVerifyResult(data);

      return {
        content: [{ type: "text" as const, text: formattedOutput }],
        details: data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 验证轮动效果失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

function formatVerifyResult(data: any): string {
  let output = "## 🔍 轮动效果验证\n\n";

  // 基本信息
  output += `**轮动日期**: ${data.rotation_date || "N/A"}\n`;
  output += `**距今天数**: ${data.days_since ?? "N/A"} 天\n\n`;

  // 预期 vs 实际
  output += `### 📊 预期 vs 实际\n\n`;
  output += "| 指标 | 预期 | 实际 | 判定 |\n";
  output += "|------|------|------|------|\n";

  const expected = data.expected || {};
  const actual = data.actual || {};

  if (expected.return_7d !== undefined || actual.return_since !== undefined) {
    const expRet = ((expected.return_7d || 0) * 100).toFixed(2);
    const actRet = ((actual.return_since || 0) * 100).toFixed(2);
    const retIcon = (actual.return_since || 0) >= (expected.return_7d || 0) ? "✅" : "⚠️";
    output += `| 收益率 | ${expRet}% | ${actRet}% | ${retIcon} |\n`;
  }

  if (actual.max_drawdown !== undefined) {
    const mdd = ((actual.max_drawdown || 0) * 100).toFixed(2);
    output += `| 最大回撤 | - | ${mdd}% | ${Math.abs(actual.max_drawdown) < 0.03 ? "✅" : "⚠️"} |\n`;
  }

  if (expected.risk_level) {
    output += `| 风险水平 | ${expected.risk_level} | ${actual.risk_level || "-"} | - |\n`;
  }
  output += "\n";

  // 判定
  const verdict = data.verdict || "unknown";
  const verdictIcon = verdict === "positive" ? "✅" : verdict === "negative" ? "❌" : "➡️";
  const verdictText = verdict === "positive" ? "正面" : verdict === "negative" ? "负面" : "中性";
  output += `### ${verdictIcon} 综合判定: ${verdictText}\n\n`;

  // 新策略表现
  if (data.new_strategies_performance?.length > 0) {
    output += `### 📈 新策略表现\n\n`;
    output += "| 策略 | 收益率 | 贡献 |\n";
    output += "|------|--------|------|\n";
    for (const s of data.new_strategies_performance) {
      const ret = ((s.return_since || 0) * 100).toFixed(2);
      output += `| ${s.name || s.strategy_id} | ${ret}% | ${s.contribution || "-"} |\n`;
    }
    output += "\n";
  }

  // 建议
  if (data.recommendation) {
    output += `### 💡 建议\n\n${data.recommendation}\n\n`;
  }

  // 下一步
  output += `### 👉 建议下一步\n\n`;
  if (verdict === "negative") {
    output += "1. ⚠️ 轮动效果不佳，考虑调用 `rotation_proposal` 查看是否需要回滚\n";
    output += "2. 调用 `experience_write` 记录此次教训\n";
    output += "3. 通过 `feishu_notify` 告知用户\n";
  } else if (verdict === "positive") {
    output += "1. 轮动效果良好，保持当前组合\n";
    output += "2. 调用 `experience_write` 记录成功经验\n";
  } else {
    output += "1. 继续观察，暂不调整\n";
    output += "2. 过几天再次调用 `rotation_verify` 复查\n";
  }

  return output;
}
