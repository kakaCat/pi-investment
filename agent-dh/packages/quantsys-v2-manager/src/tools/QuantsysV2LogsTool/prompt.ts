import type { ToolPrompt } from '@pi-investment/core-tool';

export interface QuantsysV2LogsParams {
  lines?: number;
  grep?: string;
}

export interface QuantsysV2LogsResult {
  lines: string[];
  total: number;
  _metadata: {
    log_file: string;
    last_modified: string;
    age_hours: number;
    is_stale: boolean;
    warning: string | null;
  };
  error?: string;
  rate_limited?: boolean;
}

export const quantsysV2LogsPrompt: ToolPrompt<QuantsysV2LogsParams, QuantsysV2LogsResult> = {
  description: '查看 quantsys-v2 最近日志（默认最后50行），可按关键词过滤。返回结果包含日志行 + 元数据（文件路径、最后更新时间、是否陈旧）',
  useCases: [
    '查看最近错误日志：grep="ERROR"',
    '诊断服务启动失败原因',
    '检查日志是否陈旧（超过24小时未更新）',
    '过滤特定关键词：如 exception、timeout 等',
  ],
  examples: [
    {
      title: '查看最后50行日志（正常）',
      params: {
        lines: 50,
      },
      expectedResult: '2 行日志：Server started, Database connected（日志新鲜，0.5h）',
    },
    {
      title: '过滤错误日志，发现日志陈旧',
      params: {
        lines: 20,
        grep: 'ERROR',
      },
      expectedResult: '2 行错误日志 ⚠️ 日志已 27 小时未更新',
    },
  ],
  notes: [
    '💡 默认显示最后 50 行',
    '💡 grep 支持大小写不敏感搜索',
    '⚠️ 日志超过 24 小时未更新会标记为陈旧',
    '⚠️ 频繁调用会触发速率限制（60秒内最多1次）',
  ],
  relatedTools: ['quantsys_v2_status', 'quantsys_v2_restart'],
  parameters: {
    lines: {
      type: 'integer',
      description: '显示最后 N 行，默认 50',
      default: 50,
      example: 50,
    },
    grep: {
      type: 'string',
      description: '过滤关键词（大小写不敏感），如 "ERROR"、"exception"',
      example: 'ERROR',
    },
  },
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        lines: { type: 'array', items: { type: 'string' }, description: '日志行' },
        total: { type: 'integer', description: '日志行数' },
        _metadata: {
          type: 'object', additionalProperties: true,
          description: '元数据',
          properties: {
            log_file: { type: 'string' },
            last_modified: { type: 'string' },
            age_hours: { type: 'number' },
            is_stale: { type: 'boolean' },
            warning: { type: 'string' },
          },
        },
        error: { type: 'string', description: '错误信息' },
        rate_limited: { type: 'boolean', description: '是否触发速率限制' },
      },
      additionalProperties: true,
    },
  },
};
