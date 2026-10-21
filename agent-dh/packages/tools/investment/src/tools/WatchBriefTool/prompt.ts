import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchBriefParams { symbol: string; }

export const watchBriefPrompt: ToolPrompt<WatchBriefParams, any> = {
  description:
    '单标的盯盘简报（一屏看懂「这只票现在该看什么」）：现价/成本/浮盈、每个启用规则及距触发距离、' +
    '未决触发（pending/escalated/meta_review）、近 48 小时消息监控命中、抑噪状态。' +
    '适用于：持仓巡检、触发后评估、盘前快速过一遍持仓。' +
    '⚠️ 缺数据的维度会如实标注（quote_error 等），不得当"没有数据"用。',
  useCases: [
    { title: '持仓巡检', description: '一屏看某持仓的盯盘全景', example: 'watch_brief({ symbol: "000999" })' },
    { title: '触发评估', description: '触发通知到达后查完整上下文再决策', example: 'watch_brief({ symbol: "300750" })' },
  ],
  parameters: {
    symbol: { type: 'string', description: 'A 股 6 位代码（可带 .SH/.SZ 后缀）', example: '000999' },
  },
  output: {
    schema: { type: 'object', additionalProperties: true },
    render: (_args: any, data: any) => [
      { type: 'text', text: '盯盘简报（watch_brief）：\n' + JSON.stringify(data, null, 2) },
    ],
  },
};
