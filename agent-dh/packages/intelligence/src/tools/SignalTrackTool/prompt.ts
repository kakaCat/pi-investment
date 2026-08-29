import type { ToolPrompt } from '@pi-investment/core-tool';

export interface SignalTrackParams {
  action: 'record' | 'update' | 'report';
  symbol?: string;
  signal_date?: string;
  price?: number;
  source?: string;
  grade?: 'A' | 'B' | 'C';
  reason?: string;
  lookback_days?: number;
  start_date?: string;
  end_date?: string;
}

export const signalTrackPrompt: ToolPrompt<SignalTrackParams> = {
  name: 'signal_track',
  description: '信号质量追踪（M3-1）：record 记录买入信号（标的/价格/来源/分级），update 回填 5/10/20 日表现（盘后例程调用），report 统计胜率。用于：评估信号质量、选择优胜策略、验证门裁决。',

  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['record', 'update', 'report'],
        description: 'record=记录信号, update=回填表现, report=统计胜率',
      },
      symbol: {
        type: 'string',
        description: '股票代码（record 时必填）',
      },
      signal_date: {
        type: 'string',
        description: '信号日期 YYYY-MM-DD（record 时选填，默认今天）',
      },
      price: {
        type: 'number',
        description: '买入价格（record 时必填）',
      },
      source: {
        type: 'string',
        description: '信号来源（record 时必填）：strategy_execute / opportunity_scan / mainline_stocks / watch_rule',
      },
      grade: {
        type: 'string',
        enum: ['A', 'B', 'C'],
        description: '信号分级（record 时必填）：A=≥3维共振标准仓, B=2维或轻微矛盾半仓, C=单维只观察（参见 docs/architecture/signal-grading.md）',
      },
      reason: {
        type: 'string',
        description: '信号理由（record 时选填）',
      },
      lookback_days: {
        type: 'number',
        description: '回溯天数（update 时选填，默认30）',
      },
      start_date: {
        type: 'string',
        description: '开始日期（report 时选填）',
      },
      end_date: {
        type: 'string',
        description: '结束日期（report 时选填）',
      },
    },
    required: ['action'],
  },

  returns: {
    type: 'object',
    properties: {
      action: { type: 'string', description: '执行的动作' },
      result: { type: 'string', description: '结果摘要' },
      details: {
        type: 'object',
        description: '详细数据',
        additionalProperties: true,
      },
    },
    description: '信号追踪结果',
  },

  examples: [
    {
      scenario: '记录 A 级买入信号',
      params: {
        action: 'record',
        symbol: '600519',
        price: 1800,
        source: 'strategy_execute',
        grade: 'A',
        reason: '三维共振：基本面优秀+技术形态突破+市场主线',
      },
      expectedBehavior: '记录信号，返回 signal_id',
    },
    {
      scenario: '盘后回填表现',
      params: {
        action: 'update',
        lookback_days: 30,
      },
      expectedBehavior: '回填最近 30 天信号的 5/10/20 日表现',
    },
    {
      scenario: '统计 A 级信号胜率',
      params: {
        action: 'report',
        grade: 'A',
        start_date: '2026-01-01',
        end_date: '2026-08-28',
      },
      expectedBehavior: '返回 A 级信号的统计报告，包括 5/10/20 日胜率',
    },
  ],

  useCases: [
    {
      title: '买入时记录信号',
      description: '每次生成买入信号时调用 record，记录信号质量',
      example: '策略执行后记录 A 级信号，后续追踪表现',
    },
    {
      title: '盘后回填表现',
      description: '每日盘后例程调用 update，自动回填历史信号表现',
      example: '每日 16:00 调用 update，回填最近 30 天信号',
    },
    {
      title: '评估信号质量',
      description: '定期调用 report，统计各级别信号胜率',
      example: '每周统计 A/B/C 级信号胜率，筛选优质信号源',
    },
  ],

  notes: [
    'M3-1 信号质量追踪是验证门的数据基础',
    '信号分级 A/B/C 对应不同的仓位策略（标准仓/半仓/观察）',
    'update 操作会回填 5/10/20 日的涨跌幅表现',
    'report 统计胜率时，5 日胜率是最常用的指标',
  ],

  relatedTools: [
    {
      name: 'strategy_execute',
      relationship: '策略执行生成信号',
      useCase: '策略执行后用 signal_track record 记录信号',
    },
    {
      name: 'opportunity_scan',
      relationship: '机会扫描生成信号',
      useCase: '扫描到机会后用 signal_track record 记录',
    },
  ],
};
