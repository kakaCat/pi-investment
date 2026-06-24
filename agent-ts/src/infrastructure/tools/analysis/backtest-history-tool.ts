/**
 * 回测历史查询工具
 *
 * 用途：查询策略的历史回测记录，分析性能变化趋势
 */

import type { ToolDefinition } from '@mariozechner/pi-coding-agent';
import { QuantV2Client } from '../../../infrastructure/adapters/quant/quant-v2-client.js';

const client = QuantV2Client;

interface BacktestHistoryParams {
  strategy_name?: string;  // 策略名称（可选）
  symbol?: string;          // 股票代码（可选）
  limit?: number;           // 返回数量限制（默认20）
}

export const backtestHistoryTool: ToolDefinition = {
  name: 'backtest_history',
  description: `查询策略的历史回测记录，分析性能变化趋势。

使用场景：
- 查看策略272在宁德时代上的所有回测记录
- 分析策略性能是否随时间衰减
- 对比同一策略在不同时期的表现

返回指标包括：年化收益、夏普比率、最大回撤、交易次数、胜率等。`,

  parameters: {
    type: 'object',
    properties: {
      strategy_name: {
        type: 'string',
        description: '策略名称（精确匹配），例如："新能源动量策略 v1.0"'
      },
      symbol: {
        type: 'string',
        description: '股票代码，例如："300750.SZ"（宁德时代）'
      },
      limit: {
        type: 'number',
        description: '返回数量限制，默认20',
        default: 20
      }
    }
  },

  execute: async (_toolCallId: string, params: BacktestHistoryParams) => {
    try {
      const queryParams: Record<string, string> = {};

      if (params.strategy_name) {
        queryParams.strategy_name = params.strategy_name;
      }
      if (params.symbol!) {
        queryParams.symbol = params.symbol!;
      }
      if (params.limit) {
        queryParams.limit = params.limit.toString();
      }

      const response = await client.get('/api/backtest/history', queryParams);

      if (!response.success) {
        return { content: [{ type: "text" as const, text: `❌ 查询失败: ${response.error}` }] };
      }

      const { items, count } = (response as any).data;

      if (count === 0) {
        return { content: [{ type: "text" as const, text: `📊 未找到回测记录\n\n筛选条件：\n${params.strategy_name ? `  策略: ${params.strategy_name}\n` : ''}${params.symbol! ? `  股票: ${params.symbol!}\n` : ''}` }] };
      }

      // 格式化输出
      let output = `📊 回测历史记录（共 ${count} 条）\n\n`;

      items.forEach((record: any, index: number) => {
        output += `【记录 ${index + 1}】\n`;
        output += `  策略: ${record.strategyName}\n`;
        output += `  股票: ${record.symbol}\n`;
        output += `  回测期: ${record.startDate} ~ ${record.endDate}\n`;
        output += `  📈 年化收益: ${(record.annualReturn * 100).toFixed(2)}%\n`;
        output += `  📊 夏普比率: ${record.sharpeRatio?.toFixed(2) || 'N/A'}\n`;
        output += `  📉 最大回撤: ${(record.maxDrawdown * 100).toFixed(2)}%\n`;
        output += `  🔄 交易次数: ${record.totalTrades} 次\n`;
        output += `  ✅ 胜率: ${(record.winRate * 100).toFixed(2)}%\n`;
        output += `  🕐 回测时间: ${new Date(record.createdAt).toLocaleString('zh-CN')}\n`;
        output += `\n`;
      });

      // 如果有多条记录，添加趋势分析
      if (count >= 3) {
        const recentThree = items.slice(0, 3);
        const avgReturn = recentThree.reduce((sum: number, r: any) => sum + r.annualReturn, 0) / 3;
        const avgSharpe = recentThree.reduce((sum: number, r: any) => sum + (r.sharpeRatio || 0), 0) / 3;

        output += `📌 最近3次回测平均：\n`;
        output += `  年化收益: ${(avgReturn * 100).toFixed(2)}%\n`;
        output += `  夏普比率: ${avgSharpe.toFixed(2)}\n`;
      }

      return output;

    } catch (error: any) {
      return { content: [{ type: "text" as const, text: `❌ 查询回测历史失败: ${error.message}` }] };
    }
  }
};
