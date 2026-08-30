import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomePromoteParams {
  section: string;
  reason: string;
}

export interface GenomePromoteResult {
  success: boolean;
  genome_version: string;
  section: string;
  section_version: number;
  git_commit?: string;
}

export const genomePromotePrompt: ToolPrompt<GenomePromoteParams, GenomePromoteResult> = {
  description: '把段的观察版（candidate）转为正式版（active）。不改变段内容与版本号（内容已在观察期实际运行），只改 history 标记并留谱系。用于：验证门裁决通过后转正。拒绝路径用 genome_rollback。',
  useCases: [
    '验证门裁决通过后转正',
    'candidate 观察版 → active 正式版',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '段名：principles / rules / lessons',
    },
    reason: {
      type: 'string',
      required: true,
      description: '转正理由（必填），如"观察期胜率不劣于基准"',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        genome_version: { type: 'string' },
        section: { type: 'string' },
        section_version: { type: 'number' },
        git_commit: { type: 'string' },
      },
      required: ['success', 'genome_version', 'section', 'section_version'],
    },
  },
  examples: [
    {
      input: {
        section: 'principles',
        reason: '观察期胜率不劣于基准',
      },
      output: {
        success: true,
        genome_version: 'g17',
        section: 'principles',
        section_version: 7,
        git_commit: '9a8b7c6',
      },
      description: '转正 principles 的 candidate 观察版',
    },
  ],
};
