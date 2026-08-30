/**
 * LearningTrackTool - 提示词定义
 *
 * 工具描述：手动追踪执行经验
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export type ActionType = 'trade' | 'analysis' | 'strategy_execution' | 'system_operation' | 'custom';

export interface LearningTrackParams {
  action_type: ActionType;
  context: Record<string, any>;
  outcome: {
    success: boolean;
    metrics?: Record<string, any>;
    error?: string;
  };
  reward: number;
  reasoning_trace?: string;
}

export interface LearningTrackResult {
  success: boolean;
  experience_id: string;
  message: string;
}

export const learningTrackPrompt: ToolPrompt<LearningTrackParams, LearningTrackResult> = {
  description:
    '手动追踪执行经验（写操作）。自动追踪已覆盖主要工具，仅在需要记录特殊经验时手动调用。' +
    '适用于：记录复杂决策过程、非标准工具调用、用户反馈。',

  useCases: [
    '记录复杂的交易决策过程',
    '追踪非标准工具的调用结果',
    '记录用户反馈和改进建议',
  ],

  examples: [
    {
      title: '记录交易决策',
      params: {
        action_type: 'trade',
        context: { symbol: '600000.SH', strategy_id: 'momentum_v1' },
        outcome: { success: true, metrics: { profit: 1200 } },
        reward: 0.8,
      },
      expectedResult: '返回经验ID和确认消息',
    },
  ],

  params: {
    action_type: {
      type: 'string',
      required: true,
      description: '行动类型：trade（交易）、analysis（分析）、strategy_execution（策略执行）、system_operation（系统操作）、custom（自定义）',
    },
    context: {
      type: 'object',
      required: true,
      description: '上下文信息，如 {symbol, strategy_id, market_phase}',
    },
    outcome: {
      type: 'object',
      required: true,
      description: '结果：{success: boolean, metrics?: object, error?: string}',
    },
    reward: {
      type: 'number',
      required: true,
      description: '奖励值（-1.0 到 1.0），表示结果的好坏程度',
    },
    reasoning_trace: {
      type: 'string',
      required: false,
      description: '推理过程的文本记录',
    },
  },

  output: {
    render: (args, data) => {
      let output = '## ✅ 经验已记录\n\n';
      output += `- **经验ID**: ${data.experience_id}\n`;
      output += `- **行动类型**: ${args.action_type}\n`;
      output += `- **奖励值**: ${args.reward}\n`;
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
