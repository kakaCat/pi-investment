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
  description: '重启 Agent 生命周期。用于应用重大配置变更或从异常状态恢复。重启由包内独立重启器（dist/restarter.mjs，不依赖外部脚本）执行：kill 旧进程 → start.sh 拉起 → 端口健康检查 → 失败自动回滚 base 分支重拉。重启前自动把未提交改动存入 wip 分支检查点；重启后向发起会话自动注入续跑消息（含上次消息内容）。每小时最多 10 次。⚠️ 调用后当前会话会中断（进程被杀），这是正常行为，数秒后刷新页面即可看到新进程。',
  useCases: ['应用配置变更', '从异常状态恢复', '执行维护任务'],
  examples: [
    {
      title: '重启并保留上下文',
      params: { reason: '应用新配置', preserve_context: true },
      expectedResult: '返回重启确认',
    },
  ],
  parameters: {
    reason: { type: 'string', required: true, description: '重启原因' },
    preserve_context: { type: 'boolean', required: false, description: '是否保留上下文' },
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        message: { type: 'string' },
        restart_scheduled: { type: 'boolean' },
      },
    },
    render: (args, data) => {
      let output = '## 🔄 重启已调度\n\n';
      output += `- **原因**: ${args.reason}\n`;
      output += `- **保留上下文**: ${args.preserve_context ? '是' : '否'}\n`;
      output += `- ${data.message}\n`;
      return [{ type: 'text', text: output }];
    },
  },
};
