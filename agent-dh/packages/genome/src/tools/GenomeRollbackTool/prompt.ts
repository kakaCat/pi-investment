import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeRollbackParams {
  section: string;
  target_version: string;
}

export interface GenomeRollbackResult {
  section: string;
  old_version: string;
  restored_version: string;
  content_preview: string;
  commit_hash?: string;
}

export const genomeRollbackPrompt: ToolPrompt<GenomeRollbackParams, GenomeRollbackResult> = {
  description: '回滚基因组段到指定版本',
  useCases: [
    '撤销错误的更新',
    '恢复到已知良好的版本',
    '测试不同版本的效果',
    '修复配置错误',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '要回滚的段名称',
    },
    target_version: {
      type: 'string',
      required: true,
      description: '目标版本号',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        section: { type: 'string' },
        old_version: { type: 'string' },
        restored_version: { type: 'string' },
        content_preview: { type: 'string' },
        commit_hash: { type: 'string' },
      },
    },
  },
  examples: [
    {
      input: {
        section: 'identity',
        target_version: '1.0.0',
      },
      output: {
        section: 'identity',
        old_version: '1.2.0',
        restored_version: '1.0.0',
        content_preview: '# Agent 身份\n\n我是 PI Investment Agent...',
        commit_hash: 'x9y8z7w',
      },
      description: '回滚身份段到 1.0.0',
    },
  ],
};
