/**
 * REQ-cf627b 验收测试（w-f436d4ea，2026-09-11）
 *
 * 覆盖三件事：
 *  1. factor_calculate 资金类因子「静默全 0」护栏（契约：使用 2026-09-11 从线上后端
 *     curl 到的**真实响应**，而非手写理想 payload —— 后者曾让同类 bug 通过测试）
 *  2. index_constituents 新工具（真实后端 LIVE）
 *  3. memory_recall_audit 新工具（真实后端 LIVE）
 *
 * 运行：cd agent-dh && npx vitest run tests/req-cf627b-verify.test.ts
 *      LIVE=1 npx vitest run tests/req-cf627b-verify.test.ts   # 追加真实后端用例
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { FactorCalculateTool } from '../packages/factor/src/tools/FactorCalculateTool/FactorCalculateTool.js';
import { IndexConstituentsTool } from '../packages/investment/src/tools/IndexConstituentsTool/IndexConstituentsTool.js';
import { RecallAuditTool } from '../packages/memory/src/tools/RecallAuditTool/RecallAuditTool.js';

const LIVE = process.env.LIVE === '1';
const ctx = {} as any;

// —— 真实样本 A：GET /api/stock/600150/factors（2026-09-11 02:5x 实测，截取）——
// 特征：资金类因子全部 factor_value=0.0 且 stale=false（新鲜的假数据）
const REAL_FACTORS_600150 = {
  symbol: '600150',
  stock_name: '中国船舶',
  market: 'A',
  current_price: 40.82,
  factor_ref_date: '2026-09-10',
  factors: [
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'super_large_net', factor_value: 0.0, stale_days: 0, stale: false },
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'large_net', factor_value: 0.0, stale_days: 0, stale: false },
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'main_net_inflow', factor_value: 0.0, stale_days: 0, stale: false },
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'fund_inflow_5d_sum', factor_value: 0.0, stale_days: 0, stale: false },
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'rsi14', factor_value: 79.65777878534294, stale_days: 0, stale: false },
    { symbol: '600150', factor_date: '2026-09-10', factor_name: 'ma20', factor_value: 35.17299999999997, stale_days: 0, stale: false },
  ],
};

// —— 真实样本 B：GET /api/stock/600150/fund-flow?days=5（同时间实测）——
const REAL_FUNDFLOW_600150 = {
  success: true,
  data: {
    symbol: '600150', days: 5,
    data: [{ date: '2026-09-09', closePrice: 39.51, changePct: 1.1003, mainNetInflow: 68372.88, mainNetInflowRate: 14.7382 }],
  },
};

function stubQv2(opts: { factors?: any; fundflow?: any } = {}) {
  return {
    calculateFactors: async () => opts.factors ?? REAL_FACTORS_600150,
    getStockFundFlow: async () => opts.fundflow ?? REAL_FUNDFLOW_600150,
  } as any;
}

describe('factor_calculate 资金因子静默全 0 护栏（契约，真实 payload）', () => {
  it('资金因子全 0 且与 provider 矛盾 → 剔除该组 + degraded + 附真实资金面快照', async () => {
    const tool: any = new FactorCalculateTool(stubQv2());
    const r: any = await tool.execute({ symbol: '600150' }, ctx);

    // 1) 假 0 不得留在 factors 里冒充有效值
    expect(r.factors.super_large_net).toBeUndefined();
    expect(r.factors.large_net).toBeUndefined();
    expect(r.factors.main_net_inflow).toBeUndefined();
    expect(r.factors.fund_inflow_5d_sum).toBeUndefined();
    // 2) 非资金因子不受影响
    expect(r.factors.rsi14).toBeCloseTo(79.66, 1);
    expect(r.factors.ma20).toBeCloseTo(35.17, 1);
    // 3) 显式降级 + 说明
    expect(r.degraded).toBe(true);
    expect(r.unavailable_factors.length).toBe(4);
    expect(String(r.freshness_warnings?.[0])).toContain('静默失效');
    // 4) 附 provider 真实资金面（可溯源）
    expect(r.fund_flow_provider.main_net_inflow_wan).toBe(68372.88);
    expect(r.fund_flow_provider.date).toBe('2026-09-09');
    expect(r.fund_flow_provider.contradicts_factor_table).toBe(true);
  });

  it('provider 亦为空/0 → 仍剔除并提示「不得解读为零资金流」', async () => {
    const tool: any = new FactorCalculateTool(stubQv2({ fundflow: { success: true, data: { data: [] } } }));
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.factors.super_large_net).toBeUndefined();
    expect(r.degraded).toBe(true);
    expect(String(r.freshness_warnings?.[0])).toContain('无法确认');
    expect(r.fund_flow_provider).toBeUndefined();
  });

  it('资金因子有真实值 → 保持原样，不误伤', async () => {
    const factors = JSON.parse(JSON.stringify(REAL_FACTORS_600150));
    factors.factors[0].factor_value = -1.23e8;
    const tool: any = new FactorCalculateTool(stubQv2({ factors }));
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.factors.super_large_net).toBe(-1.23e8);
    expect(r.degraded).toBe(false);
    expect(r.unavailable_factors).toBeUndefined();
  });

  it('provider 抛异常时不得放行 0 值（fail-closed）', async () => {
    const stub: any = {
      calculateFactors: async () => REAL_FACTORS_600150,
      getStockFundFlow: async () => { throw new Error('provider down'); },
    };
    const tool: any = new FactorCalculateTool(stub);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.factors.super_large_net).toBeUndefined();
    expect(r.degraded).toBe(true);
  });
});

describe.skipIf(!LIVE)('REQ-cf627b 新工具与护栏（真实后端）', () => {
  const client: any = new QuantsysV2Client({
    baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
    timeout: 30000,
  } as any);

  it('index_constituents(000300)：返回真实成分清单', async () => {
    const tool: any = new IndexConstituentsTool(client);
    const r: any = await tool.execute({ symbol: '000300' }, ctx);
    console.log('[index_constituents]', JSON.stringify({ symbol: r.symbol, count: r.count, head: r.constituents.slice(0, 5) }));
    expect(r.count).toBeGreaterThan(100);
    expect(r.constituents.every((c: string) => /^\d{6}$/.test(c))).toBe(true);
  }, 60000);

  it('index_constituents：数据源失败必须显式失败，不得静默空清单', async () => {
    const bad: any = { getIndexConstituents: async () => ({ success: false, error: 'provider down' }) };
    const tool: any = new IndexConstituentsTool(bad);
    await expect(tool.execute({ symbol: '000300' }, ctx)).rejects.toThrow(/失败/);
  });

  it('memory_recall_audit(stats)：返回真实召回统计与口径解读', async () => {
    const tool: any = new RecallAuditTool(client);
    const r: any = await tool.execute({ action: 'stats' }, ctx);
    console.log('[recall_audit]', JSON.stringify({ total: r.total, injected: r.injected, suppressed: r.suppressed, rate: r.injection_rate, interp: r.interpretation?.slice(0, 80) }));
    expect(r.total).toBeGreaterThan(0);
    expect(typeof r.injection_rate).toBe('number');
    expect(r.interpretation).toBeTruthy();
  }, 60000);

  it('data_quality_report：新增资金因子探针必须出现在体检结果中', async () => {
    const { DataQualityReportTool } = await import('../packages/data-manager/src/tools/DataQualityReportTool/DataQualityReportTool.js');
    const tool: any = new DataQualityReportTool(client);
    const r: any = await tool.call({ data_type: 'all', days: 7 } as any);
    const anomalies: any[] = r?.data?.anomalies ?? [];
    const hit = anomalies.find((a: any) => String(a?.probe ?? '').startsWith('factor.fund_group'));
    console.log('[dq probe]', JSON.stringify(hit ?? { missing: true }), '| summary:', r?.data?.summary);
    expect(hit).toBeTruthy();
    expect(['ok', 'degraded', 'fail']).toContain(hit.status);
  }, 90000);

  it('factor_calculate：真实后端下资金因子若全 0 必须 degraded（否则须有真实值）', async () => {
    const tool: any = new FactorCalculateTool(client);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    const fundKeys = ['super_large_net', 'large_net', 'main_net_inflow', 'fund_inflow_5d_sum'];
    const present = fundKeys.filter((k) => k in (r.factors ?? {}));
    const zeros = present.filter((k) => Number(r.factors[k]) === 0);
    console.log('[factor guard live]', JSON.stringify({ present, zeros, degraded: r.degraded, unavailable: r.unavailable_factors?.length }));
    if (present.length > 0 && zeros.length === present.length) {
      throw new Error('资金因子全 0 却未触发护栏：' + JSON.stringify(present));
    }
    expect(present.length === 0 || zeros.length < present.length).toBe(true);
  }, 60000);
});
