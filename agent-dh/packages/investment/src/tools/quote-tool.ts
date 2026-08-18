import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create quote tool
 */
export function createQuoteTool(client: AgentDHClient) {
  return defineTool({
    name: 'data_fetch_quote',
    description: '获取股票实时行情数据，包括当前价格、涨跌幅、成交量等信息',
    parameters: {
      symbol: {
        type: 'string',
        description: '股票代码，例如：600519（贵州茅台）、000001（平安银行）',
        required: true,
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          symbol: { type: 'string', description: '股票代码' },
          price: { type: 'number', description: '当前价格' },
          change: { type: 'number', description: '涨跌额' },
          change_pct: { type: 'number', description: '涨跌幅(%)' },
          volume: { type: 'number', description: '成交量' },
          timestamp: { type: 'string', description: '行情时间戳' },
        },
        additionalProperties: true,
      },
      render: (args, value) => [
        {
          type: 'text',
          text: JSON.stringify(value, null, 2),
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        const quote = await client.quantsysV2.getQuote(args.symbol);
        return quote;
      } catch (error) {
        throw new Error(
          `获取股票 ${args.symbol} 行情失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
