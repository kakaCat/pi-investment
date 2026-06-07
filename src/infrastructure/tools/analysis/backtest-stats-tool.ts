/**
 * 回测统计工具
 *
 * 用途：获取策略的回测统计信息，快速了解策略整体表现
 */

import type { ToolDefinition } from '@mariozechner/pi-coding-agent';
import { QuantV2Client } from '../../../infrastructure/adapters/quant/quant-v2-client.js';

const client = QuantV2Client;

interface BacktestStatsParams {
  strategy_name?: string;  // 策略名称（可选）
}

export const backtestStatsTool: ToolDefinition = {
  name: 'backtest_stats',
  description: `获取策略的回测统计信息，包括平均夏普比率、平均收益、回测次数等。

使用场景：
- 快速了解策略272的整体表现
- 查看策略在所有股票上的平均表现
- 判断策略是否稳定（多次回测结果接近）`,

  parameters: {
    type: 'object',
    properties: {
      strategy_name: {
        type: 'string',
        description: '策略名称（可选）。不指定则返回所有策略的汇总统计'
      }
    }
  },

  execute: async (_toolCallId, params: BacktestStatsParams) => {
    try {
      const queryParams: Record<string, string> = {};

      if (params.strategy_name) {
        queryParams.strategy_name = params.strategy_name;
      }

      const response = await client.get('/api/backtest/stats', queryParams);

      if (!response.success) {
        return `❌ 查询失败: ${response.error}`;
      }

      const stats = response.data;

      if (stats.totalBacktests === 0) {
        return `📊 未找到回测统计数据\n\n${params.strategy_name ? `策略 "${params.strategy_name}" 还没有回测记录。` : '系统中还没有任何回测记录。'}`;
      }

      // 格式化输出
      let output = `📊 回测统计报告\n\n`;

      if (params.strategy_name) {
        output += `📌 策略: ${params.strategy_name}\n\n`;
      } else {
        output += `📌 范围: 所有策略\n\n`;
      }

      output += `📈 统计指标：\n`;
      output += `  回测次数: ${stats.totalBacktests} 次\n`;
      output += `  平均夏普比率: ${stats.avgSharpe?.toFixed(2) || 'N/A'}\n`;
      output += `  平均年化收益: ${(stats.avgReturn * 100).toFixed(2)}%\n`;
      output += `  平均最大回撤: ${(stats.avgMaxDrawdown * 100).toFixed(2)}%\n`;
      output += `\n`;

      output += `🏆 最佳表现：\n`;
      output += `  最高夏普比率: ${stats.bestSharpe?.toFixed(2) || 'N/A'}\n`;
      if (stats.bestReturn !== undefined) {
        output += `  最高年化收益: ${(stats.bestReturn * 100).toFixed(2)}%\n`;
      }
      output += `\n`;

      // 性能评级
      const avgSharpe = stats.avgSharpe || 0;
      output += `⭐ 性能评级：`;

      if (avgSharpe >= 1.5) {
        output += ` ⭐⭐⭐⭐⭐ 优秀（夏普 ${avgSharpe.toFixed(2)}）\n`;
        output += `  建议：实盘使用，重仓配置\n`;
      } else if (avgSharpe >= 1.0) {
        output += ` ⭐⭐⭐⭐ 良好（夏普 ${avgSharpe.toFixed(2)}）\n`;
        output += `  建议：实盘使用，中等仓位\n`;
      } else if (avgSharpe >= 0.5) {
        output += ` ⭐⭐⭐ 一般（夏普 ${avgSharpe.toFixed(2)}）\n`;
        output += `  建议：小仓位试验，继续优化\n`;
      } else {
        output += ` ⭐⭐ 较差（夏普 ${avgSharpe.toFixed(2)}）\n`;
        output += `  建议：大幅改进或重新设计\n`;
      }

      return output;

    } catch (error: any) {
      return `❌ 查询统计信息失败: ${error.message}`;
    }
  }
};
