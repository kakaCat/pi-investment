import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeHistoryParams {
  section: string;
  limit?: number;
}

export interface GenomeVersionInfo {
  version: string;
  timestamp: string;
  file_size: number;
  preview: string;
}

export interface GenomeHistoryResult {
  section: string;
  current_version: string;
  history: GenomeVersionInfo[];
  total_versions: number;
}

export const genomeHistoryPrompt: ToolPrompt<GenomeHistoryParams, GenomeHistoryResult> = {
  description: '查看基因组段的版本历史',
  useCases: [
    '审计段的演化历史',
    '查找特定版本的内容',
    '分析版本变更频率',
    '准备回滚操作',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '要查询的段名称',
    },
    limit: {
      type: 'number',
      required: false,
      description: '返回的最大版本数（1-100），默认 10',
      default: 10,
      minimum: 1,
      maximum: 100,
      example: 10,
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        section: { type: 'string' },
        current_version: { type: 'string' },
        history: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            properties: {
              version: { type: 'string' },
              timestamp: { type: 'string' },
              file_size: { type: 'number' },
              preview: { type: 'string' },
            },
          },
        },
        total_versions: { type: 'number' },
      },
    },
  },
  examples: [
    {
      input: {
        section: 'identity',
        limit: 5,
      },
      output: {
        section: 'identity',
        current_version: '1.3.0',
        history: [
          {
            version: '1.3.0',
            timestamp: '2026-08-28T10:00:00Z',
            file_size: 1234,
            preview: '# Agent 身份\n\n我是 PI Investment Agent...',
          },
          {
            version: '1.2.0',
            timestamp: '2026-08-20T10:00:00Z',
            file_size: 1100,
            preview: '# Agent 身份\n\n我是量化投资助手...',
          },
        ],
        total_versions: 5,
      },
      description: '查看最近 5 个版本',
    },
  ],
};
