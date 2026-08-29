import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchManageParams {
  action: 'create' | 'enable' | 'disable' | 'delete';
  rule_id?: number;
  name?: string;
  symbol?: string;
  condition?: string;
}

export const watchManagePrompt: ToolPrompt<WatchManageParams> = {
  name: 'watch_manage',
  description: '管理盯盘规则（写操作）：创建、启用、禁用、删除。规则触发后系统自动通知，适合价格预警、涨跌幅预警、成交量异常监控等场景。创建前建议先用 watch_list 确认无重复规则。',

  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['create', 'enable', 'disable', 'delete'],
        description: '操作类型。create：创建新规则（需同时传 name、symbol、condition）；enable / disable / delete：对已有规则操作（需传 rule_id）',
      },
      rule_id: {
        type: 'integer',
        description: '规则ID，enable/disable/delete 时必填，通过 watch_list 获取',
      },
      name: {
        type: 'string',
        description: '规则名称，create 时必填，如 "茅台价格突破2000"',
      },
      symbol: {
        type: 'string',
        description: '监控的股票代码，create 时必填，如 600519',
      },
      condition: {
        type: 'string',
        description: '触发条件表达式，create 时必填。支持：price>100（突破价格）、price<90（跌破价格）、change_pct>5（涨幅超5%）、change_pct<-3（跌幅超3%）',
      },
    },
    required: ['action'],
  },

  returns: {
    type: 'object',
    properties: {
      success: { type: 'boolean', description: '是否成功' },
      rule_id: { type: 'integer', description: '规则ID' },
      action: { type: 'string', description: '执行的操作' },
      message: { type: 'string', description: '结果消息' },
    },
    description: '操作结果',
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
      title: '涨跌幅预警',
      description: '监控异常波动，及时发现机会或风险',
      example: 'condition="change_pct>5" 监控单日涨幅超 5%',
    },
    {
      title: '规则生命周期管理',
      description: '创建后可随时启用/禁用/删除',
      example: '短期监控完成后 disable，长期无用则 delete',
    },
  ],

  notes: [
    '2026-08-27 修复：create 时缺少必填参数会在前端校验，提供清晰的错误提示',
    'condition 表达式支持：price>N、price<N、change_pct>N、change_pct<-N',
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
