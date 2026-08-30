import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeUpdateParams {
  section: string;
  content: string;
  reason: string;
}

export interface GenomeUpdateResult {
  section: string;
  old_version: string;
  new_version: string;
  diff_summary: {
    added_lines: number;
    removed_lines: number;
    changed_lines: number;
  };
  commit_hash?: string;
}

export const genomeUpdatePrompt: ToolPrompt<GenomeUpdateParams, GenomeUpdateResult> = {
  description: '更新基因组段的内容（自动版本控制和 git 提交）',
  useCases: [
    '修改 agent 身份定义',
    '更新工具使用规则',
    '调整策略参数',
    '改进提示词',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '要更新的段名称',
    },
    content: {
      type: 'string',
      required: true,
      description: '新的段内容（完整替换）',
    },
    reason: {
      type: 'string',
      required: true,
      description: '更新原因（用于 git commit message）',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        section: { type: 'string' },
        old_version: { type: 'string' },
        new_version: { type: 'string' },
        diff_summary: {
          type: 'object',
          additionalProperties: false,
          properties: {
            added_lines: { type: 'number' },
            removed_lines: { type: 'number' },
            changed_lines: { type: 'number' },
          },
        },
        commit_hash: { type: 'string' },
      },
    },
  },
  examples: [
    {
      input: {
        section: 'identity',
        content: '# Agent 身份\n\n我是 PI Investment Agent...',
        reason: '更新身份描述，强调自主决策能力',
      },
      output: {
        section: 'identity',
        old_version: '1.0.0',
        new_version: '1.1.0',
        diff_summary: {
          added_lines: 5,
          removed_lines: 2,
          changed_lines: 3,
        },
        commit_hash: 'a1b2c3d',
      },
      description: '更新身份段',
    },
  ],
};
