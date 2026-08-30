/**
 * verify-smoke-20260830-r5.ts
 * 新鲜进程冒烟复测（Round 5）—— 覆盖 TOOLS_SMOKE_REPORT_20260830 失败清单
 * 验证链：tool.call() → toDSHToolDefinition().execute() → snapshotJsonValue(lossless)
 *        → validateJsonSchemaValue(schema) → output.render()
 * 独立进程，Promise.race 仅用于本进程内跳过卡死工具，不影响 DSH 执行器队列。
 */
import { QuantsysV2Client } from '../../quantsys-v2-client/dist/index.mjs';
import { AgentOSClient } from '../../agent-os-client/dist/index.mjs';
import * as dshSession from '@deepseek-ai/dsh-session';
import * as dshTools from '@deepseek-ai/dsh-tools';

import { StrategyListTool } from '../packages/investment/src/tools/StrategyListTool/StrategyListTool';
import { OpportunityScanTool } from '../packages/strategy/src/tools/OpportunityScanTool/OpportunityScanTool';
import { RiskControllerTool } from '../packages/risk/src/tools/RiskControllerTool/RiskControllerTool';
import { LearningAnalyzeTool } from '../packages/learning/src/tools/LearningAnalyzeTool/LearningAnalyzeTool';
import { QuantsysV2LogsTool } from '../packages/quantsys-v2-manager/src/tools/QuantsysV2LogsTool/QuantsysV2LogsTool';
import { AgentOsStatusTool } from '../packages/agent-os-manager/src/tools/AgentOsStatusTool/AgentOsStatusTool';
import { MemorySearchTool } from '../packages/memory/src/tools/MemorySearchTool/MemorySearchTool';
import { SlippageReportTool } from '../packages/trading/src/tools/SlippageReportTool/SlippageReportTool';
import { WatchListTool } from '../packages/intelligence/src/tools/WatchListTool/WatchListTool';
import { DataQualityReportTool } from '../packages/data-manager/src/tools/DataQualityReportTool/DataQualityReportTool';
import { RotationProposalTool } from '../packages/strategy/src/tools/RotationProposalTool/RotationProposalTool';
import { FactorAnalyzeTool } from '../packages/factor/src/tools/FactorAnalyzeTool/FactorAnalyzeTool';
import { BarraDecompositionTool } from '../packages/risk/src/tools/BarraDecompositionTool/BarraDecompositionTool';
import { DataManagerTool } from '../packages/data-manager/src/tools/DataManagerTool/DataManagerTool';
import { DataFetchFinancialTool } from '../packages/investment/src/tools/DataFetchFinancialTool/DataFetchFinancialTool';
import { FactorCalculateTool } from '../packages/factor/src/tools/FactorCalculateTool/FactorCalculateTool';
import { AgentOsLogsTool } from '../packages/agent-os-manager/src/tools/AgentOsLogsTool/AgentOsLogsTool';
import { LearningApplyTool } from '../packages/learning/src/tools/LearningApplyTool/LearningApplyTool';
import { DataFetchMacroTool } from '../packages/investment/src/tools/DataFetchMacroTool/DataFetchMacroTool';
import { DataFetchMarketSentimentTool } from '../packages/investment/src/tools/DataFetchMarketSentimentTool/DataFetchMarketSentimentTool';
import { DataFetchNorthFlowTool } from '../packages/investment/src/tools/DataFetchNorthFlowTool/DataFetchNorthFlowTool';
import { RotationSimulateTool } from '../packages/strategy/src/tools/RotationSimulateTool/RotationSimulateTool';
import { EvolutionRunTool } from '../packages/evolution/src/tools/EvolutionRunTool/EvolutionRunTool';

const snapshotJsonValue: any = (dshSession as any).snapshotJsonValue ?? (dshSession as any).default?.snapshotJsonValue;
const validateJsonSchemaValue: any = (dshTools as any).validateJsonSchemaValue;
if (!snapshotJsonValue || !validateJsonSchemaValue) {
  console.error('FATAL: dsh-session/dsh-tools 导出缺失');
  process.exit(2);
}

// ---------- 依赖 ----------
const qv2: any = new QuantsysV2Client({ baseURL: 'http://localhost:5001' });
const aos: any = new AgentOSClient({ baseURL: 'http://localhost:8080', agentId: 'agent-dh' });

const AGENT_OS_CONFIG = {
  projectRoot: '/Users/yunpeng/pi-investment/agent-os',
  port: 8080,
  healthCheckUrl: 'http://localhost:8080/health',
  startCommand: './bin/agent-os serve',
  logDir: 'logs',
  launchdLabel: 'com.pi-investment.agent-os',
};
const QV2_LOG_CONFIG = {
  projectRoot: '/Users/yunpeng/pi-investment/quantsys-v2',
  logFile: 'logs/launchd-stdout.log',
};

class HarnessMemoryStore {
  constructor(private baseURL: string) {}
  async searchMemory(params: any): Promise<any> {
    const q = params.q ?? '';
    const url = this.baseURL + '/api/v1/memory/search?q=' + encodeURIComponent(q || ' ') + '&limit=' + Math.min(params.limit ?? 20, 150);
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('memory search HTTP ' + resp.status);
    const res: any = await resp.json();
    const raw: any[] = res?.memories ?? res?.items ?? [];
    const items: any[] = [];
    for (const it of raw) {
      let env: any = null;
      try { env = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
      if (!env || typeof env !== 'object') continue;
      if (params.kind && env.kind !== params.kind) continue;
      if (env.status === 'deprecated') continue;
      items.push({ id: it.id, scope: env.scope, payload: env.payload, content: env.body ?? '', created_at: it.created_at });
    }
    return { items, total: items.length };
  }
}
const memStore = new HarnessMemoryStore('http://localhost:8080');

// learning stub（聚焦 wrap 层回归：suggestions 字符串化 / sanitizeLossless）
const analyzeExperiences = async (scope: string, focus: string, minSamples: number) => ({
  patterns: [{ name: 'test-pattern' }],
  suggestions: ['建议一', 123, null, { x: 1 }],
  sample_count: 42,
});
const applyRule = async (ruleId: string, context: any, dryRun: boolean) => ({
  applied: true,
  action_taken: undefined,
  impact: { changed: undefined, count: 1 },
  message: 'ok',
});
// ---------- 用例 ----------
interface Case { name: string; tool: any; args: any; budgetMs: number }
const cases: Case[] = [
  { name: 'strategy_list',            tool: new StrategyListTool(qv2),                 args: {}, budgetMs: 15000 },
  { name: 'opportunity_scan',         tool: new OpportunityScanTool(qv2),              args: {}, budgetMs: 60000 },
  { name: 'risk_controller',          tool: new RiskControllerTool(qv2),               args: { command: 'position_size', symbol: '600519', price: 1292.3 }, budgetMs: 10000 },
  { name: 'learning_analyze',         tool: new LearningAnalyzeTool(analyzeExperiences as any), args: { focus: 'patterns' }, budgetMs: 10000 },
  { name: 'quantsys_v2_logs',         tool: new QuantsysV2LogsTool(QV2_LOG_CONFIG),    args: {}, budgetMs: 10000 },
  { name: 'agent_os_status',          tool: new AgentOsStatusTool(AGENT_OS_CONFIG),    args: {}, budgetMs: 15000 },
  { name: 'memory_search',            tool: new MemorySearchTool(aos.memory),          args: { query: '贵州茅台' }, budgetMs: 15000 },
  { name: 'slippage_report',          tool: new SlippageReportTool(memStore as any),   args: {}, budgetMs: 15000 },
  { name: 'watch_list',               tool: new WatchListTool(qv2),                    args: {}, budgetMs: 15000 },
  { name: 'data_quality_report',      tool: new DataQualityReportTool(qv2),            args: {}, budgetMs: 40000 },
  { name: 'rotation_proposal',        tool: new RotationProposalTool(qv2),             args: {}, budgetMs: 30000 },
  { name: 'factor_analyze',           tool: new FactorAnalyzeTool(qv2),                args: { factor_name: 'rsi' }, budgetMs: 30000 },
  { name: 'risk_barra_decomposition', tool: new BarraDecompositionTool(qv2),           args: { symbols: ['600519', '000858'] }, budgetMs: 30000 },
  { name: 'data_manager_status',      tool: new DataManagerTool(qv2),                  args: { operation: 'status' }, budgetMs: 15000 },
  { name: 'data_fetch_financial',     tool: new DataFetchFinancialTool(qv2),           args: { symbol: '600519' }, budgetMs: 20000 },
  { name: 'factor_calculate',         tool: new FactorCalculateTool(qv2),              args: { symbol: '600519' }, budgetMs: 20000 },
  { name: 'agent_os_logs',            tool: new AgentOsLogsTool(AGENT_OS_CONFIG),      args: {}, budgetMs: 15000 },
  { name: 'learning_apply',           tool: new LearningApplyTool(applyRule as any),   args: { rule_id: 'R-001', context: {}, dry_run: true }, budgetMs: 10000 },
  { name: 'data_fetch_macro',         tool: new DataFetchMacroTool(qv2),               args: { indicator: 'pmi' }, budgetMs: 70000 },
  { name: 'data_fetch_market_sentiment', tool: new DataFetchMarketSentimentTool(qv2),  args: {}, budgetMs: 45000 },
  { name: 'data_fetch_north_flow',    tool: new DataFetchNorthFlowTool(qv2),           args: {}, budgetMs: 90000 },
  { name: 'rotation_simulate',        tool: new RotationSimulateTool(qv2),             args: { proposals: [{ action: 'buy', symbol: '000001', weight: 0.1 }] }, budgetMs: 20000 },
  { name: 'evolution_run_propose',    tool: new EvolutionRunTool(aos),                 args: { mode: 'propose', strategy_id: 178 }, budgetMs: 70000 },
];

async function runCase(c: Case) {
  const started = Date.now();
  try {
    const res: any = await c.tool.call(c.args);
    if (!res?.success) {
      return { name: c.name, ok: false, phase: 'call', ms: Date.now() - started, detail: JSON.stringify(res?.error ?? res).slice(0, 280) };
    }
    const def: any = c.tool.toDSHToolDefinition();
    let data: any;
    try {
      data = await def.execute(c.args);
    } catch (e: any) {
      return { name: c.name, ok: false, phase: 'def.execute', ms: Date.now() - started, detail: String(e?.message ?? e).slice(0, 280) };
    }
    const snapped = snapshotJsonValue(data);
    if (snapped === undefined) {
      return { name: c.name, ok: false, phase: 'lossless', ms: Date.now() - started, detail: 'snapshotJsonValue 返回 undefined（含 undefined/-0/稀疏数组/NaN）' };
    }
    const schema: any = c.tool.getPrompt?.().output?.schema;
    let schemaErrors: string[] = [];
    if (schema) {
      try { schemaErrors = validateJsonSchemaValue(schema, data); } catch (e: any) { schemaErrors = ['schema 校验抛异常: ' + (e?.message ?? e)]; }
    }
    if (schemaErrors.length > 0) {
      return { name: c.name, ok: false, phase: 'schema', ms: Date.now() - started, detail: schemaErrors.slice(0, 5).join(' | ') };
    }
    try {
      const rendered = def.output.render(c.args, data);
      if (!rendered) throw new Error('render 返回空');
    } catch (e: any) {
      return { name: c.name, ok: false, phase: 'render', ms: Date.now() - started, detail: String(e?.message ?? e).slice(0, 280) };
    }
    return { name: c.name, ok: true, phase: 'ok', ms: Date.now() - started, detail: JSON.stringify(data).slice(0, 120) };
  } catch (e: any) {
    return { name: c.name, ok: false, phase: 'throw', ms: Date.now() - started, detail: String(e?.message ?? e).slice(0, 280) };
  }
}

function withBudget(c: Case, fn: () => Promise<any>): Promise<any> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ name: c.name, ok: false, phase: 'timeout', ms: c.budgetMs, detail: '超过预算 ' + c.budgetMs + 'ms 终止（后端慢/挂起）' }), c.budgetMs);
    fn().then((r) => { clearTimeout(timer); resolve(r); }).catch((e) => { clearTimeout(timer); resolve(e); });
  });
}
// ---------- agent-os 健康端点探测 ----------
console.log('== agent-os :8080 健康端点探测 ==');
for (const p of ['/health', '/api/health', '/api/v1/health', '/api/agent/status', '/status']) {
  try {
    const r = await fetch('http://localhost:8080' + p, { signal: AbortSignal.timeout(4000) });
    console.log('probe', p, '->', r.status);
  } catch (e: any) {
    console.log('probe', p, '-> ERR', e?.message ?? e);
  }
}

// ---------- 执行 ----------
console.log('== 冒烟复测 Round 5（共 ' + cases.length + ' 项）==');
const results: any[] = [];
let idx = 0;
for (const c of cases) {
  idx += 1;
  const r = await withBudget(c, () => runCase(c));
  results.push(r);
  const flag = r.ok ? 'PASS' : 'FAIL';
  console.log('[' + idx + '/' + cases.length + '] ' + flag + ' ' + r.name + ' [' + r.phase + ' ' + r.ms + 'ms] ' + r.detail);
}
const passed = results.filter((r) => r.ok).length;
console.log('== 汇总：' + passed + '/' + results.length + ' 通过 ==');
for (const r of results.filter((x) => !x.ok)) {
  console.log('FAILED:', r.name, '|', r.phase, '|', r.detail);
}
process.exit(passed === results.length ? 0 : 1);
