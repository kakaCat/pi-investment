import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomePromoteParams {
  section: string;
  increment: 'major' | 'minor' | 'patch';
  reason: string;
}

export interface GenomePromoteResult {
  section: string;
  old_version: string;
  new_version: string;
  increment_type: string;
  commit_hash?: string;
}

export const genomePromotePrompt: ToolPrompt<GenomePromoteParams, GenomePromoteResult> = {
  description: '提升基因组段的版本号（不修改内容，仅用于标记里程碑）',
  useCases: [
    '标记重要的版本里程碑',
    '发布稳定版本',
    '同步版本号与其他组件',
    '记录验证通过的版本',
  ],
  examples: [
    {
      input: {
        section: 'identity',
        increment: 'major',
        reason: '完成身份系统重构，发布 2.0.0',
      },
      output: {
        section: 'identity',
        old_version: '1.5.3',
        new_version: '2.0.0',
        increment_type: 'major',
        commit_hash: 'f1e2d3c',
      },
      description: '提升主版本号',
    },
    {
      input: {
        section: 'tools_usage',
        increment: 'minor',
        reason: '添加新工具使用规则',
      },
      output: {
        section: 'tools_usage',
        old_version: '1.2.0',
        new_version: '1.3.0',
        increment_type: 'minor',
        commit_hash: 'a1b2c3d',
      },
      description: '提升次版本号',
    },
  ],
};
