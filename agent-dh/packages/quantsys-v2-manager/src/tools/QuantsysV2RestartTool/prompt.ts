import type { ToolPrompt } from '@pi-investment/core-tool';

export interface QuantsysV2RestartParams {
  force?: boolean;
  wait_startup_sec?: number;
}

export interface QuantsysV2RestartResult {
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

export const quantsysV2RestartPrompt: ToolPrompt<QuantsysV2RestartParams, QuantsysV2RestartResult> = {
  description: '重启 quantsys-v2 后端服务（智能流程：停止→验证→启动→健康检查→失败诊断）',
  useCases: [
    '服务挂死需要重启恢复',
    '代码升级后重启应用新版本',
    '配置变更后重启生效',
    '端口占用冲突需要强制重启',
  ],
  examples: [
    {
      title: '正常重启成功',
      params: {
        force: false,
        wait_startup_sec: 30,
      },
      expectedResult: '重启成功，5秒后健康检查通过 (PID: 12346)',
    },
    {
      title: '强制重启但启动失败',
      params: {
        force: true,
        wait_startup_sec: 30,
      },
      expectedResult: '重启失败：端口 5001 未监听，PostgreSQL 未就绪',
    },
  ],
  notes: [
    '💡 force=false 优先优雅停止（SIGTERM + 等待）',
    '💡 force=true 强制杀进程（SIGKILL）',
    '⚠️ 重启失败时会自动诊断并给出建议',
    '⚠️ 默认等待 30 秒启动完成',
  ],
  relatedTools: ['quantsys_v2_status', 'quantsys_v2_logs'],
  parameters: {
    force: {
      type: 'boolean',
      description: '是否强制杀进程。false（默认）：优雅停止；true：强制 SIGKILL',
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
