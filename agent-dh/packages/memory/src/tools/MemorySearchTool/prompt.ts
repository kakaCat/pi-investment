import type { ToolPrompt } from '@pi-investment/core-tool';

export interface MemorySearchParams {
  query: string;
  top_k?: number;
  namespace?: string;
}

export interface MemoryItem {
  id: string;
  title: string;
  content: string;
  kind: string;
  scope: string;
  confidence: number;
  created_at: string;
  payload?: any;
}

export interface MemorySearchResult {
  query: string;
  results: MemoryItem[];
  total: number;
  degraded?: boolean;
  strategy?: string;
}

export const memorySearchPrompt: ToolPrompt<MemorySearchParams, MemorySearchResult> = {
  description: '语义搜索长期记忆，找回历史分析结论、决策理由、经验教训',
  useCases: [
    '分析某只股票前查是否已分析过',
    '复盘历史决策',
    '复用过往经验',
    '查找特定主题的记忆',
  ],
  examples: [
    {
      title: '搜索贵州茅台相关记忆',
      params: {
        query: '贵州茅台',
        top_k: 5,
        namespace: 'default',
      },
      expectedResult: '找到 1 条记忆：2024Q3营收增长15%',
    },
    {
      title: '搜索交易经验教训',
      params: {
        query: '止损经验',
        top_k: 3,
        namespace: 'experience',
      },
      expectedResult: '找到 1 条经验：突破买入后遭遇大盘回调 -8.2%',
    },
  ],
  notes: [
    '💡 记忆由 memory_write / experience_write 写入',
    '💡 namespace=experience 专门搜索交易经验',
    '💡 支持自然语言和关键词搜索',
  ],
  relatedTools: ['memory_write', 'experience_write'],
  parameters: {
    query: {
      type: 'string',
      description: '搜索内容，支持自然语言或关键词，如 "贵州茅台"、"止损经验"、"2024Q1 白酒"',
      required: true,
      example: '贵州茅台',
    },
    top_k: {
      type: 'integer',
      description: '返回最相关的结果条数，默认 5。结果不全时可增大',
      default: 5,
      example: 5,
    },
    namespace: {
      type: 'string',
      description: '记忆命名空间。default（默认）：通用记忆；experience：交易经验；decision：决策记录；analysis：分析结论',
      default: 'default',
      example: 'default',
    },
  },
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        query: { type: 'string', description: '搜索关键词' },
        results: {
          type: 'array',
          description: '记忆条目列表',
          items: {
            type: 'object', additionalProperties: true,
            properties: {
              id: { type: 'string' },
              title: { type: 'string' },
              content: { type: 'string' },
              kind: { type: 'string' },
              scope: { type: 'string' },
              confidence: { type: 'number' },
              created_at: { type: 'string' },
            },
          },
        },
        total: { type: 'integer', description: '总匹配数' },
        degraded: { type: 'boolean', description: '是否降级模式' },
        strategy: { type: 'string', description: '检索策略' },
      },
      additionalProperties: true,
    },
  },
};
