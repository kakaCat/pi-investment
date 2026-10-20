import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchTriggersParams {
  /** 只看某标的（6 位代码，可选） */
  symbol?: string;
  /** 只看待处置/已升级等：pending|escalated|meta_review|handled|... */
  disposition?: string;
  /** 增量水位：只返回该 ISO 时间之后的触发（轮询"有什么新信号"用） */
  since?: string;
  limit?: number;
}

export const watchTriggersPrompt: ToolPrompt<WatchTriggersParams, any> = {
  description:
    '盯盘触发查询/增量轮询。两种用法：① 查存量（disposition=pending 看待办清单）；' +
    '② **增量轮询**（带 since=上次查询时间）——框架的"信号感知"通道：轮询比等摘要唤醒更快。' +
    '⚠️ 失败必须显式报错，禁止把"接口挂了"当"没有新信号"。',
  useCases: [
    { title: '新信号轮询', description: '每 5-15 分钟问一次"since 之后有什么新触发"', example: 'watch_triggers({ since: "2026-10-20T10:00:00" })' },
    { title: '待办清单', description: '看全部未决触发（pending+escalated）', example: 'watch_triggers({ disposition: "pending" })' },
    { title: '单标的历史', description: '某标的触发史', example: 'watch_triggers({ symbol: "000999", limit: 20 })' },
  ],
  parameters: {
    symbol: { type: 'string', required: false, description: '6 位代码', example: '000999' },
    disposition: { type: 'string', required: false, description: '处置状态过滤', example: 'pending' },
    since: { type: 'string', required: false, description: 'ISO 时间水位（本地时区）', example: '2026-10-20T10:00:00' },
    limit: { type: 'number', required: false, description: '条数上限', default: 50 },
  },
  output: {
    schema: { type: 'object', additionalProperties: true },
    render: (_args: any, data: any) => [
      { type: 'text', text: '盯盘触发查询（watch_triggers）：\n' + JSON.stringify(data, null, 2) },
    ],
  },
};
