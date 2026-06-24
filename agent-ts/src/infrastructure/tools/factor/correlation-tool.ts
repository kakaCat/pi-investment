/**
 * Factor Correlation Tool - 因子相关性分析
 *
 * 功能：分析多个因子之间的相关性，优化因子组合
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorCorrelationParams {
  factors: string[];
  symbols?: string[];
  start_date: string;
  end_date: string;
  method?: "pearson" | "spearman";
}

export const factorCorrelationTool: ToolDefinition = {
  name: "factor_correlation",
  label: "因子相关性分析",
  description:
    "分析多个因子之间的相关性矩阵。" +
    "\n\n🔬 **核心功能**：" +
    "\n  • 计算因子之间的相关系数" +
    "\n  • 支持 Pearson 和 Spearman 相关性" +
    "\n  • 生成相关性矩阵热力图数据" +
    "\n  • 识别高度相关的因子对" +
    "\n\n💡 **使用场景**：" +
    "\n  • 多因子组合前检查相关性" +
    "\n  • 避免选择高度相关的因子（冗余）" +
    "\n  • 寻找互补的因子组合" +
    "\n  • 因子降维和去冗余" +
    "\n\n📊 **相关性阈值参考**：" +
    "\n  • |ρ| > 0.8 - 高度相关（建议只保留一个）" +
    "\n  • 0.5 < |ρ| < 0.8 - 中度相关（谨慎使用）" +
    "\n  • |ρ| < 0.5 - 低相关（可组合使用）" +
    "\n\n⚠️ **注意**：相关性基于历史数据计算，未来可能变化",

  parameters: Type.Object({
    factors: Type.Array(
      Type.String(),
      {
        description: "要分析的因子列表（至少2个），如 ['rsi14', 'macd', 'momentum_20d']"
      }
    ),
    symbols: Type.Optional(
      Type.Array(
        Type.String(),
        {
          description: "股票池范围（可选），A股6位代码列表。不提供则使用默认股票池（沪深300成分股）"
        }
      )
    ),
    start_date: Type.String({
      description: "开始日期，格式 YYYY-MM-DD（如 2024-01-01）"
    }),
    end_date: Type.String({
      description: "结束日期，格式 YYYY-MM-DD（如 2024-12-31）"
    }),
    method: Type.Optional(
      Type.String({
        description: "相关性计算方法（可选，默认 pearson）。pearson=线性相关，spearman=秩相关（对异常值更稳健）",
        enum: ["pearson", "spearman"]
      })
    )
  }),

  execute: async (_toolCallId, params: FactorCorrelationParams) => {
    const { factors, symbols, start_date, end_date, method = "pearson" } = params;

    // 参数验证
    if (factors.length < 2) {
      return {
        content: [{
          type: "text" as const,
          text: "❌ 至少需要2个因子才能计算相关性"
        }],
        details: null
      };
    }

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/analysis/factor-correlation`;

      const requestBody = {
        factors,
        symbols,
        start_date,
        end_date,
        method
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
        throw new Error((result as any).error || '计算因子相关性失败');
      }

      const data = (result as any).data;
      const correlationMatrix = data.correlation_matrix;
      const highCorrelations = data.high_correlations || [];

      // 格式化相关性矩阵
      const matrixText = formatCorrelationMatrix(factors, correlationMatrix);

      // 格式化高相关因子对
      let highCorrText = "";
      if (highCorrelations.length > 0) {
        highCorrText = "\n\n⚠️ **高度相关因子对** (|ρ| > 0.7):\n" +
          highCorrelations
            .map((pair: any) => `  • ${pair.factor1} ↔ ${pair.factor2}: ${pair.correlation.toFixed(3)}`)
            .join('\n');
      }

      // 生成建议
      const suggestions = generateSuggestions(highCorrelations, factors);

      return {
        content: [{
          type: "text" as const,
          text: `📊 因子相关性分析结果\n\n` +
                `分析期间: ${start_date} ~ ${end_date}\n` +
                `计算方法: ${method}\n` +
                `股票数量: ${data.n_stocks || 'N/A'}\n\n` +
                `${matrixText}${highCorrText}\n\n` +
                `${suggestions}`
        }],
        details: data
      };

    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 格式化相关性矩阵
 */
function formatCorrelationMatrix(factors: string[], matrix: number[][]): string {
  const n = factors.length;
  
  // 表头
  let text = "相关性矩阵:\n\n";
  text += "         " + factors.map(f => f.padEnd(8).slice(0, 8)).join(" ") + "\n";
  text += "-".repeat(9 + factors.length * 9) + "\n";

  // 矩阵数据
  for (let i = 0; i < n; i++) {
    text += factors[i].padEnd(8).slice(0, 8) + " ";
    for (let j = 0; j < n; j++) {
      const val = matrix[i][j];
      const formatted = val.toFixed(2).padStart(6);
      text += formatted + "   ";
    }
    text += "\n";
  }

  return text;
}

/**
 * 生成因子组合建议
 */
function generateSuggestions(highCorrelations: any[], factors: string[]): string {
  if (highCorrelations.length === 0) {
    return "✅ **建议**: 所有因子相关性较低，可以组合使用";
  }

  const correlatedFactors = new Set<string>();
  highCorrelations.forEach((pair: any) => {
    correlatedFactors.add(pair.factor1);
    correlatedFactors.add(pair.factor2);
  });

  const suggestions = [
    "💡 **优化建议**:",
    "  • 高度相关的因子提供冗余信息，建议只保留一个",
    "  • 可以选择 IC 更高或更稳定的因子",
    "  • 或使用主成分分析（PCA）进行因子降维"
  ];

  if (correlatedFactors.size < factors.length) {
    const independentFactors = factors.filter(f => !correlatedFactors.has(f));
    suggestions.push(`  • 独立因子（推荐保留）: ${independentFactors.join(', ')}`);
  }

  return suggestions.join('\n');
}
