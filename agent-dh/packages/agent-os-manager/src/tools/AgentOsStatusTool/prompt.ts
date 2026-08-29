import type { ToolPrompt } from '@pi-investment/core-tool';

export interface AgentOsStatusParams {
  // 无参数
}

export interface AgentOsStatusResult {
  running: boolean;
  pid: number;
  port: number;
  port_listening: boolean;
  health_ok: boolean;
  health_error: string | null;
  recent_errors: string[];
  timestamp: string;
}

export const agentOsStatusPrompt: ToolPrompt<AgentOsStatusParams, AgentOsStatusResult> = {
  description: '检查 Agent OS 服务状态：进程/端口/健康检查/最近日志错误',
  useCases: [
    '重启前后验证服务是否正常运行',
    '故障诊断：定位服务挂死、端口占用等问题',
    '日常巡检：确认 Agent OS 服务健康状态',
    '部署验证：确认新版本启动成功',
  ],
  examples: [
    {
      title: '服务正常运行',
      params: {},
      expectedResult: '运行中 (PID: 23456), 端口 8080 监听, 健康检查通过',
    },
    {
      title: '服务未运行',
      params: {},
      expectedResult: '未运行, 健康检查失败: Connection refused, 2 个最近错误',
    },
  ],
  notes: [
    '💡 无参数，直接调用即可',
    '💡 检查进程、端口、健康检查、最近错误',
    '⚠️ 健康检查失败时查看 recent_errors',
  ],
  relatedTools: ['agent_os_restart', 'agent_os_logs'],
  parameters: {},
  output: {
    schema: {
      type: 'object',
      properties: {
        running: { type: 'boolean', description: '进程是否运行' },
        pid: { type: 'number', description: '进程 PID，0 表示未运行' },
        port: { type: 'number', description: '服务端口' },
        port_listening: { type: 'boolean', description: '端口是否监听' },
        health_ok: { type: 'boolean', description: '健康检查是否通过' },
        health_error: { type: 'string', description: '健康检查错误信息' },
        recent_errors: { type: 'array', items: { type: 'string' }, description: '最近的错误日志' },
        timestamp: { type: 'string', description: '检查时间戳' },
      },
      additionalProperties: true,
    },
  },
};
