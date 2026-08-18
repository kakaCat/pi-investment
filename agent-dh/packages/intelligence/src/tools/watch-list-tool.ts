import { defineTool } from '@deepseek-ai/dsh-tools';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * Create watch list tool
 */
export function createWatchListTool(client: AgentDHClient) {
  return defineTool({
    name: 'watch_list',
    description: '获取盯盘规则列表，查看所有已设置的市场监控规则和触发条件',
    parameters: {},
    output: {
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'integer', description: '规则ID' },
            name: { type: 'string', description: '规则名称' },
            symbol: { type: 'string', description: '监控的股票代码' },
            condition: { type: 'string', description: '触发条件' },
            enabled: { type: 'boolean', description: '是否启用' },
            created_at: { type: 'string', description: '创建时间' },
            updated_at: { type: 'string', description: '更新时间' },
            triggered_count: { type: 'integer', description: '触发次数' },
          },
          additionalProperties: true,
        },
      },
      render: (args, value) => [
        {
          type: 'text',
          text: `共找到 ${value.length} 条盯盘规则:\n${JSON.stringify(value, null, 2)}`,
        },
      ],
    },
    timeoutMs: 10000,
    execute: async (args, exec) => {
      try {
        const rules = await client.quantsysV2.listWatchRules();
        return rules;
      } catch (error) {
        throw new Error(
          `获取盯盘规则列表失败: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },
  });
}
