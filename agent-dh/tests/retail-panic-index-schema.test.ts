/**
 * RetailPanicIndexTool 输出 schema 回归测试（2026-09-10，w-23c70356）
 *
 * 故障现场：后端在某一维度数据源降级时该键返回 null（2026-09-10 实测
 * dimensions.retail_flow_score=null、raw.retail_flow_yi=null），而 prompt.ts 的 output schema
 * 把这些键声明为 `type: 'number'` → 工具返回即被校验拒绝：
 *   "value.dimensions.retail_flow_score must be a number"
 * 修复：_shape 采用"无数据即不出键"（compact），schema 侧键全部可选。
 *
 * 本测试自带一个与框架同口径的 schema 校验器（类型 + additionalProperties），
 * 因此它能抓住原实现（旧实现必然失败）。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RetailPanicIndexTool } from '../packages/competition/src/tools/RetailPanicIndexTool/RetailPanicIndexTool.js';
import { retailPanicIndexPrompt } from '../packages/competition/src/tools/RetailPanicIndexTool/prompt.js';

const OUT_SCHEMA: any = (retailPanicIndexPrompt as any).output.schema;

/** 与 dsh-tools 同口径的极简校验器：缺失=合法（可选），null 一律非法，对象键必须在 properties 内 */
function assertMatchesSchema(schema: any, value: any, path = 'value'): void {
  if (value === undefined) return;
  expect(value, `${path} 不得为 null（schema type=${schema?.type}）`).not.toBeNull();
  if (schema?.type === 'number') expect(typeof value, `${path} 应为 number`).toBe('number');
  if (schema?.type === 'string') expect(typeof value, `${path} 应为 string`).toBe('string');
  if (schema?.type === 'boolean') expect(typeof value, `${path} 应为 boolean`).toBe('boolean');
  if (schema?.type === 'object') {
    for (const [k, v] of Object.entries(value as Record<string, any>)) {
      const sub = schema.properties?.[k];
      if (!sub) {
        expect(schema.additionalProperties, `${path}.${k} 未在 schema 声明`).toBe(true);
        continue;
      }
      assertMatchesSchema(sub, v, `${path}.${k}`);
    }
  }
}

function collectNulls(value: any, path = 'value', acc: string[] = []): string[] {
  if (value === null) acc.push(path);
  else if (Array.isArray(value)) value.forEach((v, i) => collectNulls(v, `${path}[${i}]`, acc));
  else if (typeof value === 'object' && value !== undefined) {
    for (const [k, v] of Object.entries(value)) collectNulls(v, `${path}.${k}`, acc);
  }
  return acc;
}

// 2026-09-10 线上实测原始返回（curl /api/market/perception/panic-index）
const LIVE_PAYLOAD = {
  trade_date: '2026-09-10',
  panic_index: 80.1,
  level: 'panic',
  degraded: false,
  dimensions: {
    retail_flow_score: null,
    ad_ratio_score: 100.0,
    volume_score: 7.2,
    fear_greed_score: 100.0,
    volatility_score: 100.0,
  },
  raw: {
    retail_flow_yi: null,
    ad_ratio: 0.23,
    volume_ratio: 0.32,
    fear_greed_index: 0.0,
    volatility: 14.1,
  },
};

describe('RetailPanicIndexTool 输出 schema 兼容（null 维度）', () => {
  let tool: RetailPanicIndexTool;
  let mockClient: any;
  const ctx = {} as any;

  beforeEach(() => {
    mockClient = { getRetailPanicIndex: vi.fn() };
    tool = new RetailPanicIndexTool(mockClient);
  });

  it('线上含 null 维度的返回值必须通过输出 schema（回归：原实现在此失败）', async () => {
    mockClient.getRetailPanicIndex.mockResolvedValue(LIVE_PAYLOAD);
    const result: any = await (tool as any).execute({}, ctx);

    expect(collectNulls(result)).toEqual([]);
    assertMatchesSchema(OUT_SCHEMA, result);
    // 有数据的两维保留，无数据的零售资金流维度被剔除
    expect(result.dimensions.retail_flow_score).toBeUndefined();
    expect(result.dimensions.ad_ratio_score).toBe(100);
    expect(result.raw.retail_flow_yi).toBeUndefined();
    expect(result.raw.volatility).toBe(14.1);
    expect((retailPanicIndexPrompt as any).output.render({}, result)[0].text).toContain('散户资金流: N/A');
  });

  it('全维度缺失（数据源整体降级）时剔除 dimensions/raw 且仍通过 schema', async () => {
    mockClient.getRetailPanicIndex.mockResolvedValue({ trade_date: '2026-09-10', degraded: true, reason: '数据源不可用' });
    const result: any = await (tool as any).execute({}, ctx);

    expect(collectNulls(result)).toEqual([]);
    assertMatchesSchema(OUT_SCHEMA, result);
    expect(result.dimensions).toBeUndefined();
    expect(result.raw).toBeUndefined();
    const text = (retailPanicIndexPrompt as any).output.render({}, result)[0].text;
    expect(text).toContain('数据不可用');
    expect(text).toContain('数据源不可用');
  });

  it('series 模式取首行，同样不输出 null', async () => {
    mockClient.getRetailPanicIndex.mockResolvedValue({ days: 5, series: [LIVE_PAYLOAD, { ...LIVE_PAYLOAD, trade_date: '2026-09-07' }] });
    const result: any = await (tool as any).execute({ days: 5 }, ctx);

    expect(result.trade_date).toBe('2026-09-10');
    expect(collectNulls(result)).toEqual([]);
    assertMatchesSchema(OUT_SCHEMA, result);
  });

  it('NaN / 字符串等脏值一律剔除，不进入返回值', async () => {
    mockClient.getRetailPanicIndex.mockResolvedValue({
      trade_date: '2026-09-10',
      level: 'panic',
      degraded: false,
      panic_index: Number.NaN,
      dimensions: { ad_ratio_score: '100' as any, volume_score: 7.2 },
      raw: { ad_ratio: null, volatility: 14.1 },
    });
    const result: any = await (tool as any).execute({}, ctx);

    expect(collectNulls(result)).toEqual([]);
    assertMatchesSchema(OUT_SCHEMA, result);
    expect(result.panic_index).toBeUndefined();
    expect(result.dimensions.ad_ratio_score).toBeUndefined();
    expect(result.dimensions.volume_score).toBe(7.2);
  });
});
