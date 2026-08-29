import type { ToolPrompt } from '@pi-investment/core-tool';

export interface MarketAlertParams {
  level?: 'all' | 'high' | 'medium' | 'low';
  limit?: number;
}

export const marketAlertPrompt: ToolPrompt<MarketAlertParams> = {
  name: 'market_alert',
  description: '获取系统生成的市场告警：异常波动、重大事件、风险信号，按触发时间倒序返回。适用于：盘前/盘中定期查看市场异常动态。告警是系统主动发现的风险线索，high 级别应优先处理并评估是否影响持仓。',

  parameters: {
    level: {
      type: 'string',
      enum: ['all', 'high', 'medium', 'low'],
      description: '告警级别过滤。all（默认）：全部；high：高风险，建议优先处理；medium：中等；low：低风险',
    },
    limit: {
      type: 'integer',
      description: '返回数量上限，默认 20',
    },
  },

  output: {
    schema: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        properties: {
          id: { type: 'string', description: '告警ID' },
          level: { type: 'string', description: '级别：high/medium/low' },
          title: { type: 'string', description: '告警标题' },
          description: { type: 'string', description: '详细描述' },
          symbol: { type: 'string', description: '相关股票代码' },
          triggered_at: { type: 'string', description: '触发时间' },
        },
        additionalProperties: true,
      },
      description: '告警列表',
    },
    render: (_args: MarketAlertParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '查看所有告警',
      params: { level: 'all', limit: 20 },
      expectedBehavior: '返回所有级别的告警，最多 20 条',
    },
    {
      scenario: '查看高风险告警',
      params: { level: 'high', limit: 10 },
      expectedBehavior: '返回 high 级别告警，最多 10 条',
    },
    {
      scenario: '盘前快速巡视',
      params: { level: 'all', limit: 5 },
      expectedBehavior: '返回最近 5 条告警，快速了解市场动态',
    },
  ],

  useCases: [
    {
      title: '盘前风险巡视',
      description: '每日开盘前查看 high 级别告警，评估是否影响持仓',
      example: '查看持仓标的是否有高风险告警',
    },
    {
      title: '盘中动态监控',
      description: '盘中定期查看告警，及时发现异常波动',
      example: '每小时查看一次 all 级别告警',
    },
    {
      title: '事后复盘',
      description: '收盘后回顾告警，分析市场事件',
      example: '查看全天告警，分析哪些告警有效',
    },
  ],

  notes: [
    '告警按触发时间倒序返回（最新的在前）',
    'high 级别告警建议优先处理，评估是否影响持仓',
    '告警是系统主动发现的风险线索，结合 watch_list 规则触发生成',
  ],

  relatedTools: [
    {
      name: 'watch_list',
      relationship: '查看盯盘规则',
      useCase: '告警通常由盯盘规则触发，通过 watch_list 查看规则详情',
    },
    {
      name: 'position_list',
      relationship: '查看持仓',
      useCase: '发现持仓标的告警时，用 position_list 确认持仓情况',
    },
  ],
};
