import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create K-line tool
 */
export function createKlineTool(client: AgentDHClient) {
  return defineTool({
    name: 'data_fetch_kline',
    description: '获取股票K线数据，用于技术分析和趋势研判',
    parameters: {
      symbol: {
        type: 'string',
        description: '股票代码，例如：600519',
        required: true,
      },
      start_date: {
        type: 'string',
        description: '开始日期，格式：YYYY-MM-DD，例如：2024-01-01',
        required: true,
      },
      end_date: {
        type: 'string',
        description: '结束日期，格式：YYYY-MM-DD，例如：2024-12-31',
        required: true,
      },
      period: {
        type: 'string',
        description: 'K线周期：daily（日线）、weekly（周线）、monthly（月线）',
        enum: ['daily', 'weekly', 'monthly'],
        default: 'daily',
      },
    },
    output: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            date: { type: 'string', description: '日期' },
            open: { type: 'number', description: '开盘价' },
            high: { type: 'number', description: '最高价' },
            low: { type: 'number', description: '最低价' },
            close: { type: 'number', description: '收盘价' },
            volume: { type: 'number', description: '成交量' },
            amount: { type: 'number', description: '成交额' },
          },
          additionalProperties: true,
        },
      },
      render: (args, value) => [
        {
          type: 'text',
          text: `获取到 ${value.length} 条K线数据:\n${JSON.stringify(value, null, 2)}`,
        },
      ],
    },
    timeoutMs: 15000,
    execute: async (args, exec) => {
      try {
        const period = args.period || 'daily';
        const klines = await client.quantsysV2.getKlines(
          args.symbol,
          args.start_date,
          args.end_date,
          period as 'daily' | 'weekly' | 'monthly'
        );
        return klines;
      } catch (error) {
        throw new Error(
          `获取股票 ${args.symbol} K线数据失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
