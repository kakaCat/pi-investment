/**
 * SelfFinalizeTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SelfFinalizeParams {
  reason: string;
  save_state?: boolean;
}

export interface SelfFinalizeResult {
  success: boolean;
  message: string;
  finalized: boolean;
}

export const selfFinalizePrompt: ToolPrompt<SelfFinalizeParams, SelfFinalizeResult> = {
  description: '终止 Agent 生命周期。用于优雅关闭、保存状态并退出。',
  useCases: ['优雅关闭', '任务完成后退出', '保存状态并终止'],
  examples: [
    {
      title: '保存状态并终止',
      params: { reason: '任务完成', save_state: true },
      expectedResult: '返回终止确认',
    },
  ],
  params: {
    reason: { type: 'string', required: true, description: '终止原因' },
    save_state: { type: 'boolean', required: false, description: '是否保存状态' },
  },
  output: {
    render: (args, data) => {
      let output = '## 🛑 终止已调度\n\n';
      output += `- **原因**: ${args.reason}\n`;
      output += `- **保存状态**: ${args.save_state ? '是' : '否'}\n`;
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
