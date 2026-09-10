/**
 * 数据真实性护栏契约测试（REQ-342799）
 *
 * 目的：锁死『后端返回失败/字段缺失 → 工具静默返回 0/空』这一类故障。
 * 与既有单测的区别：这里用的是 2026-09-11 从线上后端 curl 到的**真实响应**，
 * 而不是手写的理想 payload（后者曾让 bug 通过测试）。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChipAnalysisTool } from '../packages/market/src/tools/ChipAnalysisTool/ChipAnalysisTool.js';
import { BarraDecompositionTool } from '../packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool.js';
import { DataFetchKlineTool } from '../packages/investment/src/tools/DataFetchKlineTool/DataFetchKlineTool.js';
import { WatchListTool } from '../packages/intelligence/src/tools/WatchListTool/WatchListTool.js';

const ctx = {} as any;

// —— 真实样本 1：GET /api/analysis/chip-distribution/600150（2026-09-11 01:2x 实测）——
const REAL_CHIP_600150 = {
  success: true,
  data: {
    symbol: '600150',
    asOf: '2026-09-10',
    close: 40.82,
    curve: [
      { price: 39.3724, weight: 0.012667092448551362 },
      { price: 40.5145, weight: 0.13091054390331214 },
      { price: 40.8952, weight: 0.056422363648137075 },
    ],
    metrics: {
      profitRatio: 0.9061409969644746,
      avgCost: 40.31754899672987,
      cost90Low: 39.62615,
      cost90High: 40.89515,
      cost70Low: 39.87995000000001,
      cost70High: 40.76825000000001,
      peakPrice: 40.514450000000004,
      concentration: 0.02202900994690522,
    },
  },
};

// —— 真实样本 2：POST /api/risk/metrics（后端计算成功，但未计算 beta/alpha）——
const REAL_RISK_METRICS = {
  success: true,
  data: {
    sharpeRatio: -11.34670985581161,
    sortinoRatio: -10.564379554145876,
    calmarRatio: 17.787134109452094,
    maxDrawdown: -0.06695652173913046,
    annualReturn: 1.190964631676358,
    annualVolatility: 0.3692252213466794,
    var95: -0.030623727071412202,
    cvar95: -0.03367049582189598,
    cumulativeReturn: 0.1396527981474336,
  },
};

describe('chip_analysis 数据真实性护栏', () => {
  it('解析后端 metrics（旧实现静默返回全 0）', async () => {
    const tool: any = new ChipAnalysisTool({ getChipDistribution: vi.fn().mockResolvedValue(REAL_CHIP_600150) } as any);
    const r = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.avg_cost).toBeCloseTo(40.3175, 3);
    expect(r.profit_ratio).toBeCloseTo(90.61, 1);
    expect(r.concentration).toBeCloseTo(2.2, 1);
    expect(r.as_of).toBe('2026-09-10');
    expect(r.support_levels.length).toBeGreaterThan(0);
    expect(r.resistance_levels.length).toBeGreaterThan(0);
    expect(r.curve_points).toBe(3);
  });

  it('缺 metrics 时显式失败，而不是返回 0', async () => {
    const tool: any = new ChipAnalysisTool({ getChipDistribution: vi.fn().mockResolvedValue({ success: true, data: { symbol: '600150' } }) } as any);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/缺少 metrics/);
  });
});

describe('risk_barra_decomposition 数据真实性护栏', () => {
  it('后端 success=false（样本不足）时抛错，不再输出 total_risk=0 假结论', async () => {
    const tool: any = new BarraDecompositionTool({
      getBarraDecomposition: vi.fn().mockResolvedValue({ success: false, data: null, message: 'Insufficient data for all symbols' }),
    } as any);
    await expect(tool.execute({ symbols: ['300677', '600887'] }, ctx)).rejects.toThrow(/Insufficient data|无有效结果/);
  });

  it('后端全空字段时同样抛错', async () => {
    const tool: any = new BarraDecompositionTool({
      getBarraDecomposition: vi.fn().mockResolvedValue({ data: { totalRisk: null, factorRisks: [] } }),
    } as any);
    await expect(tool.execute({}, ctx)).rejects.toThrow(/无有效结果/);
  });

  it('后端有真实数据时正常映射', async () => {
    const tool: any = new BarraDecompositionTool({
      getBarraDecomposition: vi.fn().mockResolvedValue({ data: { totalRisk: 15.5, factorRisks: [{ name: 'size', risk: 3.1 }], idiosyncraticRisk: 5.0 } }),
    } as any);
    const r = await tool.execute({}, ctx);
    expect(r.total_risk).toBe(15.5);
    expect(r.factor_risks.length).toBe(1);
  });
});

describe('data_fetch_kline 指数数据（amount=null）', () => {
  it('指数 null amount 不再让整条调用失败，且不伪造成 0', async () => {
    const tool: any = new DataFetchKlineTool({
      getKlines: vi.fn().mockResolvedValue([
        { symbol: '000300', trade_date: '2026-08-03', open: 4561.817, high: 4572.588, low: 4529.186, close: 4543.178, volume: 23204258400, amount: null },
      ]),
    } as any);
    const rows = await tool.execute({ symbol: '000300', start_date: '2026-08-01', end_date: '2026-09-10' }, ctx);
    expect(rows.length).toBe(1);
    expect(rows[0].date).toBe('2026-08-03');
    expect('amount' in rows[0]).toBe(false);
    expect(rows[0].close).toBeCloseTo(4543.178, 3);
  });
});

describe('watch_list 字段契约（conditions[] + context）', () => {
  it('归一化出 name/condition，不再全是 undefined', async () => {
    const tool: any = new WatchListTool({
      listWatchRules: vi.fn().mockResolvedValue({
        rules: [{ id: 135, symbol: '600150', enabled: true, conditions: [{ type: 'price_break', params: { price: 39.25, direction: 'below' } }], context: '600150 火灾事故破位预警' }],
      }),
    } as any);
    const rules = await tool.execute({}, ctx);
    expect(rules[0].name).toBe('规则#135');
    expect(rules[0].condition).toBe('price < 39.25');
    expect(rules[0].reason).toContain('火灾');
  });
});

describe('risk_metrics 诚实性', () => {
  it('后端未计算 beta/alpha 时给出解释字段，而不是让 0 冒充中性', async () => {
    const { RiskMetricsTool } = await import('../packages/risk/src/tools/RiskMetricsTool/RiskMetricsTool.js');
    // 客户端 unwrap() 会剥掉 {success,data} 外层 → tool 收到的是内层 data 对象
    const tool: any = new RiskMetricsTool({ getRiskMetrics: vi.fn().mockResolvedValue(REAL_RISK_METRICS.data) } as any);
    const r = await tool.execute({ days: 60 }, ctx);
    expect(r.volatility).toBeCloseTo(36.92, 1);
    expect(r.max_drawdown).toBeCloseTo(-6.7, 1);
    expect(r.beta_note).toMatch(/未计算|无基准/);
  });
});

/**
 * 框架口径的输出校验（与 dsh-tools 一致）：additionalProperties:false 时，
 * 未在 schema.properties 中声明的键会被静默丢弃——新增字段必须先声明，
 * 否则『修好了但线上看不到』（REQ-342799 实测踩过一次）。
 */
function undeclaredKeys(schema: any, value: any, path = 'value', errs: string[] = []): string[] {
  if (value === null || value === undefined || typeof value !== 'object') return errs;
  if (Array.isArray(value)) {
    value.forEach((v, i) => undeclaredKeys(schema?.items ?? {}, v, path + '[' + i + ']', errs));
    return errs;
  }
  const props = schema?.properties ?? {};
  for (const [k, v] of Object.entries(value)) {
    const sub: any = (props as any)[k];
    if (!sub) {
      if (schema?.additionalProperties !== true) errs.push(path + '.' + k + ' 未在 schema 声明（会被框架丢弃）');
      continue;
    }
    undeclaredKeys(sub, v, path + '.' + k, errs);
  }
  return errs;
}

describe('输出 schema 完整性护栏（additionalProperties:false 会静默丢字段）', () => {
  it('data_quality_report 的语义探针字段必须在 schema 中声明', async () => {
    const { dataQualityReportPrompt } = await import('../packages/data-manager/src/tools/DataQualityReportTool/prompt.js');
    const props: any = (dataQualityReportPrompt as any).output.schema.properties;
    expect(props.tool_health).toBeTruthy();
    expect(props.tool_health_summary).toBeTruthy();
    expect(props.scope_note).toBeTruthy();
  });

  it('工具真实输出不得含未声明字段（framework-strip 自查）', async () => {
    const { dataQualityReportPrompt } = await import('../packages/data-manager/src/tools/DataQualityReportTool/prompt.js');
    const schema: any = (dataQualityReportPrompt as any).output.schema;
    const sample = { data_type: 'all', check_date: '2026-09-10', overall_score: 92.5, missing_data: [], delayed_data: [], anomalies: [], summary: 'x', tool_health: [{ probe: 'p', status: 'ok', evidence: 'e' }], tool_health_summary: 's', scope_note: 'n' };
    expect(undeclaredKeys(schema, sample)).toEqual([]);
  });
});

describe('signal_track 写入护栏（决策账本防污染）', () => {
  const load = async () => {
    const { SignalTrackTool } = await import('../packages/intelligence/src/tools/SignalTrackTool/SignalTrackTool.js');
    return SignalTrackTool;
  };

  it('非交易日 → 拒绝写入（历史 3 条记录落在周末）', async () => {
    const T = await load();
    // 真实 client 对无数据会抛错（后端返回 {error:'No kline data'}），而非返回空数组
    const tool: any = new T({ getKlines: vi.fn().mockRejectedValue(new Error('No kline data for 600519')), recordSignal: vi.fn() } as any);
    await expect(
      tool.execute({ action: 'record', symbol: '600519', price: 1292.3, source: 'watch_rule', grade: 'C', signal_date: '2026-08-30' }, ctx),
    ).rejects.toThrow(/校验取数失败|无法与行情对账|不存在的K线|非交易日|日期不匹配/);
  });

  it('价格与真实收盘偏离 >15% → 拒绝写入（历史 A 级假数据形态：1800 vs 真实 1292）', async () => {
    const T = await load();
    const tool: any = new T({ getKlines: vi.fn().mockResolvedValue([{ close: 1292.3 }]), recordSignal: vi.fn() } as any);
    await expect(
      tool.execute({ action: 'record', symbol: '600519', price: 1850.5, source: 'mainline_stocks', grade: 'A', signal_date: '2026-08-27' }, ctx),
    ).rejects.toThrow(/偏离/);
  });

  it('后端回退返回邻近交易日K线（日期不匹配）→ 拒绝写入', async () => {
    const T = await load();
    const tool: any = new T({ getKlines: vi.fn().mockResolvedValue([{ trade_date: '2026-09-04', close: 1330 }]), recordSignal: vi.fn() } as any);
    await expect(
      tool.execute({ action: 'record', symbol: '600519', price: 1330, source: 'watch_rule', grade: 'C', signal_date: '2026-09-06' }, ctx),
    ).rejects.toThrow(/日期不匹配/);
  });

  it('价格合理 → 正常写入并附带校验结果', async () => {
    const T = await load();
    const recordSignal = vi.fn().mockResolvedValue({ signalId: 99 });
    const tool: any = new T({ getKlines: vi.fn().mockResolvedValue([{ close: 1292.3 }]), recordSignal } as any);
    const r: any = await tool.execute({ action: 'record', symbol: '600519', price: 1295, source: 'opportunity_scan', grade: 'B', signal_date: '2026-08-27' }, ctx);
    expect(recordSignal).toHaveBeenCalledOnce();
    expect(String(r.details.price_check)).toMatch(/verified/);
  });
});
describe('pool_list 字段契约（后端为 symbol_count）', () => {
  it('把 symbol_count 映射为 member_count（旧实现恒 undefined）', async () => {
    const { PoolListTool } = await import('../packages/investment/src/tools/PoolListTool/PoolListTool.js');
    const tool: any = new PoolListTool({ listPools: vi.fn().mockResolvedValue([{ id: 41, name: '机器人供应链观察池', symbol_count: 7 }]) } as any);
    const pools: any[] = await tool.execute({}, ctx);
    expect(pools[0].member_count).toBe(7);
  });
});

describe('data_fetch_dividend 数据真实性护栏', () => {
  it('后端返回 success=true 但全 0 / 全 null 时必须显式失败（不得当成"不分红"）', async () => {
    const { DataFetchDividendTool } = await import('../packages/investment/src/tools/DataFetchDividendTool/DataFetchDividendTool.js');
    const zeros = [
      { symbol: '600176', dividend_per_share: 0.0, dividend_yield: null, ex_dividend_date: null },
      { symbol: '600176', dividend_per_share: 0.0, dividend_yield: null, ex_dividend_date: null },
    ];
    const tool: any = new DataFetchDividendTool({ getDividends: vi.fn().mockResolvedValue(zeros) } as any);
    await expect(tool.execute({ mode: 'history', symbol: '600176' }, ctx)).rejects.toThrow(/无有效分红数据/);
  });

  it('有真实分红数据时正常返回', async () => {
    const { DataFetchDividendTool } = await import('../packages/investment/src/tools/DataFetchDividendTool/DataFetchDividendTool.js');
    const rows = [{ symbol: '601398', dividend_per_share: 0.3, ex_dividend_date: '2026-07-10' }];
    const tool: any = new DataFetchDividendTool({ getDividends: vi.fn().mockResolvedValue(rows) } as any);
    const r: any = await tool.execute({ mode: 'history', symbol: '601398' }, ctx);
    expect(r.data.length).toBe(1);
    expect(r.raw_rows).toBe(1);
  });
});

describe('fund_flow 新鲜度标注', () => {
  it('个股模式补 data_date / staleness_days / freshness_note', async () => {
    const { FundFlowTool } = await import('../packages/competition/src/tools/FundFlowTool/FundFlowTool.js');
    const tool: any = new FundFlowTool({
      getStockFundFlow: vi.fn().mockResolvedValue({ success: true, data: [{ date: '2020-01-02', mainNetInflow: 100 }] }),
      getStockMargin: vi.fn().mockResolvedValue({ success: true, data: [] }),
    } as any);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.data_date).toBe('2020-01-02');
    expect(r.staleness_days).toBeGreaterThan(1);
    expect(r.freshness_note).toMatch(/非当日数据/);
  });
});

describe('sector_analysis 窗口诚实性', () => {
  it('标注后端忽略 days（单一窗口），避免被当 N 日区间涨幅', async () => {
    const { SectorAnalysisTool } = await import('../packages/market/src/tools/SectorAnalysisTool/SectorAnalysisTool.js');
    const tool: any = new SectorAnalysisTool({ getSectorAnalysis: vi.fn().mockResolvedValue({ data_type: 'sector_list', data: { industries: [] } }) } as any);
    const r: any = await tool.execute({ days: 20 }, ctx);
    expect(r.days_requested).toBe(20);
    expect(r.window_note).toMatch(/忽略 days/);
  });
});
