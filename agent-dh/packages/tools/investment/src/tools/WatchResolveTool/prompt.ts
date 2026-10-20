import type { ToolPrompt } from '@pi-investment/core-tool';

export interface WatchResolveParams {
  /** 触发记录 id（watch_triggers 返回的 id） */
  trigger_id: number;
  /** handled=已按结论动作 / ignored=知悉不动作（必须 reason）/ expired=失效归档 */
  disposition: 'handled' | 'ignored' | 'expired';
  /** 处置理由；ignored 必填（为什么不动 + 下次什么条件下才动） */
  reason?: string;
}

export const watchResolvePrompt: ToolPrompt<WatchResolveParams, any> = {
  description:
    '处置一条盯盘触发（闭环动作）：把未决触发收敛为终态并留理由。' +
    '这是「信号→决策→收敛」闭环的最后一棒——处置过的触发才进复盘统计。' +
    '⚠️ ignored 必须给 reason（下次什么条件下才动），空理由会被拒。' +
    '⚠️ 交易类执行（真下单）不走本工具——归 trading 工具；本工具只收敛「盯盘信号账」。',
  useCases: [
    { title: '收敛信号', description: '评估触发后记录结论', example: 'watch_resolve({ trigger_id: 3483, disposition: "handled", reason: "已减半锁利" })' },
    { title: '知悉不动', description: '带 NEXT 条件忽略', example: 'watch_resolve({ trigger_id: 3483, disposition: "ignored", reason: "缩量回踩，等放量再看" })' },
  ],
  parameters: {
    trigger_id: { type: 'number', description: '触发记录 id', example: 3483 },
    disposition: { type: 'string', description: 'handled|ignored|expired', example: 'handled' },
    reason: { type: 'string', required: false, description: '处置理由（ignored 必填）', example: '已减半锁利' },
  },
  output: {
    schema: { type: 'object', additionalProperties: true },
    render: (_args: any, data: any) => [
      { type: 'text', text: '触发处置结果（watch_resolve）：\n' + JSON.stringify(data, null, 2) },
    ],
  },
};
