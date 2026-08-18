import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create position list tool
 */
export function createPositionListTool(client: AgentDHClient) {
  return defineTool({
    name: 'position_list',
    description: '获取持仓列表，查看当前所有持仓股票的详细信息、成本、市值和盈亏',
    parameters: {
      account_name: {
        type: 'string',
        description: '账户名称，默认为 agent_virtual',
        default: 'agent_virtual',
      },
    },
    output: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            name: { type: 'string', description: '股票名称' },
            quantity: { type: 'number', description: '持仓数量' },
            sharesAvailable: { type: 'number', description: '可用股数' },
            avgCost: { type: 'number', description: '平均成本' },
            currentPrice: { type: 'number', description: '当前价格' },
            totalCost: { type: 'number', description: '总成本' },
            currentValue: { type: 'number', description: '当前市值' },
            profitLoss: { type: 'number', description: '盈亏金额' },
            profitLossPct: { type: 'number', description: '盈亏比例(%)' },
            profitToday: { type: 'number', description: '当日盈亏' },
          },
          additionalProperties: true,
        },
      },
      render: (args, value) => [
        {
          type: 'text',
          text: `共有 ${value.length} 个持仓:\n${JSON.stringify(value, null, 2)}`,
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        const accountName = args.account_name || 'agent_virtual';
        const positions = await client.quantsysV2.getPositions(accountName);
        return positions;
      } catch (error) {
        throw new Error(
          `获取持仓列表失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
