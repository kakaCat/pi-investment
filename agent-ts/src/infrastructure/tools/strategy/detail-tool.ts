/**
 * Strategy Detail Tool — 查询策略详情（集成统一持久化）
 *
 * 查询单个策略的详细信息，包括参数、代码、回测结果等。
 *
 * 从 quant_cli 的 strategy.get 提取为独立工具。
 *
 * 🆕 集成统一持久化：使用 handleToolResponse 自动格式化和持久化大数据
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";
import { formatStrategyDetail } from "../../adapters/quant/formatters.js";

interface DetailParams {
  strategy_id: string;
}

export const strategyDetailTool: ToolDefinition = {
  name: "strategy_detail",
  label: "策略详情",
  description:
    "查询单个策略的详细信息，包括策略参数、代码、配置和历史回测统计。" +
    "需提供 strategy_id（可通过 strategy_list 查询）。" +
    "\n\n自动显示回测统计：年化收益、夏普比率、最大回撤、性能评级等。" +
    "\n💾 大数据自动保存到本地文件，避免污染上下文。",

  parameters: Type.Object({
    strategy_id: Type.String({
      description: "策略ID（可通过 strategy_list 查询）",
    }),
  }),

  execute: async (_toolCallId, rawParams: DetailParams) => {
    try {
      // 1. 获取策略详情
      const result = await runQuantV2("strategy.get", rawParams as unknown as Record<string, unknown>);
      const data = (result as any).data ?? result;

      // 2. 获取该策略的回测统计（如果有）
      let backtestStats = null;
      try {
        const { QuantV2Client } = await import('../../adapters/quant/quant-v2-client.js');
        const client = QuantV2Client;

        // 查询回测统计
        const statsResponse = await client.get('/api/backtest/stats', {
          strategy_name: data.name
        });

        if (statsResponse.success && (statsResponse as any).data.totalBacktests > 0) {
          backtestStats = (statsResponse as any).data;
        }
      } catch (statsErr) {
        // 静默失败，不影响策略详情显示
        console.warn('获取回测统计失败:', statsErr);
      }

      // 3. 增强格式化函数，添加回测统计
      const enhancedFormatter = (strategyData: any) => {
        let output = formatStrategyDetail(strategyData);

        // 如果有回测统计，添加到输出
        if (backtestStats) {
          output += '\n\n' + '='.repeat(60) + '\n';
          output += '📊 历史回测统计\n';
          output += '='.repeat(60) + '\n';
          output += `  回测次数: ${backtestStats.totalBacktests} 次\n`;
          output += `  📈 平均年化收益: ${(backtestStats.avgReturn * 100).toFixed(2)}%\n`;
          output += `  📊 平均夏普比率: ${backtestStats.avgSharpe?.toFixed(2) || 'N/A'}\n`;
          output += `  📉 平均最大回撤: ${(backtestStats.avgMaxDrawdown * 100).toFixed(2)}%\n`;
          output += `  🏆 最佳夏普比率: ${backtestStats.bestSharpe?.toFixed(2) || 'N/A'}\n`;

          // 性能评级
          const avgSharpe = backtestStats.avgSharpe || 0;
          output += '\n⭐ 性能评级: ';
          if (avgSharpe >= 1.5) {
            output += '⭐⭐⭐⭐⭐ 优秀（推荐实盘）\n';
          } else if (avgSharpe >= 1.0) {
            output += '⭐⭐⭐⭐ 良好（可以实盘）\n';
          } else if (avgSharpe >= 0.5) {
            output += '⭐⭐⭐ 一般（需要优化）\n';
          } else {
            output += '⭐⭐ 较差（建议重新设计）\n';
          }

          output += '\n💡 提示: 使用 backtest_history 工具查看详细的历史记录\n';
        } else {
          output += '\n\n💡 提示: 该策略还没有回测记录，运行回测后可查看性能指标\n';
        }

        return output;
      };

      // 使用统一的响应处理器（自动格式化和持久化）
      return handleToolResponse({
        toolName: 'strategy_detail',
        data,
        formatter: enhancedFormatter,
        metadata: {
          strategy_id: rawParams.strategy_id,
        },
        threshold: 40 * 1024, // 40KB（策略代码可能较长）
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `查询策略详情失败: ${errorMsg}`,
        }],
        details: null,
      };
    }
  },
};
