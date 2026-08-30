import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeUpdateParams {
  section: string;
  content: string;
  reason: string;
  /** 乐观锁：期望的当前段版本（整数），不匹配则拒绝写入 */
  expected_section_version?: number;
  /** RFC 008 验证门：candidate=观察版（模拟盘 A/B 中），active=正式版（默认） */
  stage?: 'active' | 'candidate';
  /** 交易时段强制修改（会留痕 history），仅紧急修复使用 */
  force?: boolean;
}

export interface GenomeUpdateResult {
  success: boolean;
  section: string;
  /** 更新前的段版本 */
  old_version: number;
  /** 更新后的段版本（旧版本 + 1） */
  new_version: number;
  /** 新的基因组代数（gN） */
  genome_version: string;
  diff_summary: {
    added_lines: number;
    removed_lines: number;
    changed_lines: number;
  };
  /** 规则 ID 增删（仅 rules 段有意义，其余段为空数组） */
  rule_id_changes: { added: string[]; removed: string[] };
  git_commit?: string;
  /** 交易时段 force 修改的留痕警告 */
  warning?: string;
}

export const genomeUpdatePrompt: ToolPrompt<GenomeUpdateParams, GenomeUpdateResult> = {
  description: '更新基因组段（宪法层禁止；整数版本号自动 +1；gN 代数推进；历史只增不改；金丝雀渲染失败自动还原）',
  useCases: [
    '进化 principles / rules / lessons 段内容',
    'RFC 008 验证门：以 candidate 观察版写入',
    '规则段新增/修订规则条目',
  ],
  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '要更新的段名称（principles / rules / lessons；constitution 为宪法层禁止修改）',
    },
    content: {
      type: 'string',
      required: true,
      description: '新的段内容（完整替换，须通过花括号/大小/规则ID校验）',
    },
    reason: {
      type: 'string',
      required: true,
      description: '更新原因（写入 git commit message 与 history）',
    },
    expected_section_version: {
      type: 'number',
      required: false,
      description: '乐观锁：期望的当前段版本（整数），不匹配则拒绝写入',
    },
    stage: {
      type: 'string',
      required: false,
      description: 'RFC 008 验证门：candidate=观察版，active=正式版（默认）',
      enum: ['active', 'candidate'],
    },
    force: {
      type: 'boolean',
      required: false,
      description: '交易时段强制修改（会留痕 history），仅紧急修复使用',
    },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        section: { type: 'string' },
        old_version: { type: 'number' },
        new_version: { type: 'number' },
        genome_version: { type: 'string' },
        diff_summary: {
          type: 'object',
          additionalProperties: false,
          properties: {
            added_lines: { type: 'number' },
            removed_lines: { type: 'number' },
            changed_lines: { type: 'number' },
          },
          required: ['added_lines', 'removed_lines', 'changed_lines'],
        },
        rule_id_changes: {
          type: 'object',
          additionalProperties: false,
          properties: {
            added: { type: 'array', items: { type: 'string' } },
            removed: { type: 'array', items: { type: 'string' } },
          },
          required: ['added', 'removed'],
        },
        git_commit: { type: 'string' },
        warning: { type: 'string' },
      },
      required: ['success', 'section', 'old_version', 'new_version', 'genome_version', 'diff_summary', 'rule_id_changes'],
    },
  },
  examples: [
    {
      input: {
        section: 'principles',
        content: '# 决策原则\n\n1. 数据驱动',
        reason: '更新决策原则',
        expected_section_version: 6,
      },
      output: {
        success: true,
        section: 'principles',
        old_version: 6,
        new_version: 7,
        genome_version: 'g17',
        diff_summary: { added_lines: 2, removed_lines: 1, changed_lines: 0 },
        rule_id_changes: { added: [], removed: [] },
        git_commit: 'a1b2c3d',
      },
      description: '更新原则段（带乐观锁）',
    },
  ],
};
