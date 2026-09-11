/**
 * P2 产业链工具 LIVE 验收（RFC 015 §2，w-f436d4ea）
 *
 * 覆盖 chain_list / chain_scan / symbol_chain 三工具对真实后端的端到端可用性，
 * 并锁死两条"不得静默误判"的语义：
 *   · 链不存在 → 必须显式报错（不得当作"该链无成员"）
 *   · symbol_chain 无记录 → 必须说明"策展覆盖有限"，不得断言"不在产业链中"
 *
 * 运行：cd agent-dh && LIVE=1 npx vitest run tests/p2-chain-tools-verify.test.ts
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ChainListTool } from '../packages/market/src/tools/ChainListTool/ChainListTool.js';
import { ChainScanTool } from '../packages/market/src/tools/ChainScanTool/ChainScanTool.js';
import { SymbolChainTool } from '../packages/market/src/tools/SymbolChainTool/SymbolChainTool.js';

const LIVE = process.env.LIVE === '1';
const ctx = {} as any;
const client: any = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
  timeout: 60000,
} as any);

describe('契约（无需后端）', () => {
  it('chain_scan：name 为空被拒并提示先 chain_list', async () => {
    const tool: any = new ChainScanTool(client);
    const r: any = await tool.call({ name: '' } as any);
    expect(r.success).toBe(false);
    expect(String(JSON.stringify(r.error))).toContain('chain_list');
  });

  it('chain_scan：链不存在必须显式报错（不得当空链）', async () => {
    const bad: any = { scanIndustryChain: async () => ({ success: false, error: '策展库中不存在产业链：不存在的链', attempted_sources: ['curated'] }) };
    const tool: any = new ChainScanTool(bad);
    await expect(tool.execute({ name: '不存在的链' }, ctx)).rejects.toThrow(/链不存在|不得当作/);
  });

  it('chain_list：全源失败必须显式报错', async () => {
    const bad: any = { getIndustryChains: async () => ({ success: false, error: 'all providers failed' }) };
    const tool: any = new ChainListTool(bad);
    await expect(tool.execute({}, ctx)).rejects.toThrow(/没有产业链|失败/);
  });

  it('chain_list：空清单必须显式报错（不得静默返回 0 条）', async () => {
    const bad: any = { getIndustryChains: async () => ({ success: true, data: { chains: [] } }) };
    const tool: any = new ChainListTool(bad);
    await expect(tool.execute({}, ctx)).rejects.toThrow(/为空/);
  });

  it('symbol_chain：无记录时提示"策展覆盖有限"而非断言不在产业链', async () => {
    const bad: any = { getStockChain: async () => ({ success: true, data: { symbol: '999999', chains: [] } }) };
    const tool: any = new SymbolChainTool(bad);
    const r: any = await tool.execute({ symbol: '999999' }, ctx);
    expect(r.count).toBe(0);
    expect(String(r.note)).toContain('不等于');
  });
});

describe.skipIf(!LIVE)('LIVE（真实后端）', () => {
  it('chain_list：返回已策展产业链', async () => {
    const tool: any = new ChainListTool(client);
    const r: any = await tool.execute({}, ctx);
    console.log('[chain_list]', JSON.stringify({ count: r.count, source: r.source, names: (r.chains || []).map((c: any) => c.name).slice(0, 4) }));
    expect(r.count).toBeGreaterThan(0);
    expect(r.source).toBeTruthy();
  }, 60000);

  it('chain_scan(玻纤)：按环节分组返回成员（含证据口径）', async () => {
    const tool: any = new ChainScanTool(client);
    const r: any = await tool.execute({ name: '玻纤' }, ctx);
    const stageKeys = Object.keys(r.stages || {});
    console.log('[chain_scan 玻纤]', JSON.stringify({ chain: r.chain, member_count: r.member_count, stages: stageKeys, upstream_head: (r.stages?.upstream || []).slice(0, 2).map((m: any) => m.symbol) }));
    expect(r.member_count).toBeGreaterThan(0);
    expect(stageKeys.length).toBeGreaterThan(0);
    expect(r.evidence_note).toBeTruthy();
  }, 60000);

  it('symbol_chain(600176)：返回所属链/环节/占比证据', async () => {
    const tool: any = new SymbolChainTool(client);
    const r: any = await tool.execute({ symbol: '600176' }, ctx);
    console.log('[symbol_chain 600176]', JSON.stringify(r.summary));
    expect(r.count).toBeGreaterThan(0);
    const first = r.summary[0];
    expect(first.chain).toBeTruthy();
    expect(first.stage).toBeTruthy();
  }, 60000);
});
