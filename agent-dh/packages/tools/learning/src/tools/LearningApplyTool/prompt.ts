/**
 * LearningApplyTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface LearningApplyParams {
  rule_id: string;
  context: Record<string, any>;
  dry_run?: boolean;
}

export interface LearningApplyResult {
  success: boolean;
  applied: boolean;
  action_taken?: string;
  impact?: Record<string, any>;
  message: string;
}

export const learningApplyPrompt: ToolPrompt<LearningApplyParams, LearningApplyResult> = {
  description: '应用学习到的规则（写操作）。将提炼的规则应用到实际决策中，可以先 dry_run 预览效果。',
  useCases: ['应用学习到的交易规则', '测试新规则的效果', '自动应用改进建议'],
  examples: [
    {
      title: '试运行规则',
      params: { rule_id: 'rule_001', context: { symbol: '600000.SH' }, dry_run: true },
      expectedResult: '返回预期影响，不实际执行',
    },
  ],
  parameters: {
    rule_id: { type: 'string', required: true, description: '规则ID' },
    context: { type: 'object', required: true, additionalProperties: true, description: '应用上下文' },
    dry_run: { type: 'boolean', required: false, description: '是否仅模拟运行' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        applied: { type: 'boolean' },
        action_taken: { type: 'string' },
        impact: { type: 'object', additionalProperties: true },
        message: { type: 'string' },
      },
    },
    render: (args, data) => {
      let output = '## 🚀 规则应用结果\n\n';
      output += `- **规则ID**: ${args.rule_id}\n`;
      output += `- **执行模式**: ${args.dry_run ? '模拟运行' : '实际执行'}\n`;
      output += `- **是否应用**: ${data.applied ? '是' : '否'}\n`;
      if (data.action_taken) {
        output += `- **采取动作**: ${data.action_taken}\n`;
      }
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
