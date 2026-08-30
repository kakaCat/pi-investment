/**
 * SelfRestartTool - 提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SelfRestartParams {
  reason: string;
  preserve_context?: boolean;
}

export interface SelfRestartResult {
  success: boolean;
  message: string;
  restart_scheduled: boolean;
}

export const selfRestartPrompt: ToolPrompt<SelfRestartParams, SelfRestartResult> = {
  description: '重启 Agent 生命周期。用于应用重大配置变更或从异常状态恢复。',
  useCases: ['应用配置变更', '从异常状态恢复', '执行维护任务'],
  examples: [
    {
      title: '重启并保留上下文',
      params: { reason: '应用新配置', preserve_context: true },
      expectedResult: '返回重启确认',
    },
  ],
  params: {
    reason: { type: 'string', required: true, description: '重启原因' },
    preserve_context: { type: 'boolean', required: false, description: '是否保留上下文' },
  },
  output: {
    render: (args, data) => {
      let output = '## 🔄 重启已调度\n\n';
      output += `- **原因**: ${args.reason}\n`;
      output += `- **保留上下文**: ${args.preserve_context ? '是' : '否'}\n`;
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
