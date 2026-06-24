/**
 * Factor Layering Backtest Tool - L2 因子工厂层
 *
 * 因子分层回测：验证因子有效性的金标准
 *
 * 🆕 集成统一响应处理系统：回测结果自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface FactorLayeringBacktestParams {
  factor_name: string;
  symbols?: string[];
  start_date: string;
  end_date: string;
  n_quantiles?: number;
  holding_period?: number;
}

export const factorLayeringBacktestTool: ToolDefinition = {
  name: "factor_layering_backtest",
  label: "因子分层回测",
  description:
    "L2 因子工厂工具：因子分层回测验证因子有效性。" +
    "按因子值将股票分N层（默认10层），计算每层收益，分析单调性和多空组合收益。" +
    "返回因子有效性评分（0-10分）、IC统计、单调性得分。" +
    "用于验证新因子是否具有预测能力。" +
    "\n\n💾 回测结果自动保存到本地文件。",

  parameters: Type.Object({
    factor_name: Type.String({
      description: "因子名称（如 reversal_1d, momentum_6m, rsi14）"
    }),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票列表（可选，默认使用沪深300等股票池，约400只）"
      })
    ),
    start_date: Type.String({
      description: "回测起始日期（YYYY-MM-DD格式，如 2024-01-01）"
    }),
    end_date: Type.String({
      description: "回测结束日期（YYYY-MM-DD格式，如 2024-12-31）"
    }),
    n_quantiles: Type.Optional(
      Type.Number({
        description: "分层数量（可选，默认10层。建议5-10层）"
      })
    ),
    holding_period: Type.Optional(
      Type.Number({
        description: "持有期天数（可选，默认20天）"
      })
    )
  }),

  execute: async (_toolCallId: string, params: FactorLayeringBacktestParams) => {
    const { factor_name, symbols, start_date, end_date, n_quantiles, holding_period } = params;

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/backtest/factor-layering`;

      const requestBody = {
        factor_name,
        symbols,
        start_date,
        end_date,
        n_quantiles: n_quantiles || 10,
        holding_period: holding_period || 20
      };

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody),
        signal: AbortSignal.timeout(120000) // 2分钟超时
      });

      if (!response.ok) {
        const errorData: any = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(`API请求失败: ${errorData.error || response.statusText}`);
      }

      const result = await response.json();

      if (!(result as any).success) {
        throw new Error((result as any).error || '因子分层回测失败');
      }

      // 使用统一响应处理（自动持久化）
      return handleToolResponse({
        toolName: 'factor_layering_backtest',
        data: result,
        formatter: formatLayeringBacktestResult,
        metadata: {
          factor_name,
          n_quantiles: n_quantiles || 10,
          holding_period: holding_period || 20,
          period: `${start_date} ~ ${end_date}`,
        },
        threshold: 40 * 1024, // 40KB
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 格式化分层回测结果
 */
function formatLayeringBacktestResult(result: any): string {
  const lines: string[] = [];

  // 标题
  lines.push(`\n=== 因子分层回测结果 ===`);
  lines.push(`因子: ${result.factor_name}`);
  lines.push(`分层数: ${result.n_quantiles}`);
  lines.push(`回测期间: ${result.start_date} 至 ${result.end_date}`);
  lines.push(`股票数量: ${result.symbols_count}`);

  // 有效性评分
  const score = result.effectiveness_score || 0;
  lines.push(`\n📊 因子有效性评分: ${score.toFixed(1)}/10`);

  // 评级
  const rating = score >= 8 ? "⭐⭐⭐ 优秀" :
                 score >= 6 ? "⭐⭐ 良好" :
                 score >= 4 ? "⭐ 一般" : "❌ 较差";
  lines.push(`评级: ${rating}\n`);

  // 核心指标
  lines.push(`--- 核心指标 ---`);
  lines.push(`多空组合收益: ${(result.long_short_return * 100).toFixed(2)}%`);
  lines.push(`单调性得分: ${(result.monotonicity_score * 100).toFixed(1)}%`);

  const ic_stats = result.ic_stats || {};
  lines.push(`IC均值: ${(ic_stats.IC_mean || 0).toFixed(4)}`);
  lines.push(`IC信息比率: ${(ic_stats.IC_IR || 0).toFixed(2)}`);
  lines.push(`IC正比率: ${((ic_stats.IC_positive_rate || 0) * 100).toFixed(1)}%\n`);

  // 分层统计
  lines.push(`--- 分层统计 (从低到高) ---`);
  const layer_stats = result.layer_stats || {};
  const layerNames = Object.keys(layer_stats).sort();

  for (const layer of layerNames) {
    const stats = layer_stats[layer];
    lines.push(
      `${layer}: 平均收益 ${(stats.mean_return * 100).toFixed(2)}% | ` +
      `夏普 ${stats.sharpe_ratio.toFixed(2)} | ` +
      `胜率 ${(stats.win_rate * 100).toFixed(1)}%`
    );
  }

  // 使用建议
  lines.push(`\n--- 使用建议 ---`);
  if (score >= 8) {
    lines.push(`✅ 该因子具有强预测能力，建议在选股中使用`);
    lines.push(`   可用于 opportunity_scan 的动态权重模式`);
  } else if (score >= 6) {
    lines.push(`⚠️ 该因子具有一定预测能力，可与其他因子组合使用`);
    lines.push(`   建议权重不超过30%`);
  } else if (score >= 4) {
    lines.push(`⚠️ 该因子预测能力一般，建议谨慎使用`);
    lines.push(`   可作为辅助因子，权重建议10-20%`);
  } else {
    lines.push(`❌ 该因子预测能力较弱，不建议使用`);
    lines.push(`   建议寻找其他更有效的因子`);
  }

  return lines.join('\n');
}
