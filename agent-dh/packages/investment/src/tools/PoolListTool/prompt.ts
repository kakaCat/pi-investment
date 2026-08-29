import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PoolListParams {}

export interface PoolItem {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  member_count: number;
  [key: string]: any;
}

export type PoolListResult = PoolItem[];

export const poolListPrompt: ToolPrompt<PoolListParams, PoolListResult> = {
  description: '获取全部股票池列表：名称、筛选逻辑描述、成员数量、更新时间。股票池是预定义筛选条件的集合（如高ROE池、低估值池），是博弈中的"战场"。适用于：盘前查看可用池子、选择分析对象。',

  useCases: ['查看可用股票池', '选择分析对象'],

  parameters: {},

  output: {
    schema: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        properties: {
          id: { type: 'number' },
          name: { type: 'string' },
          description: { type: 'string' },
          created_at: { type: 'string' },
          updated_at: { type: 'string' },
          member_count: { type: 'number' },
        },
      },
    },
    render: (args, data) => [{ type: 'text', text: `共找到 ${data.length} 个股票池:\n${JSON.stringify(data, null, 2)}` }],
  },
};
