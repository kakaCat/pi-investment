/**
 * LearningDistillTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface LearningDistillParams {
  source: string;
  target_format: 'rule' | 'prompt' | 'code';
  min_confidence?: number;
  max_rules?: number;
}

export interface LearningDistillResult {
  success: boolean;
  rules: any[];
  source_count: number;
  distill_method: string;
  validation_stats: Record<string, any>;
  // 2026-09-03 Fix③：规则落库结果（候选 kind='rule' status='testing'；rules 项带 memory_id）
  persistence?: {
    persisted: number;
    total: number;
    failed: number;
    error: string | null;
  };
}

export const learningDistillPrompt: ToolPrompt<LearningDistillParams, LearningDistillResult> = {
  description: '将经验提炼为可执行规则（写操作）。从经验库中提取模式，转化为规则、提示词或代码片段。',
  useCases: ['将成功经验转化为规则', '生成决策提示词', '提炼代码模式'],
  examples: [
    {
      title: '提炼交易规则',
      params: { source: 'recent_trades', target_format: 'rule', min_confidence: 0.7 },
      expectedResult: '返回提炼的规则列表',
    },
  ],
  parameters: {
    source: { type: 'string', required: true, description: '经验来源标识' },
    target_format: { type: 'string', required: true, description: '目标格式：rule、prompt、code' },
    min_confidence: { type: 'number', required: false, description: '最小置信度（0-1）' },
    max_rules: { type: 'number', required: false, description: '最大规则数' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        rules: { type: 'array', items: { type: 'object', additionalProperties: true } },
        source_count: { type: 'number' },
        distill_method: { type: 'string' },
        validation_stats: { type: 'object', additionalProperties: true },
        persistence: {
          type: 'object',
          additionalProperties: true,
          description: '规则落库结果（Fix③）',
        },
      },
    },
    render: (args, data) => {
      let output = '## 🎯 规则提炼结果\n\n';
      output += `- **源样本数**: ${data.source_count}\n`;
      output += `- **提炼规则数**: ${data.rules.length}\n`;
      output += `- **提炼方法**: ${data.distill_method}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
