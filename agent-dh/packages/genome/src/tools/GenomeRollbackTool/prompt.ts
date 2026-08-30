import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeRollbackParams {
  section: string;
  /** 目标段版本（整数；不传=回滚到上一版本） */
  to_section_version?: number;
  reason: string;
}

export interface GenomeRollbackResult {
  success: boolean;
  genome_version: string;
  section_version: number;
  /** 实际回滚到的目标版本 */
  rolled_back_to: number;
  git_commit?: string;
}

export const genomeRollbackPrompt: ToolPrompt<GenomeRollbackParams, GenomeRollbackResult> = {
  description: '回滚段到历史版本。回滚=新版本（内容同目标版本，代数+1），历史只增不改。用于：验证门失败回退、进化恶化复原。',
  useCases: [
    '验证门失败回退',
    '进化恶化复原',
    '回滚到指定历史版本',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '段名：principles / rules / lessons（constitution 为宪法层禁止回滚）',
    },
    to_section_version: {
      type: 'number',
      required: false,
      description: '目标段版本（整数；不传=回滚到上一版本）',
    },
    reason: {
      type: 'string',
      required: true,
      description: '回滚理由，如"模拟盘 A/B 恶化"',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        genome_version: { type: 'string' },
        section_version: { type: 'number' },
        rolled_back_to: { type: 'number' },
        git_commit: { type: 'string' },
      },
      required: ['success', 'genome_version', 'section_version', 'rolled_back_to'],
    },
  },
  examples: [
    {
      input: {
        section: 'principles',
        reason: '模拟盘 A/B 恶化',
      },
      output: {
        success: true,
        genome_version: 'g18',
        section_version: 8,
        rolled_back_to: 6,
        git_commit: 'f4e5d6c',
      },
      description: '回滚 principles 到上一版本',
    },
  ],
};
