import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create pool list tool
 */
export function createPoolListTool(client: AgentDHClient) {
  return defineTool({
    name: 'pool_list',
    description: '获取股票池列表，查看所有已创建的股票筛选池及其基本信息',
    parameters: {},
    output: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'integer', description: '股票池ID' },
            name: { type: 'string', description: '股票池名称' },
            description: { type: 'string', description: '股票池描述' },
            created_at: { type: 'string', description: '创建时间' },
            updated_at: { type: 'string', description: '更新时间' },
            member_count: { type: 'integer', description: '成员数量' },
          },
          additionalProperties: true,
        },
      },
      render: (args, value) => [
        {
          type: 'text',
          text: `共找到 ${value.length} 个股票池:\n${JSON.stringify(value, null, 2)}`,
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        const pools = await client.quantsysV2.listPools();
        return pools;
      } catch (error) {
        throw new Error(
          `获取股票池列表失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
