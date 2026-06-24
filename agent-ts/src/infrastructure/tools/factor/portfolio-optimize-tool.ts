/**
 * Factor Portfolio Optimize Tool - 因子组合优化
 *
 * 功能：从候选因子中自动选择最优组合
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorPortfolioOptimizeParams {
  candidate_factors: string[];
  symbols?: string[];
  start_date: string;
  end_date: string;
  max_factors?: number;
  optimization_target?: "ic" | "sharpe" | "monotonicity" | "combined";
  min_ic?: number;
  max_correlation?: number;
}

export const factorPortfolioOptimizeTool: ToolDefinition = {
  name: "factor_portfolio_optimize",
  label: "因子组合优化",
  description:
    "从候选因子中自动选择最优组合。" +
    "\n\n🎯 **核心功能**：" +
    "\n  • 从多个候选因子中筛选最优组合" +
    "\n  • 基于 IC、Sharpe、单调性等指标优化" +
    "\n  • 自动去除高相关因子（去冗余）" +
    "\n  • 输出最优因子及权重" +
    "\n\n📊 **优化目标**：" +
    "\n  • ic - 最大化信息系数（预测能力）" +
    "\n  • sharpe - 最大化夏普比率（风险调整收益）" +
    "\n  • monotonicity - 最大化单调性（分层效果）" +
    "\n  • combined - 综合评分（推荐，默认）" +
    "\n\n💡 **使用场景**：" +
    "\n  • 多因子策略开发：从10个候选中选3-5个" +
    "\n  • 因子降维：去除冗余因子" +
    "\n  • 自动化因子选择：节省手动验证时间" +
    "\n\n⚙️ **优化策略**：" +
    "\n  1. 计算每个因子的有效性评分" +
    "\n  2. 过滤低质量因子（IC < min_ic）" +
    "\n  3. 计算因子相关性矩阵" +
    "\n  4. 贪心选择：逐个添加最优因子，确保相关性低" +
    "\n  5. 输出最优组合及权重",

  parameters: Type.Object({
    candidate_factors: Type.Array(
      Type.String(),
      {
        description: "候选因子列表（至少3个），如 ['rsi14', 'macd', 'momentum_20d', 'reversal_1d', 'volatility_20']"
      }
    ),
    symbols: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "股票池范围（可选），A股6位代码列表。不提供则使用默认股票池"
        }
      )
    ),
    start_date: Type.String({
      description: "回测起始日期（YYYY-MM-DD格式）"
    }),
    end_date: Type.String({
      description: "回测结束日期（YYYY-MM-DD格式）"
    }),
    max_factors: Type.Optional(
      Type.Number({
        description: "最多选择的因子数量（可选，默认3）。建议3-5个，过多会增加复杂度"
      })
    ),
    optimization_target: Type.Optional(
      Type.String({
        description: "优化目标（可选，默认 combined）。ic=信息系数，sharpe=夏普比率，monotonicity=单调性，combined=综合评分",
        enum: ["ic", "sharpe", "monotonicity", "combined"]
      })
    ),
    min_ic: Type.Optional(
      Type.Number({
        description: "最小IC阈值（可选，默认0.02）。低于此阈值的因子会被过滤"
      })
    ),
    max_correlation: Type.Optional(
      Type.Number({
        description: "最大相关性阈值（可选，默认0.7）。高于此阈值的因子对会被去重"
      })
    )
  }),

  execute: async (_toolCallId: string, params: FactorPortfolioOptimizeParams) => {
    const {
      candidate_factors,
      symbols,
      start_date,
      end_date,
      max_factors = 3,
      optimization_target = "combined",
      min_ic = 0.02,
      max_correlation = 0.7
    } = params;

    // 参数验证
    if (candidate_factors.length < 3) {
      return {
        content: [{
          type: "text" as const,
          text: "❌ 至少需要3个候选因子才能进行优化"
        }],
        details: null
      };
    }

    if (max_factors > candidate_factors.length) {
      return {
        content: [{
          type: "text" as const,
          text: `❌ max_factors (${max_factors}) 不能大于候选因子数量 (${candidate_factors.length})`
        }],
        details: null
      };
    }

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/analysis/factor-portfolio-optimize`;

      const requestBody = {
        candidate_factors,
        symbols,
        start_date,
        end_date,
        max_factors,
        optimization_target,
        min_ic,
        max_correlation
      };

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`API 请求失败: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();

      if (!(result as any).success) {
        throw new Error((result as any).error || '因子组合优化失败');
      }

      const data = (result as any).data;

      // 格式化输出
      const selectedFactors = data.selected_factors || [];
      const rejectedFactors = data.rejected_factors || [];
      const factorScores = data.factor_scores || {};

      let outputText = `🎯 因子组合优化结果\n\n`;
      outputText += `优化参数:\n`;
      outputText += `  • 候选因子: ${candidate_factors.length} 个\n`;
      outputText += `  • 优化目标: ${optimization_target}\n`;
      outputText += `  • 最大因子数: ${max_factors}\n`;
      outputText += `  • IC阈值: ${min_ic}\n`;
      outputText += `  • 相关性阈值: ${max_correlation}\n\n`;

      // 最优组合
      if (selectedFactors.length > 0) {
        outputText += `✅ **最优因子组合** (${selectedFactors.length}个):\n`;
        selectedFactors.forEach((factor: any, index: number) => {
          outputText += `  ${index + 1}. ${factor.name}\n`;
          outputText += `     • 权重: ${(factor.weight * 100).toFixed(1)}%\n`;
          outputText += `     • IC: ${factor.ic.toFixed(3)}\n`;
          outputText += `     • 评分: ${factor.score.toFixed(2)}/10\n`;
        });
      } else {
        outputText += `⚠️ 未找到符合条件的因子组合\n`;
      }

      // 被拒绝的因子
      if (rejectedFactors.length > 0) {
        outputText += `\n❌ **被过滤因子** (${rejectedFactors.length}个):\n`;
        rejectedFactors.forEach((factor: any) => {
          outputText += `  • ${factor.name}: ${factor.reason}\n`;
        });
      }

      // 使用建议
      if (selectedFactors.length > 0) {
        outputText += `\n💡 **使用建议**:\n`;
        outputText += `  • 在策略中使用以下因子组合:\n`;
        const factorNames = selectedFactors.map((f: any) => f.name);
        outputText += `    ${factorNames.join(', ')}\n`;
        outputText += `  • 建议权重:\n`;
        selectedFactors.forEach((f: any) => {
          outputText += `    df["score"] += ${f.weight.toFixed(2)} * df["${f.name}"]\n`;
        });
      }

      return {
        content: [{
          type: "text" as const,
          text: outputText
        }],
        details: data
      };

    } catch (error) {
      return createErrorResponse(error);
    }
  }
};
