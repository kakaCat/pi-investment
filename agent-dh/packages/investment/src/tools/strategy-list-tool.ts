import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create strategy list tool
 */
export function createStrategyListTool(client: AgentDHClient) {
  return defineTool({
    name: 'strategy_list',
    description: '获取策略列表，查看所有可用的交易策略及其配置参数',
    parameters: {
      source: {
        type: 'string',
        description: '策略来源：builtin（内置策略）、user（用户自定义策略）',
        enum: ['builtin', 'user'],
      },
      code_type: {
        type: 'string',
        description: '策略类型：indicator（指标策略）、trend_following（趋势跟踪）、mean_reversion（均值回归）等',
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          total: { type: 'integer', description: '策略总数' },
          page: { type: 'integer', description: '当前页码' },
          pageSize: { type: 'integer', description: '每页数量' },
          items: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string', description: '策略ID' },
                name: { type: 'string', description: '策略名称' },
                strategyType: { type: 'string', description: '策略类型' },
                type: { type: 'string', description: '类别' },
                status: { type: 'string', description: '状态' },
                description: { type: 'string', description: '策略描述' },
                code: { type: 'string', description: '策略代码' },
                params: { type: 'array', description: '参数列表' },
              },
              additionalProperties: true,
            },
          },
        },
        additionalProperties: true,
      },
      render: (args, value) => [
        {
          type: 'text',
          text: `共找到 ${value.total} 个策略（当前页 ${value.page}，每页 ${value.pageSize}，本页 ${value.items.length} 个）:\n${JSON.stringify(value.items.slice(0, 5), null, 2)}${value.items.length > 5 ? '\n...(仅显示前5个)' : ''}`,
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        const params: { source?: 'builtin' | 'user'; code_type?: string } = {};
        if (args.source) {
          params.source = args.source as 'builtin' | 'user';
        }
        if (args.code_type) {
          params.code_type = args.code_type;
        }
        const strategies = await client.quantsysV2.listStrategies(params);
        return strategies;
      } catch (error) {
        throw new Error(
          `获取策略列表失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
