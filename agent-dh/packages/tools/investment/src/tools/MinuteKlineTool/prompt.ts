/**
 * MinuteKlineTool - 分钟线（P1 微观结构，RFC 015）
 *
 * 背景（2026-09-11，w-f436d4ea）：下单无分钟级择时依据；现有 kline provider 里
 * 只有 akshare 支持分钟且为末位通道。本工具走后端多源故障转移
 * （腾讯/东财/新浪 + 本地 DB 兜底），并如实透出实际服务源与降级状态。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface MinuteKlineParams {
  symbol: string;
  period?: string;
  date?: string;
  limit?: number;
}

export const minuteKlinePrompt: ToolPrompt<MinuteKlineParams, any> = {
  name: 'minute_kline',
  description: '获取个股分钟级K线（多源故障转移：腾讯/东财/新浪 + 本地DB兜底）。适用于：①盘中择时（分时位置、量能节奏）；②执行拆单参考（R-003）；③判断当日价格相对均价/高低点的位置。注意事项：返回体含 source（实际服务源）/attempted_sources（尝试过的源）/degraded/stale/as_of（数据时点）——引用时必须标注来源与时点（R-013）；上游全失败时显式报错，禁止把空结果当"无成交"。',

  parameters: {
    symbol: { type: 'string', description: 'A股6位代码，如 600150', required: true },
    period: { type: 'string', description: "周期：1m/5m/15m/30m/60m（默认 5m）", enum: ['1m', '5m', '15m', '30m', '60m'] },
    date: { type: 'string', description: '交易日 YYYY-MM-DD（默认最近一个交易日）' },
    limit: { type: 'integer', description: '返回条数上限（默认 240，约一个交易日的 5 分钟线）' },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string' },
        period: { type: 'string' },
        count: { type: 'integer', description: '返回分钟线根数' },
        source: { type: 'string', description: '实际服务的数据源' },
        attempted_sources: { type: 'array', items: { type: 'string' }, description: '实际尝试过的数据源（降级链）' },
        degraded: { type: 'boolean' },
        stale: { type: 'boolean' },
        as_of: { type: 'string', description: '数据时点' },
      },
      additionalProperties: true,
    },
    render: (_args: MinuteKlineParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    { scenario: '看某股今日 5 分钟线', params: { symbol: '600150' }, expectedBehavior: '返回 240 根左右 5m K线 + source/as_of' },
    { scenario: '看 15 分钟线', params: { symbol: '600150', period: '15m' }, expectedBehavior: '返回 15m 粒度' },
  ],

  useCases: [
    { title: '盘中择时', description: '结合现价与分时均价/高低点判断介入位置', example: "minute_kline({ symbol: '600150', period: '5m' })" },
    { title: '执行参考', description: '为大单拆单提供流动性视角（配合 execution_estimate）', example: '估算参与率' },
  ],

  notes: [
    '2026-09-11 上线（P1/RFC 015）：分钟线本地表 quant.minute_klines 主键为 (symbol, trade_datetime)，仅存单一粒度，多周期由服务层处理。',
    'R-013：引用分时数据必须标注 source 与 as_of。',
    '数据源失败与空结果语义分离——失败即报错，不得当作"无成交"。',
  ],

  relatedTools: [
    { name: 'data_fetch_quote', relationship: '实时快照', useCase: '先看现价再用分钟线看路径' },
    { name: 'trading_status', relationship: '可交易性', useCase: '下单前先确认非停牌/涨跌停' },
  ],
};
