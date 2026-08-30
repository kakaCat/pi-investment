import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeListParams {
  /** 按类别过滤：constitution（宪法层，锁定）/ evolvable（可进化段） */
  class?: 'constitution' | 'evolvable';
}

export interface GenomeSectionInfo {
  name: string;
  class: 'constitution' | 'evolvable';
  version: number;
  description?: string;
  char_count: number;
}

export interface GenomeListResult {
  sections: GenomeSectionInfo[];
  total: number;
  by_class?: {
    constitution: number;
    evolvable: number;
  };
}

export const genomeListPrompt: ToolPrompt<GenomeListParams, GenomeListResult> = {
  description: '列出基因组全部段及其版本（线上模型：整数版本号，class 为 constitution/evolvable）',
  useCases: [
    '查看当前基因组各段版本',
    '按类别过滤查询（constitution/evolvable）',
    '确认某段是否锁定',
  ],
  parameters: {
    class: {
      type: 'string',
      required: false,
      description: '按类别过滤：constitution（宪法层，锁定）/ evolvable（可进化段）。不传则列出全部',
      enum: ['constitution', 'evolvable'],
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        sections: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            properties: {
              name: { type: 'string' },
              class: { type: 'string', enum: ['constitution', 'evolvable'] },
              version: { type: 'number' },
              description: { type: 'string' },
              char_count: { type: 'number' },
            },
            required: ['name', 'class', 'version', 'char_count'],
          },
        },
        total: { type: 'number' },
        by_class: {
          type: 'object',
          additionalProperties: false,
          properties: {
            constitution: { type: 'number' },
            evolvable: { type: 'number' },
          },
        },
      },
      required: ['sections', 'total'],
    },
  },
  examples: [
    {
      input: {},
      output: {
        sections: [
          {
            name: 'constitution',
            class: 'constitution',
            version: 1,
            description: '交易宪法（不可修改）',
            char_count: 1234,
          },
          {
            name: 'principles',
            class: 'evolvable',
            version: 6,
            description: '决策原则（可进化）',
            char_count: 3456,
          },
        ],
        total: 4,
        by_class: { constitution: 1, evolvable: 3 },
      },
      description: '列出所有段',
    },
    {
      input: { class: 'evolvable' },
      output: {
        sections: [
          {
            name: 'principles',
            class: 'evolvable',
            version: 6,
            description: '决策原则（可进化）',
            char_count: 3456,
          },
        ],
        total: 3,
      },
      description: '只列出可进化段',
    },
  ],
};
