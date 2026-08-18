import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create account info tool
 */
export function createAccountInfoTool(client: AgentDHClient) {
  return defineTool({
    name: 'account_info',
    description: '获取账户信息，包括总资产、可用资金、持仓市值、盈亏情况等',
    parameters: {
      account_name: {
        type: 'string',
        description: '账户名称，默认为 agent_virtual',
        default: 'agent_virtual',
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          totalValue: { type: 'number', description: '总资产' },
          totalCost: { type: 'number', description: '总成本' },
          totalMarketValue: { type: 'number', description: '持仓市值' },
          totalPnl: { type: 'number', description: '总盈亏' },
          totalPnlPct: { type: 'number', description: '总盈亏比例(%)' },
          dailyChange: { type: 'number', description: '当日涨跌' },
          positions: { type: 'integer', description: '持仓数量' },
          cash: { type: 'number', description: '可用资金' },
          liquidAssets: { type: 'number', description: '流动资产' },
          profitCount: { type: 'integer', description: '盈利持仓数' },
          lossCount: { type: 'integer', description: '亏损持仓数' },
          lastUpdated: { type: 'string', description: '更新时间' },
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
        const accountName = args.account_name || 'agent_virtual';
        const summary = await client.quantsysV2.getPortfolioSummary(accountName);
        return summary;
      } catch (error) {
        throw new Error(
          `获取账户信息失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
