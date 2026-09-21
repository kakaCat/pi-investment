import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeHistoryParams {
  /** 段名（不传=全部段的历史） */
  section?: string;
  /** 返回最近 N 条（默认 10） */
  limit?: number;
}

export interface GenomeHistoryEntry {
  version: string;
  section: string;
  section_version: number;
  parent: string;
  reason: string;
  ts: string;
  author?: string;
  type?: string;
  git_commit?: string;
  stage?: string;
  force?: boolean;
  baseline_version?: string;
}

export interface GenomeHistoryResult {
  history: GenomeHistoryEntry[];
}

export const genomeHistoryPrompt: ToolPrompt<GenomeHistoryParams, GenomeHistoryResult> = {
  description: '查询基因组版本历史：各版本的段、理由、commit、时间。用于：复盘"这轮进化改了什么"、追溯决策依据。',
  useCases: [
    '复盘基因组进化历史',
    '按段追溯版本谱系',
    '查看最近 N 条变更',
  ],
  parameters: {
    section: {
      type: 'string',
      required: false,
      description: '段名（不传=全部段的历史）',
    },
    limit: {
      type: 'number',
      required: false,
      description: '返回最近 N 条（默认 10）',
      default: 10,
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        history: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: true,
            properties: {
              version: { type: 'string' },
              section: { type: 'string' },
              section_version: { type: 'number' },
              parent: { type: 'string' },
              reason: { type: 'string' },
              ts: { type: 'string' },
              author: { type: 'string' },
              type: { type: 'string' },
              git_commit: { type: 'string' },
              stage: { type: 'string' },
              force: { type: 'boolean' },
              baseline_version: { type: 'string' },
            },
          },
        },
      },
      required: ['history'],
    },
  },
  examples: [
    {
      input: { limit: 3 },
      output: {
        history: [
          {
            version: 'g16',
            section: 'lessons',
            section_version: 5,
            parent: 'g15',
            reason: '新增经验教训',
            ts: '2026-08-30T10:00:00.000Z',
            author: 'agent',
            type: 'update',
            git_commit: 'a1b2c3d',
            stage: 'active',
          },
        ],
      },
      description: '查询最近历史',
    },
  ],
};
