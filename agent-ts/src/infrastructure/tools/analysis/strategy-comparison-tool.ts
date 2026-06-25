/**
 * 策略性能对比工具
 *
 * 用途：对比多个策略的历史回测表现，找出最优策略
 */

import type { ToolDefinition } from "../index.js";
import { QuantV2Client } from '../../../infrastructure/adapters/quant/quant-v2-client.js';

const client = QuantV2Client;

interface StrategyComparisonParams {
  strategy_names: string[];  // 策略名称列表（必需）
  symbol?: string;           // 指定股票对比（可选）
  metric?: string;           // 排序指标（可选，默认 sharpe_ratio）
}

export const strategyComparisonTool: ToolDefinition = {
  name: 'strategy_performance_comparison',
  label: '策略对比',
  description: `对比多个策略的历史回测表现，生成性能排名。

使用场景：
- 对比策略271、272、273在宁德时代上的表现
- 找出夏普比率最高的策略
- 分析哪个策略最稳定（回撤最小）

支持的排序指标：sharpe_ratio（夏普比率）、annual_return（年化收益）、max_drawdown（最大回撤）`,

  parameters: {
    type: 'object',
    properties: {
      strategy_names: {
        type: 'array',
        items: { type: 'string' },
        description: '策略名称列表，例如：["新能源动量策略 v1.0", "宽松动量策略 v1.0"]'
      },
      symbol: {
        type: 'string',
        description: '指定股票代码，只对比该股票的回测结果（可选）'
      },
      metric: {
        type: 'string',
        enum: ['sharpe_ratio', 'annual_return', 'max_drawdown'],
        description: '排序指标，默认 sharpe_ratio',
        default: 'sharpe_ratio'
      }
    },
    required: ['strategy_names']
  },

  execute: async (_toolCallId: string, params: StrategyComparisonParams, _signal?: AbortSignal, _onUpdate?: any, _ctx?: any) => {
    try {
      if (!params.strategy_names || params.strategy_names.length === 0) {
        return { details: {} as any, content: [{ type: "text" as const, text: `❌ 参数错误: 请提供至少一个策略名称` }] };
      }

      const requestBody = {
        strategy_names: params.strategy_names,
        symbol: params.symbol!,
        metric: params.metric || 'sharpe_ratio'
      };

      const response = await client.post('/api/strategies/performance-comparison', requestBody);

      if (!response.success) {
        return { details: {} as any, content: [{ type: "text" as const, text: `❌ 对比失败: ${response.error}` }] };
      }

      const { comparison, ranking } = (response as any).data;

      if (comparison.length === 0) {
        return { details: {} as any, content: [{ type: "text" as const, text: `📊 未找到回测数据\n\n请确认策略名称正确，且已有回测记录。` }] };
      }

      // 格式化输出
      let output = `📊 策略性能对比报告\n\n`;
      output += `🎯 排序指标: ${params.metric || 'sharpe_ratio'}\n`;
      if (params.symbol!) {
        output += `📌 指定股票: ${params.symbol!}\n`;
      }
      output += `\n`;

      output += `🏆 性能排名：\n`;
      ranking.forEach((name: string, index: number) => {
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `${index + 1}.`;
        output += `  ${medal} ${name}\n`;
      });
      output += `\n`;

      output += `📈 详细对比：\n\n`;
      comparison.forEach((item: any, index: number) => {
        const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : '  ';
        output += `${medal} 【${item.strategyName}】\n`;
        output += `  平均夏普比率: ${item.avgSharpe?.toFixed(2) || 'N/A'}\n`;
        output += `  平均年化收益: ${(item.avgReturn * 100).toFixed(2)}%\n`;
        output += `  平均最大回撤: ${(item.avgMaxDrawdown * 100).toFixed(2)}%\n`;
        output += `  回测次数: ${item.backtestCount} 次\n`;
        output += `  最佳夏普: ${item.bestSharpe?.toFixed(2) || 'N/A'}\n`;
        if (item.bestSymbol) {
          output += `  最佳股票: ${item.bestSymbol}\n`;
        }
        output += `\n`;
      });

      // 推荐建议
      const best = comparison[0];
      output += `💡 推荐建议：\n`;

      if (best.avgSharpe >= 1.5) {
        output += `  ✅ ${best.strategyName} 表现优秀（夏普 ${best.avgSharpe.toFixed(2)}），推荐实盘使用\n`;
      } else if (best.avgSharpe >= 1.0) {
        output += `  ✅ ${best.strategyName} 表现良好（夏普 ${best.avgSharpe.toFixed(2)}），可以实盘\n`;
      } else if (best.avgSharpe >= 0.5) {
        output += `  ⚠️ ${best.strategyName} 表现一般（夏普 ${best.avgSharpe.toFixed(2)}），建议优化后再用\n`;
      } else {
        output += `  ❌ 所有策略表现较差，建议重新设计\n`;
      }

      return { details: {} as any, content: [{ type: "text" as const, text: output }] };

    } catch (error: any) {
      return { details: {} as any, content: [{ type: "text" as const, text: `❌ 策略对比失败: ${error.message}` }] };
    }
  }
};
