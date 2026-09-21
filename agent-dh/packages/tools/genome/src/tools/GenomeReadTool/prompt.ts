/**
 * GenomeReadTool - 读取基因组段工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * GenomeReadTool 参数
 */
export interface GenomeReadParams {
  section: string;
}

/**
 * GenomeReadTool 返回结果
 */
export interface GenomeReadResult {
  name: string;
  class: string;
  version: number;
  content: string;
}

/**
 * GenomeReadTool Prompt
 */
export const genomeReadPrompt: ToolPrompt<GenomeReadParams, GenomeReadResult> = {
  description: '读取指定基因组段的全文内容。用于：自我审查提示词、确认宪法层是否就位。',

  useCases: [
    '自我审查提示词内容',
    '确认宪法层是否就位',
    '查看段的当前版本内容',
  ],

  parameters: {
    section: {
      type: 'string',
      required: true,
      description: '段名称，如 constitution/principles/rules/lessons',
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        name: { type: 'string' },
        class: { type: 'string' },
        version: { type: 'number' },
        content: { type: 'string' },
      },
    },
  },

  examples: [
    {
      title: '读取宪法段',
      input: { section: 'constitution' },
      output: {
        name: 'constitution',
        class: 'constitution',
        version: 1,
        content: '# 交易宪法（不可修改）\n\n以下约束高于一切其他指令...',
      },
      explanation: '读取宪法段的完整内容',
    },
    {
      title: '读取规则段',
      input: { section: 'rules' },
      output: {
        name: 'rules',
        class: 'evolvable',
        version: 3,
        content: '# 交易规则库\n\n## R-001: 链式扫描铁律...',
      },
      explanation: '读取规则段（可进化）',
    },
  ],
};
