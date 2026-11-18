import type { ToolPrompt } from '@pi-investment/core-tool';

export interface MarketAlertParams {
  level?: 'all' | 'high' | 'medium' | 'low';
  limit?: number;
}

export const marketAlertPrompt: ToolPrompt<MarketAlertParams> = {
  name: 'market_alert',
  description: '获取系统生成的市场告警：异常波动、重大事件、风险信号，按触发时间倒序返回。适用于：盘前/盘中定期查看市场异常动态。notify_worthy=true 才是新出现/内容变化的新提醒；false 的持续告警仍代表风险存在，但不得重复当作新风险。告警是风险线索，high 级别应结合证据窗口评估是否影响持仓。',

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
          triggered_at: { type: 'string', description: '首次触发时间；持续告警的最近一次见数据时间另见 last_seen_at' },
          notify_worthy: { type: 'boolean', description: '仅 true 表示新出现或内容变化，需要按新风险提醒；false 不重复提醒' },
          notification_reason: { type: 'string', description: 'new_or_changed / unchanged / dedup_error' },
          dedup_status: { type: 'string', description: '去重状态；error 时只保持风险可见，不作为新告警' },
          window: { type: 'string', description: '资金证据窗口，如 trailing_5d_cumulative / single_day' },
          start: { type: 'string', description: '证据窗口开始日' },
          end: { type: 'string', description: '证据窗口结束日' },
          as_of: { type: 'string', description: '实际数据最新时点，不是轮询时间' },
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
    'high 级别告警建议优先处理，评估是否影响持仓；但只有 notify_worthy=true 才作为新事件提醒',
    'notify_worthy=false 且 notification_reason=unchanged：风险仍活跃但内容未变，不重复告警；dedup_error：状态不可读，先复核状态而非放大提醒',
    'trailing_5d_cumulative 是闭区间 5 个日历日的历史累计，不是当日风险；single_day 才代表真实单日数据',
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
