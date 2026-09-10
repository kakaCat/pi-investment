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
    const rows: any[] = await tool.execute({ symbol: '000300', start_date: '2026-08-01', end_date: '2026-09-10' }, ctx);
    console.log('[kline-index] rows=' + rows.length + ' first=' + JSON.stringify(rows[0] ?? null));
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
});
