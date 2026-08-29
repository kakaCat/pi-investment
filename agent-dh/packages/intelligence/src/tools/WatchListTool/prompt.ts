import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchListParams {
  // 无参数
}

export const watchListPrompt: ToolPrompt<WatchListParams> = {
  name: 'watch_list',
  description: '获取全部盯盘规则：监控标的、触发条件、启用状态、历史触发次数。盯盘规则在条件触发时会自动推送通知，无需人工盯盘。适用于：查看已有监控覆盖面、管理规则前确认 rule_id。创建/启停/删除规则用 watch_manage。',

  parameters: {
    type: 'object',
    properties: {},
    required: [],
  },

  returns: {
    type: 'array',
    items: {
      type: 'object',
      properties: {
        id: { type: 'integer', description: '规则ID' },
        name: { type: 'string', description: '规则名称' },
        symbol: { type: 'string', description: '监控的股票代码' },
        condition: { type: 'string', description: '触发条件，如 price>100、change_pct>5' },
        enabled: { type: 'boolean', description: '是否启用' },
        created_at: { type: 'string', description: '创建时间' },
        updated_at: { type: 'string', description: '更新时间' },
        triggered_count: { type: 'integer', description: '历史触发次数' },
      },
    },
    description: '盯盘规则列表',
  },

  examples: [
    {
      scenario: '查看所有盯盘规则',
      params: {},
      expectedBehavior: '返回当前所有盯盘规则的列表，包括启用和禁用的规则',
    },
    {
      scenario: '管理规则前确认 rule_id',
      params: {},
      expectedBehavior: '先调用 watch_list 获取规则 ID，再调用 watch_manage 进行启用/禁用/删除操作',
    },
  ],

  useCases: [
    {
      title: '查看监控覆盖面',
      description: '盘前查看已有监控规则，确认重要标的是否有监控',
      example: '查看是否有茅台价格突破 2000 的监控规则',
    },
    {
      title: '管理前确认 ID',
      description: '在启用/禁用/删除规则前，先获取规则 ID',
      example: '先 watch_list 找到规则 ID，再 watch_manage 删除',
    },
  ],

  notes: [
    '盯盘规则是系统自动监控机制，触发时会推送通知',
    'triggered_count 记录历史触发次数，可用于评估规则有效性',
    '禁用的规则仍会返回，通过 enabled 字段区分',
  ],

  relatedTools: [
    {
      name: 'watch_manage',
      relationship: '创建、启用、禁用、删除盯盘规则',
      useCase: 'watch_list 获取规则 ID 后，用 watch_manage 管理规则',
    },
    {
      name: 'market_alert',
      relationship: '获取系统告警',
      useCase: '盯盘规则触发后会生成告警，通过 market_alert 查看',
    },
  ],
};
