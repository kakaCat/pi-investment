import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchManageParams {
  action: 'create' | 'enable' | 'disable' | 'delete';
  rule_id?: number;
  name?: string;
  symbol?: string;
  condition?: string;
  reason?: string;
  cost_price?: number;
  account?: string;
  expires_at?: string;
}

export const watchManagePrompt: ToolPrompt<WatchManageParams> = {
  name: 'watch_manage',
  description: '管理盯盘规则（写操作）：创建、启用、禁用、删除。规则触发后系统自动通知，适合价格预警、涨跌幅预警、持仓盈亏止损止盈、成交量异动、瞬时涨速监控等场景。持仓股开仓后必须立即挂止损规则（换仓补位纪律）。创建前建议先用 watch_list 确认无重复规则。',

  parameters: {
    action: {
      type: 'string',
      enum: ['create', 'enable', 'disable', 'delete'],
      description: '操作类型。create：创建新规则（需同时传 name、symbol、condition）；enable / disable / delete：对已有规则操作（需传 rule_id）',
      required: true,
    },
    rule_id: {
      type: 'integer',
      description: '规则ID，enable/disable/delete 时必填，通过 watch_list 获取',
    },
    name: {
      type: 'string',
      description: '规则名称，create 时必填，如 "茅台突破2000"',
    },
    symbol: {
      type: 'string',
      description: '监控的股票代码，create 时必填，如 600519',
    },
    condition: {
      type: 'string',
      description: '触发条件表达式，create 时必填。支持：price>100（上破价格）、price<90（下破价格）、change_pct>5（涨幅超5%）、change_pct<-3（跌幅超3%）、pnl_pct<-8（持仓盈亏跌至-8%，需 cost_price 或不传自动取持仓成本）、pnl_pct>10（止盈）、volume_surge>4（成交量≥同期20日均量4倍）、velocity>2/15（15分钟内波动≥2%）',
    },
    reason: {
      type: 'string',
      description: '监视理由（强烈建议填写）：为什么盯这只票、触发后该怎么决策。触发通知会带出此文本，供未来自己/其他窗口回溯决策上下文',
    },
    cost_price: {
      type: 'number',
      description: '成本价，pnl_pct 条件用。不传时自动取 account 持仓成本；无持仓则报错',
    },
    account: {
      type: 'string',
      description: '账户名（默认 agent_virtual），pnl_pct 自动取成本价时指定持仓账户',
    },
    expires_at: {
      type: 'string',
      description: '规则过期时间 ISO 格式（如 2026-09-30T15:00:00），过期自动失效，避免僵尸规则',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        success: { type: 'boolean', description: '是否成功' },
        rule_id: { type: 'integer', description: '规则ID' },
        action: { type: 'string', description: '执行的操作' },
        message: { type: 'string', description: '结果消息' },
      },
      description: '操作结果',
      additionalProperties: true,
    },
    render: (_args: WatchManageParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    {
      scenario: '创建价格突破监控',
      params: {
        action: 'create',
        name: '茅台价格突破2000',
        symbol: '600519',
        condition: 'price>2000',
      },
      expectedBehavior: '创建新规则，返回规则 ID',
    },
    {
      scenario: '创建涨幅监控',
      params: {
        action: 'create',
        name: '宁德时代涨幅超5%',
        symbol: '300750',
        condition: 'change_pct>5',
      },
      expectedBehavior: '创建涨幅超过5%的监控规则',
    },
    {
      scenario: '持仓止损（pnl_pct，自动取成本）',
      params: {
        action: 'create',
        name: '中石油浮亏-8%止损',
        symbol: '601857',
        condition: 'pnl_pct<-8',
        reason: '8/31 突破买入，大盘蓝筹止损线-8%',
      },
      expectedBehavior: '自动取持仓成本价，创建盈亏止损规则',
    },
    {
      scenario: '量能异动监控',
      params: {
        action: 'create',
        name: '汇川技术量能异动4倍',
        symbol: '300124',
        condition: 'volume_surge>4',
        reason: '机器人观察池标的，放量异动评估买入',
      },
      expectedBehavior: '成交量达同期均量4倍时触发',
    },
    {
      scenario: '启用规则',
      params: {
        action: 'enable',
        rule_id: 123,
      },
      expectedBehavior: '启用指定规则',
    },
    {
      scenario: '删除规则',
      params: {
        action: 'delete',
        rule_id: 123,
      },
      expectedBehavior: '删除指定规则',
    },
  ],

  useCases: [
    {
      title: '价格预警',
      description: '监控重要标的价格突破或跌破关键位',
      example: 'condition="price>2000" 监控茅台突破 2000 元',
    },
    {
      title: '持仓止损止盈（换仓补位纪律）',
      description: '新开仓/换仓后立即挂 pnl_pct 规则：蓝筹-8%、成长-10%、小盘-12%；止盈+10%',
      example: 'condition="pnl_pct<-8" + reason="买入理由"，成本价自动取持仓',
    },
    {
      title: '量能异动/瞬时涨速',
      description: 'volume_surge>4 抓放量异动；velocity>2/15 抓 15 分钟急拉急跌',
      example: 'condition="volume_surge>4"（阈值按噪音迭代：触发太频繁就上调倍数）',
    },
    {
      title: '规则生命周期管理',
      description: '创建后可随时启用/禁用/删除；建议设 expires_at 避免僵尸规则',
      example: '短期监控完成后 disable，长期无用则 delete',
    },
  ],

  notes: [
    '2026-09-01 扩展：新增 pnl_pct（持仓盈亏%）、volume_surge（量能倍数）、velocity（窗口波动）条件，新增 reason（监视理由）/cost_price/expires_at 参数——对标 agent-ts watch 能力，后端引擎原生支持',
    'condition 表达式：price>N、price<N、change_pct>N、change_pct<-N、pnl_pct>N、pnl_pct<-N、volume_surge>N、velocity>N/M（M=窗口分钟）',
    'pnl_pct 不传 cost_price 时自动取 account（默认 agent_virtual）持仓成本；无持仓会报错',
    '告警阈值按噪音迭代：触发太频繁（一天多次）就上调阈值，而不是忍受噪音',
    '创建前建议先 watch_list 确认无重复规则',
    'enable/disable/delete 操作需要先通过 watch_list 获取 rule_id',
  ],

  relatedTools: [
    {
      name: 'watch_list',
      relationship: '获取规则列表和 rule_id',
      useCase: '管理规则前先 watch_list 获取 rule_id',
    },
    {
      name: 'market_alert',
      relationship: '查看规则触发的告警',
      useCase: '规则触发后通过 market_alert 查看告警详情',
    },
  ],
};
