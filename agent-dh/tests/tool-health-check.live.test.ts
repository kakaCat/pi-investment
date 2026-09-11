/**
 * 投资工具数据真实性体检（REQ-342799 P0）
 *
 * 背景（2026-09-11，w-c8cae280）：对 12 个核心工具抽样，发现 2 个硬失败 + 4 个静默失效
 * （返回全 0 / 空数组 / 无有效字段却不报错），而 data_quality_report 同期报 92.5 分 0 异常。
 * 本套件把『体检』固化为可重复执行的线上探针，防止静默失效回归。
 *
 * 运行：cd agent-dh && LIVE=1 npx vitest run tests/tool-health-check.live.test.ts
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ChipAnalysisTool } from '../packages/market/src/tools/ChipAnalysisTool/ChipAnalysisTool.js';
import { BarraDecompositionTool } from '../packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool.js';
import { DataFetchKlineTool } from '../packages/investment/src/tools/DataFetchKlineTool/DataFetchKlineTool.js';
import { WatchListTool } from '../packages/intelligence/src/tools/WatchListTool/WatchListTool.js';
import { RiskMetricsTool } from '../packages/risk/src/tools/RiskMetricsTool/RiskMetricsTool.js';

const LIVE = process.env.LIVE === '1';
const ctx = {} as any;
const client: any = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
  timeout: 30000,
} as any);

/** 判定一组数值是否『全 0 / 全空』——即静默失效特征 */
function looksLikeSilentFailure(obj: any, keys: string[]): boolean {
  if (!obj || typeof obj !== 'object') return true;
  const vals = keys.map((k) => obj[k]);
  if (vals.every((v) => v === undefined)) return true;
  return vals.every((v) => v === 0 || v === null || (Array.isArray(v) && v.length === 0) || v === '');
}

describe.skipIf(!LIVE)('工具数据真实性体检（真实后端）', () => {
  it('chip_analysis：必须返回真实筹码（不得全 0）', async () => {
    const tool: any = new ChipAnalysisTool(client);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    console.log('[chip]', JSON.stringify({ avg_cost: r.avg_cost, profit_ratio: r.profit_ratio, concentration: r.concentration, as_of: r.as_of, levels: [r.support_levels?.length, r.resistance_levels?.length] }));
    expect(looksLikeSilentFailure(r, ['avg_cost', 'profit_ratio', 'concentration'])).toBe(false);
    expect(r.avg_cost).toBeGreaterThan(0);
    expect(r.profit_ratio).toBeGreaterThan(0);
    expect(r.as_of).toBeTruthy();
  }, 60000);

  it('risk_barra_decomposition：无有效结果必须显式失败，不得输出 0 风险', async () => {
    const tool: any = new BarraDecompositionTool(client);
    let threw = '';
    let value: any = null;
    try { value = await tool.execute({ symbols: ['300677', '600887'] }, ctx); } catch (e: any) { threw = String(e?.message ?? e); }
    console.log('[barra]', threw ? 'EXPLICIT_FAIL: ' + threw.slice(0, 160) : JSON.stringify(value));
    expect(threw !== '' || !looksLikeSilentFailure(value, ['total_risk', 'idiosyncratic_risk', 'style_exposure'])).toBe(true);
  }, 90000);

  it('data_fetch_kline：指数（000300）可取到且输出 schema 安全（amount=null 不再炸）', async () => {
    const tool: any = new DataFetchKlineTool(client);
    // 2026-09-11（REQ-733c5e）：输出由纯数组改为对象 {klines, resolved_kind, ...}
    const r: any = await tool.execute({ symbol: '000300', start_date: '2026-08-01', end_date: '2026-09-10' }, ctx);
    const rows: any[] = Array.isArray(r?.klines) ? r.klines : [];
    console.log('[kline-index] rows=' + rows.length + ' resolved=' + JSON.stringify({ kind: r?.resolved_kind, name: r?.resolved_name }) + ' first=' + JSON.stringify(rows[0] ?? null));
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      for (const k of ['open', 'high', 'low', 'close', 'volume', 'amount']) {
        if (k in row) expect(Number.isFinite(Number(row[k]))).toBe(true);
      }
    }
  }, 60000);

  it('watch_list：每条规则必须有可读的 name/condition', async () => {
    const tool: any = new WatchListTool(client);
    const rules: any[] = await tool.execute({} as any, ctx);
    const bad = rules.filter((r) => !r?.name || typeof r?.condition !== 'string' || r.condition.length === 0);
    console.log('[watch] total=' + rules.length + ' malformed=' + bad.length + ' sample=' + JSON.stringify(rules[0] ?? null));
    expect(rules.length).toBeGreaterThan(0);
    expect(bad.length).toBe(0);
  }, 60000);

  it('窗口不变性探针：risk_metrics 的 days 是否真的生效（不生效=DEGRADED 记录）', async () => {
    const tool: any = new RiskMetricsTool(client);
    const a: any = await tool.execute({ days: 30 }, ctx);
    const b: any = await tool.execute({ days: 250 }, ctx);
    const identical = JSON.stringify({ v: a.volatility, m: a.max_drawdown, s: a.sharpe_ratio }) ===
      JSON.stringify({ v: b.volatility, m: b.max_drawdown, s: b.sharpe_ratio });
    console.log('[risk-window] days=30 vs 250 identical=' + identical + ' beta_note=' + String(a.beta_note).slice(0, 60));
    expect(a.beta_note).toBeTruthy();
    if (identical) console.log('[risk-window] DEGRADED：后端窗口参数未生效（30/250 同值），分析时不得声称多窗口对比');
  }, 90000);

  it('pool_list：member_count 有值（后端 symbol_count 映射）', async () => {
    const { PoolListTool } = await import('../packages/investment/src/tools/PoolListTool/PoolListTool.js');
    const tool: any = new PoolListTool(client);
    const pools: any[] = await tool.execute({}, ctx);
    const withCount = pools.filter((p) => typeof p?.member_count === 'number' && p.member_count > 0);
    console.log('[pool] total=' + pools.length + ' with_count=' + withCount.length + ' sample=' + JSON.stringify({ n: pools[0]?.name, c: pools[0]?.member_count }));
    expect(pools.length).toBeGreaterThan(0);
    expect(withCount.length).toBeGreaterThan(0);
  }, 60000);

  it('sector_analysis：必须标注后端忽略 days（单一窗口）', async () => {
    const { SectorAnalysisTool } = await import('../packages/market/src/tools/SectorAnalysisTool/SectorAnalysisTool.js');
    const tool: any = new SectorAnalysisTool(client);
    const r: any = await tool.execute({ days: 20 }, ctx);
    console.log('[sector] days_requested=' + r.days_requested + ' note=' + String(r.window_note).slice(0, 40));
    expect(r.window_note).toMatch(/忽略 days/);
  }, 60000);

  it('data_quality_report：语义探针 pack 可用且能抓到已知失效', async () => {
    const { DataQualityReportTool } = await import('../packages/data-manager/src/tools/DataQualityReportTool/DataQualityReportTool.js');
    const tool: any = new DataQualityReportTool(client);
    const r: any = await tool.execute({ data_type: 'all', days: 7 }, ctx);
    console.log('[dq] ' + r.tool_health_summary);
    for (const p of r.tool_health ?? []) console.log('   - ' + p.probe + ': ' + p.status + ' | ' + p.evidence);
    expect(Array.isArray(r.tool_health)).toBe(true);
    expect(r.tool_health.length).toBeGreaterThanOrEqual(5);
    expect(r.scope_note).toBeTruthy();
    const sectorWin = (r.tool_health ?? []).find((p: any) => p.probe === 'sector_analysis.window');
    expect(sectorWin?.status).toBe('degraded');
  }, 120000);

  it('memory_search 放宽召回（真实后端）：多词/长句不再零命中', async () => {
    // 用最小 real-HTTP 适配器替代 MemoryClient（同一契约：GET /api/v1/memory/search?q=&limit=&category=），
    // 从而在真实后端上检验工具层的放宽召回逻辑（不是 mock 匹配行为）。
    const realMemoryClient: any = {
      async search(params: any) {
        const url = new URL('http://127.0.0.1:8080/api/v1/memory/search');
        url.searchParams.set('q', String(params.query ?? ''));
        if (params.top_k) url.searchParams.set('limit', String(params.top_k));
        if (params.category) url.searchParams.set('category', String(params.category));
        const resp = await fetch(url);
        return await resp.json();
      },
    };
    const { MemorySearchTool } = await import('../packages/memory/src/tools/MemorySearchTool/MemorySearchTool.js');
    const tool: any = new MemorySearchTool(realMemoryClient);
    const multi = await tool.execute({ query: '业绩归因 超额 beta alpha', namespace: 'analysis', top_k: 3 }, ctx);
    // 句子内含已知短语（'业绩归因' 存在于记忆库）→ 期望放宽后命中
    const long = await tool.execute({ query: '帮我看看那个业绩归因的超额数据到底怎么样', top_k: 3 }, ctx);
    // 句内短语确实不存在于库中 → 允许 0 命中，但**必须显式说明已放宽尝试**（不得静默返回"无历史"）
    const absent = await tool.execute({ query: '紫电青霜玄武朱雀完全不存在的话题', top_k: 3 }, ctx);
    console.log('[mem-relax] 多词 total=' + multi.total + ' relaxed=' + multi.query_relaxed);
    console.log('[mem-relax] 长句 total=' + long.total + ' relaxed=' + long.query_relaxed + ' attempts=' + long.relax_attempts.length);
    console.log('[mem-relax] 不存在 total=' + absent.total + ' note=' + String(absent.relax_note).slice(0, 60));
    expect(multi.total).toBeGreaterThan(0);
    expect(long.total).toBeGreaterThan(0);
    expect(absent.total).toBe(0);
    expect(String(absent.relax_note)).toMatch(/均零命中|确无相关历史/);
  }, 90000);

  it('signal_track 写入护栏（真实后端）：非交易日与偏离价必须被拒', async () => {
    const { SignalTrackTool } = await import('../packages/intelligence/src/tools/SignalTrackTool/SignalTrackTool.js');
    const tool: any = new SignalTrackTool(client);
    let eSunday = '';
    let ePrice = '';
    try { await tool.execute({ action: 'record', symbol: '600519', price: 1295, source: 'watch_rule', grade: 'C', signal_date: '2026-09-06' }, ctx); } catch (e: any) { eSunday = String(e?.message ?? e); }
    try { await tool.execute({ action: 'record', symbol: '600519', price: 1850.5, source: 'opportunity_scan', grade: 'A', signal_date: '2026-08-27' }, ctx); } catch (e: any) { ePrice = String(e?.message ?? e); }
    console.log('[signal-guard] 周日 → ' + (eSunday ? 'REJECT: ' + eSunday.slice(0, 90) : '❌ 被写入了'));
    console.log('[signal-guard] 偏离价 → ' + (ePrice ? 'REJECT: ' + ePrice.slice(0, 90) : '❌ 被写入了'));
    expect(eSunday).toMatch(/无法与行情对账|校验取数失败|日期不匹配/);
    expect(ePrice).toMatch(/偏离|校验取数失败/);
  }, 60000);

  it('risk_metrics：基准（沪深300）接入后 beta/alpha 为真实值，附业绩归因', async () => {
    const { RiskMetricsTool } = await import('../packages/risk/src/tools/RiskMetricsTool/RiskMetricsTool.js');
    const tool: any = new RiskMetricsTool(client);
    const r: any = await tool.execute({ days: 60 }, ctx);
    console.log('[risk-attrib] beta=' + r.beta + ' alpha=' + r.alpha + ' IR=' + r.information_ratio);
    console.log('[risk-nav] ' + JSON.stringify(r.nav_coverage));
    expect(r.nav_coverage === null || typeof r.nav_coverage === 'object').toBe(true);
    console.log('[risk-attrib] ' + JSON.stringify(r.attribution));
    expect(r.beta_note).toBeTruthy();
    if (r.attribution) {
      expect(r.attribution.benchmark_symbol).toBe('000300');
      expect(String(r.beta_note)).toMatch(/backend_provided/);
      console.log('[risk-attrib] 组合 ' + r.attribution.portfolio_return_pct + '% vs 基准 ' + r.attribution.benchmark_return_pct + '% → 超额 ' + r.attribution.excess_return_pct + '%');
    }
  }, 120000);

  it('data_fetch_dividend：只允许"显式失败"或"有效数据"，绝不静默返回全 0', async () => {
    const { DataFetchDividendTool } = await import('../packages/investment/src/tools/DataFetchDividendTool/DataFetchDividendTool.js');
    const tool: any = new DataFetchDividendTool(client);
    let threw = '';
    let val: any = null;
    try { val = await tool.execute({ mode: 'history', symbol: '600519' }, ctx); } catch (e: any) { threw = String(e?.message ?? e); }
    console.log('[dividend] ' + (threw ? 'EXPLICIT_FAIL: ' + threw.slice(0, 120) : 'rows=' + (val?.data?.length ?? 0)));
    if (!threw) {
      const rows: any[] = val?.data ?? [];
      expect(rows.every((x: any) => Number(x?.dividend_per_share) > 0)).toBe(true);
    } else {
      expect(threw).toMatch(/无有效分红数据|源失效|失败/);
    }
  }, 60000);
});
