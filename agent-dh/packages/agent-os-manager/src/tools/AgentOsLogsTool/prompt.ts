import type { ToolPrompt } from '@pi-investment/core-tool';

export interface AgentOsLogsParams {
  lines?: number;
  grep?: string;
  source?: string;
}

export interface AgentOsLogsResult {
  lines: string[];
  total: number;
  source: string;
  error?: string;
}

export const agentOsLogsPrompt: ToolPrompt<AgentOsLogsParams, AgentOsLogsResult> = {
  description: '查看 Agent OS 最近日志（默认最后50行），可按关键词过滤',
  useCases: [
    '查看最近错误日志：grep="error"',
    '诊断服务启动失败原因',
    '查看主服务日志：source="main"',
    '查看调度器日志：source="scheduler"',
  ],
  examples: [
    {
      title: '查看主服务日志',
      params: {
        lines: 50,
        source: 'main',
      },
      expectedResult: '2 行日志：Server started, listening on port 8080',
    },
    {
      title: '过滤错误日志',
      params: {
        lines: 20,
        grep: 'error',
        source: 'main',
      },
      expectedResult: '1 行错误：Database connection failed',
    },
  ],
  notes: [
    '💡 默认显示最后 50 行',
    '💡 grep 支持大小写不敏感搜索（JS includes，非系统 grep）',
    '💡 source 可选：main（默认）、scheduler',
    '💡 2026-08-31 起按 mtime 最新优先选活跃日志（launchd 托管时读 launchd-stdout/stderr）；读取失败或无日志时返回建议 bash 命令（plan 兜底）',
  ],
  relatedTools: ['agent_os_status', 'agent_os_restart'],
  parameters: {
    lines: {
      type: 'integer',
      description: '显示最后 N 行（1-1000），默认 50',
      default: 50,
      minimum: 1,
      maximum: 1000,
      example: 50,
    },
    grep: {
      type: 'string',
      description: '过滤关键词（大小写不敏感），如 "error"、"warning"',
      example: 'error',
    },
    source: {
      type: 'string',
      description: '日志来源：main（主服务日志，默认）、scheduler（调度器日志）',
      default: 'main',
      example: 'main',
    },
  },
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        lines: { type: 'array', items: { type: 'string' }, description: '日志行' },
        total: { type: 'integer', description: '日志行数' },
        source: { type: 'string', description: '日志文件路径' },
        error: { type: 'string', description: '错误信息' },
      },
      additionalProperties: true,
    },
  },
};
