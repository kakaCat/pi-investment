import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create financial data tool
 */
export function createFinancialTool(client: AgentDHClient) {
  return defineTool({
    name: 'data_fetch_financial',
    description: '获取股票财务数据，包括利润表、资产负债表、现金流量表等核心财务指标',
    parameters: {
      symbol: {
        type: 'string',
        description: '股票代码，例如：600519',
        required: true,
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          symbol: { type: 'string', description: '股票代码' },
          report_date: { type: 'string', description: '报告期' },
          revenue: { type: 'number', description: '营业收入' },
          net_profit: { type: 'number', description: '净利润' },
          total_assets: { type: 'number', description: '总资产' },
          total_liabilities: { type: 'number', description: '总负债' },
          roe: { type: 'number', description: '净资产收益率(%)' },
          eps: { type: 'number', description: '每股收益' },
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
    timeoutMs: 15000,
    execute: async (args, exec) => {
      try {
        const financial = await client.quantsysV2.getFinancialData(args.symbol);
        return financial;
      } catch (error) {
        throw new Error(
          `获取股票 ${args.symbol} 财务数据失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
