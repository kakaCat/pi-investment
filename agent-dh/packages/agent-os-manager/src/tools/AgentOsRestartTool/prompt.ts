import type { ToolPrompt } from '@pi-investment/core-tool';

export interface AgentOsRestartParams {
  force?: boolean;
  wait_startup_sec?: number;
}

export interface AgentOsRestartResult {
  success: boolean;
  steps: Array<{
    step: string;
    status: string;
    [key: string]: any;
  }>;
  final_status?: any;
  diagnosis?: {
    issues: string[];
    recommendation: string;
  };
  error?: string;
}

export const agentOsRestartPrompt: ToolPrompt<AgentOsRestartParams, AgentOsRestartResult> = {
  description: '重启 Agent OS 服务（智能流程：launchd kickstart 或手动 spawn→健康检查→失败诊断）',
  useCases: [
    '服务挂死需要重启恢复',
    '代码升级后重启应用新版本',
    '配置变更后重启生效',
    'launchd 守护进程重启',
  ],
  examples: [
    {
      title: '通过 launchd 重启成功',
      params: {
        force: false,
        wait_startup_sec: 30,
      },
      expectedResult: '重启成功，5秒后健康检查通过 (PID: 23456)',
    },
    {
      title: '重启但启动失败',
      params: {
        force: false,
        wait_startup_sec: 30,
      },
      expectedResult: '重启失败：端口 8080 未监听，建议查看日志',
    },
  ],
  notes: [
    '💡 force=false 优先使用 launchd kickstart（推荐）',
    '💡 force=true 强制手动重启（杀进程+启动）',
    '⚠️ 重启失败时会自动诊断并给出建议',
    '⚠️ 默认等待 30 秒启动完成',
  ],
  relatedTools: ['agent_os_status', 'agent_os_logs'],
  parameters: {
    force: {
      type: 'boolean',
      description: '是否强制手动重启（杀进程+启动）。false（默认）：优先 launchd kickstart',
      default: false,
      example: false,
    },
    wait_startup_sec: {
      type: 'integer',
      description: '等待启动完成的最大秒数，默认 30',
      default: 30,
      example: 30,
    },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        success: { type: 'boolean', description: '是否重启成功' },
        steps: {
          type: 'array',
          description: '重启步骤',
          items: { type: 'object', additionalProperties: true },
        },
        final_status: { type: 'object', description: '最终状态', additionalProperties: true },
        diagnosis: {
          type: 'object',
          description: '失败诊断',
          properties: {
            issues: { type: 'array', items: { type: 'string' } },
            recommendation: { type: 'string' },
          },
        },
        error: { type: 'string', description: '错误信息' },
      },
      additionalProperties: true,
    },
  },
};
