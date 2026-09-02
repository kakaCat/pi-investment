/**
 * WeeklyReportTool - M6 学习飞轮周报工具
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface WeeklyReportParams {
  week_start?: string;
  week_end?: string;
  format?: 'json' | 'markdown';
}

export interface WeeklyReportResult {
  period: {
    start: string;
    end: string;
    weekNum: number;
    year: number;
  };
  summary: Record<string, any>;
  signals: Record<string, any>;
  attribution: Record<string, any>;
  regimeChanges: any[];
  highlights: string[];
  recommendations: string[];
  markdown: string;
}

export const weeklyReportPrompt: ToolPrompt<WeeklyReportParams> = {
  description: 'M6 学习飞轮周报：汇总指定周的交易表现、信号质量、规则归因、组合盈亏归因与进化事件。用于：周日 12:00 周报定时任务、周报生成与飞书推送。',
  useCases: [
    'weekly-report-m6 定时任务：生成并推送学习飞轮周报（周日 12:00）',
    '手动查看某周的学习飞轮周报',
    '复盘时对比多周信号质量与规则归因',
  ],
  notes: [
    '调用后端 GET /api/reports/weekly（默认上周一至上周日；不传 week_start/week_end 取最近一期）',
    'format=markdown 时返回格式化周报全文，便于直接引用/推送',
    '周报含：信号统计（A/B/C 分级）、规则归因（R-xxx 胜率）、组合盈亏归因、regime 变化、亮点与建议',
  ],
  relatedTools: ['feishu_notify', 'daily_distill', 'validation_gate', 'memory_write'],
  parameters: {
    week_start: {
      type: 'string',
      description: '周开始日期 YYYY-MM-DD（默认上周一）',
    } as ParameterDefinition,

    week_end: {
      type: 'string',
      description: '周结束日期 YYYY-MM-DD（默认上周日）',
    } as ParameterDefinition,

    format: {
      type: 'string',
      description: '输出格式：markdown=全文（默认，便于汇报）；json=结构化数据',
      enum: ['json', 'markdown'],
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '生成上周周报（默认）',
      params: {},
      expectedResult: '返回最近一期周报的 markdown 全文与结构化数据',
    },
    {
      title: '指定周',
      params: {
        week_start: '2026-08-24',
        week_end: '2026-08-30',
      },
      expectedResult: '返回该周周报',
    },
  ],
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        period: { type: 'object', additionalProperties: true },
        summary: { type: 'object', additionalProperties: true },
        signals: { type: 'object', additionalProperties: true },
        attribution: { type: 'object', additionalProperties: true },
        regimeChanges: { type: 'array', items: { type: 'object', additionalProperties: true } },
        highlights: { type: 'array', items: { type: 'string' } },
        recommendations: { type: 'array', items: { type: 'string' } },
        markdown: { type: 'string' },
      },
    },
    render: (_args: WeeklyReportParams, data: any) => {
      const md = data?.markdown;
      return [{
        type: 'text',
        text: md && md.length > 0 ? md : JSON.stringify(data ?? {}, null, 2),
      }];
    },
  },
};
