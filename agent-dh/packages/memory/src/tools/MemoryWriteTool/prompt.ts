import type { ToolPrompt } from '@pi-investment/core-tool';

export interface MemoryWriteParams {
  content: string;
  importance?: number;
  namespace?: string;
  tags?: string[];
}

export interface MemoryWriteResult {
  success: boolean;
  memory_id: string;
  message: string;
}

export const memoryWritePrompt: ToolPrompt<MemoryWriteParams, MemoryWriteResult> = {
  description: '写入长期记忆，保存分析结论、决策依据，供未来 memory_search 检索复用',
  useCases: [
    '完成重要分析后沉淀结论',
    '记录决策理由以便复盘',
    '保存关键信息供后续检索',
    '建立知识库条目',
  ],
  examples: [
    {
      title: '保存分析结论',
      params: {
        content: '600519贵州茅台：2024Q3营收增长15%，驱动来自系列酒放量，需关注渠道库存',
        importance: 0.7,
        namespace: 'analysis',
        tags: ['600519', '白酒', 'Q3财报'],
      },
      expectedResult: '已写入记忆库，ID: 123',
    },
    {
      title: '记录决策依据',
      params: {
        content: '市场进入震荡期，减少追涨杀跌，关注低估值白马股',
        importance: 0.5,
        namespace: 'decision',
        tags: ['市场判断', '操作策略'],
      },
      expectedResult: '已写入记忆库，ID: 456',
    },
  ],
  notes: [
    '💡 记录交易得失经验请用 experience_write（结构更专门）',
    '💡 内容建议结构化并包含股票代码和时间',
    '💡 importance 影响后续检索排序',
  ],
  relatedTools: ['memory_search', 'experience_write'],
  parameters: {
    content: {
      type: 'string',
      description: '记忆内容。建议结构化描述并含关键实体，如 "600519贵州茅台：2024Q3营收增长15%，驱动来自系列酒放量，需关注渠道库存"',
      required: true,
      example: '600519贵州茅台：2024Q3营收增长15%',
    },
    importance: {
      type: 'number',
      description: '重要程度 0-1，默认 0.5。参考：0.3 普通记录；0.5 重要；0.8 关键决策依据',
      default: 0.5,
      example: 0.7,
    },
    namespace: {
      type: 'string',
      description: '记忆命名空间：default（默认）、experience、decision、analysis',
      default: 'default',
      example: 'analysis',
    },
    tags: {
      type: 'array',
      description: '标签列表，如 ["600519", "白酒", "Q3财报"]，用于提升检索命中率',
      items: { type: 'string' },
      example: ['600519', '白酒', 'Q3财报'],
    },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        success: { type: 'boolean', description: '是否成功' },
        memory_id: { type: 'string', description: '记忆ID' },
        message: { type: 'string', description: '结果消息' },
      },
      additionalProperties: true,
    },
  },
};
