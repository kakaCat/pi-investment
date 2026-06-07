/**
 * Risk Metrics Tool - 风险指标工具
 *
 * 基于 empyrical-reloaded 计算专业风险指标
 * 支持 8 种业界标准指标
 */

import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { calculateRiskMetrics } from "../../adapters/quant/quant-v2-client.js";
import { formatRiskMetrics } from "../../adapters/quant/formatters.js";
import { wrapToolExecution } from "../shared/error-handler.js";

interface RiskMetricsParams {
  returns: number[];
  benchmark_returns?: number[];
  risk_free_rate?: number;
}

export const riskMetricsTool: ToolDefinition = {
  name: "risk_metrics",
  label: "风险指标分析",
  description:
    "计算投资组合或策略的专业风险指标（基于 empyrical-reloaded）。" +
    "\n\n📊 **支持的指标**（8种业界标准）：" +
    "\n  • 夏普比率（Sharpe Ratio）- 风险调整后收益" +
    "\n  • 索提诺比率（Sortino Ratio）- 下行风险专用" +
    "\n  • 卡尔马比率（Calmar Ratio）- 最大回撤调整收益" +
    "\n  • 最大回撤（Max Drawdown）- 历史最大损失" +
    "\n  • Alpha/Beta - 相对基准的超额收益和系统性风险" +
    "\n  • VaR (95%) - 尾部风险（Value at Risk）" +
    "\n  • CVaR (95%) - 条件 VaR（尾部期望）" +
    "\n  • 年化收益率/波动率 - 标准化度量" +
    "\n\n🎯 **使用场景**：" +
    "\n  • 评估策略的风险收益特征" +
    "\n  • 对比不同策略的风险调整后表现" +
    "\n  • 计算相对基准的 Alpha 和 Beta" +
    "\n  • 监控组合的尾部风险" +
    "\n\n💡 **输入说明**：" +
    "\n  • returns: 日收益率序列（必填）" +
    "\n  • benchmark_returns: 基准收益率（可选，用于 Alpha/Beta）" +
    "\n  • risk_free_rate: 年化无风险利率（可选，默认 2%）" +
    "\n\n📈 **指标解读**：" +
    "\n  • 夏普比率 > 1: 优秀，0-1: 良好，< 0: 差" +
    "\n  • 索提诺比率: 只惩罚下行波动，比夏普更合理" +
    "\n  • 卡尔马比率: 收益/最大回撤，衡量回撤调整后收益" +
    "\n  • VaR: 95%置信度下的最大损失" +
    "\n  • CVaR: 超过VaR的平均损失（尾部期望）",

  parameters: Type.Object({
    returns: Type.Array(Type.Number(), {
      description: "日收益率序列（如 [0.01, -0.02, 0.015, ...]）"
    }),
    benchmark_returns: Type.Optional(
      Type.Array(Type.Number(), {
        description: "基准收益率序列（可选，用于计算 Alpha/Beta）"
      })
    ),
    risk_free_rate: Type.Optional(
      Type.Number({
        description: "年化无风险利率（可选，默认 0.02 即 2%）",
        default: 0.02
      })
    )
  }),

  execute: async (_toolCallId: string, params: RiskMetricsParams) => {
    return wrapToolExecution(
      async () => {
        // 验证参数
        if (!params.returns || params.returns.length === 0) {
          throw new Error("returns 参数不能为空");
        }

        if (params.returns.length < 10) {
          throw new Error("收益率序列至少需要 10 个数据点才能计算有效的风险指标");
        }

        // 调用 API
        const result = await calculateRiskMetrics({
          returns: params.returns,
          benchmark_returns: params.benchmark_returns,
          risk_free_rate: params.risk_free_rate || 0.02
        });

        // 格式化输出
        const formatted = formatRiskMetrics(result);

        // 添加数据统计
        let output = `✅ 风险指标计算完成\n\n`;
        output += `📈 数据统计:\n`;
        output += `  样本数量: ${params.returns.length}\n`;
        if (params.benchmark_returns) {
          output += `  基准数据: ${params.benchmark_returns.length} 个数据点\n`;
        }
        output += `  无风险利率: ${((params.risk_free_rate || 0.02) * 100).toFixed(2)}%\n`;
        output += `\n${formatted}`;

        // 添加使用建议
        output += `\n\n💡 使用建议:\n`;
        if (result.sharpe_ratio > 1) {
          output += `  • 夏普比率优秀 (${result.sharpe_ratio.toFixed(4)})，风险调整后收益表现良好\n`;
        } else if (result.sharpe_ratio > 0) {
          output += `  • 夏普比率良好 (${result.sharpe_ratio.toFixed(4)})，有改进空间\n`;
        } else {
          output += `  • ⚠️ 夏普比率为负 (${result.sharpe_ratio.toFixed(4)})，建议重新评估策略\n`;
        }

        if (Math.abs(result.max_drawdown) > 0.2) {
          output += `  • ⚠️ 最大回撤较大 (${(result.max_drawdown * 100).toFixed(2)}%)，建议加强风险控制\n`;
        } else if (Math.abs(result.max_drawdown) > 0.1) {
          output += `  • 最大回撤适中 (${(result.max_drawdown * 100).toFixed(2)}%)，可接受范围\n`;
        } else {
          output += `  • 最大回撤控制良好 (${(result.max_drawdown * 100).toFixed(2)}%)\n`;
        }

        if (result.alpha !== undefined) {
          if (result.alpha > 0) {
            output += `  • ✅ 产生正 Alpha (${(result.alpha * 100).toFixed(4)}%)，跑赢基准\n`;
          } else {
            output += `  • Alpha 为负 (${(result.alpha * 100).toFixed(4)}%)，未跑赢基准\n`;
          }
        }

        return output;
      },
      {
        toolName: "risk_metrics",
        errorSuggestion:
          "请确保:\n" +
          "1. returns 是日收益率序列（不是价格）\n" +
          "2. 至少提供 10 个数据点\n" +
          "3. 如果提供 benchmark_returns，长度应与 returns 相同\n" +
          "4. 收益率应为小数形式（如 0.01 表示 1%）"
      }
    );
  },
};
