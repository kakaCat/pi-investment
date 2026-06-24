/**
 * Batch Factor Layering Backtest Tool - L2 因子工厂层
 *
 * 批量因子分层回测：快速筛选高质量因子
 *
 * 🆕 集成统一响应处理系统：批量回测结果自动持久化
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { handleToolResponse, createErrorResponse } from "../utils/index.js";

interface BatchFactorLayeringBacktestParams {
  factor_names: string[];
  symbols?: string[];
  start_date: string;
  end_date: string;
  n_quantiles?: number;
}

export const batchFactorLayeringBacktestTool: ToolDefinition = {
  name: "batch_factor_layering_backtest",
  label: "批量因子分层回测",
  description:
    "L2 因子工厂工具：批量验证多个因子的有效性。" +
    "对多个因子并行执行分层回测，返回按有效性评分排序的结果。" +
    "用于快速筛选高质量因子，对比不同因子的预测能力。" +
    "\n\n💾 批量回测结果自动保存到本地文件。",

  parameters: Type.Object({
    factor_names: Type.Array(Type.String(), {
      description: "因子名称列表（如 ['reversal_1d', 'momentum_6m', 'rsi14']）"
    }),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票列表（可选，默认使用股票池）"
      })
    ),
    start_date: Type.String({
      description: "回测起始日期（YYYY-MM-DD格式）"
    }),
    end_date: Type.String({
      description: "回测结束日期（YYYY-MM-DD格式）"
    }),
    n_quantiles: Type.Optional(
      Type.Number({
        description: "分层数量（可选，默认10层）"
      })
    )
  }),

  execute: async (_toolCallId, params: BatchFactorLayeringBacktestParams) => {
    const { factor_names, symbols, start_date, end_date, n_quantiles } = params;

    try {
      // 调用 quantsys-v2 API
      const QUANTSYS_API_URL = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = `${QUANTSYS_API_URL}/api/backtest/factor-layering/batch`;

      const requestBody = {
        factor_names,
        symbols,
        start_date,
        end_date,
        n_quantiles: n_quantiles || 10
      };

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody),
        signal: AbortSignal.timeout(300000) // 5分钟超时（批量回测较慢）
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(`API请求失败: ${errorData.error || response.statusText}`);
      }

      const result = await response.json();

      if (!(result as any).success) {
        throw new Error((result as any).error || '批量因子分层回测失败');
      }

      // 使用统一响应处理（自动持久化）
      return handleToolResponse({
        toolName: 'batch_factor_layering_backtest',
        data: result,
        formatter: formatBatchLayeringBacktestResult,
        metadata: {
          factor_count: factor_names.length,
          n_quantiles: n_quantiles || 10,
          period: `${start_date} ~ ${end_date}`,
        },
        threshold: 80 * 1024, // 80KB，批量回测数据量大
      });
    } catch (error) {
      return createErrorResponse(error);
    }
  }
};

/**
 * 格式化批量分层回测结果
 */
function formatBatchLayeringBacktestResult(result: any): string {
  const lines: string[] = [];

  // 标题
  lines.push(`\n=== 批量因子分层回测结果 ===`);
  lines.push(`测试因子数: ${result.count}`);
  lines.push(``);

  // 排名表格
  lines.push(`--- 因子有效性排名 ---`);
  lines.push(`排名 | 因子名称 | 评分 | IC均值 | 多空收益`);
  lines.push(`-----|---------|------|--------|----------`);

  const ranking = result.ranking || [];
  for (let i = 0; i < ranking.length; i++) {
    const r = ranking[i];
    const rank = i + 1;
    const emoji = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}.`;

    lines.push(
      `${emoji.padEnd(5)} | ${r.factor_name.padEnd(15)} | ` +
      `${r.effectiveness_score.toFixed(1).padEnd(4)} | ` +
      `${r.ic_mean.toFixed(4).padEnd(6)} | ` +
      `${(r.long_short_return * 100).toFixed(2)}%`
    );
  }

  // 分类汇总
  lines.push(`\n--- 分类汇总 ---`);
  const excellent = ranking.filter((r: any) => r.effectiveness_score >= 8);
  const good = ranking.filter((r: any) => r.effectiveness_score >= 6 && r.effectiveness_score < 8);
  const average = ranking.filter((r: any) => r.effectiveness_score >= 4 && r.effectiveness_score < 6);
  const poor = ranking.filter((r: any) => r.effectiveness_score < 4);

  lines.push(`⭐⭐⭐ 优秀 (≥8分): ${excellent.length}个`);
  if (excellent.length > 0) {
    lines.push(`   ${excellent.map((r: any) => r.factor_name).join(', ')}`);
  }

  lines.push(`⭐⭐ 良好 (6-8分): ${good.length}个`);
  if (good.length > 0) {
    lines.push(`   ${good.map((r: any) => r.factor_name).join(', ')}`);
  }

  lines.push(`⭐ 一般 (4-6分): ${average.length}个`);
  if (average.length > 0) {
    lines.push(`   ${average.map((r: any) => r.factor_name).join(', ')}`);
  }

  if (poor.length > 0) {
    lines.push(`❌ 较差 (<4分): ${poor.length}个`);
    lines.push(`   ${poor.map((r: any) => r.factor_name).join(', ')}`);
  }

  // 使用建议
  lines.push(`\n--- 使用建议 ---`);
  if (excellent.length > 0) {
    lines.push(`✅ 优先使用: ${excellent.slice(0, 3).map((r: any) => r.factor_name).join(', ')}`);
    lines.push(`   这些因子具有强预测能力，建议在选股中重点使用`);
  }

  if (good.length > 0) {
    lines.push(`⚠️ 组合使用: ${good.slice(0, 3).map((r: any) => r.factor_name).join(', ')}`);
    lines.push(`   可与优秀因子组合，提升选股稳定性`);
  }

  if (poor.length > 0) {
    lines.push(`❌ 不建议使用: ${poor.map((r: any) => r.factor_name).join(', ')}`);
  }

  return lines.join('\n');
}
