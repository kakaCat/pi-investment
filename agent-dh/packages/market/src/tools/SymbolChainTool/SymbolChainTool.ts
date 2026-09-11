import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { symbolChainPrompt, type SymbolChainParams } from './prompt';

export class SymbolChainTool extends BaseTool<SymbolChainParams, any> {
  protected readonly metadata: ToolMetadata = { name: 'symbol_chain', category: 'market', version: '1.0.0', timeoutMs: 20000 };
  protected readonly prompt = symbolChainPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }
  protected validate(args: SymbolChainParams): ValidationResult {
    if (!args?.symbol || !/^\d{6}$/.test(args.symbol)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol', issue: `无效的股票代码: ${args?.symbol}`, expected: 'A股6位数字代码，如 600176', example: '600176' };
    }
    return { success: true };
  }
  protected async execute(args: SymbolChainParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getStockChain(args.symbol);
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      throw new Error(`个股产业链反查失败（${args.symbol}）：${why}。禁止据此判定『该股不属于任何产业链』`);
    }
    const p: any = res.data ?? res;
    const chains: any[] = Array.isArray(p) ? p : (p?.chains ?? []);
    // 归一化摘要（原始行保留在 chains，不丢字段）：后端真实字段为 chain_name/chain_id/node_name
    const summary = chains.map((c: any) => ({
      chain: c?.chain_name ?? c?.chain ?? c?.chain_id ?? null,
      node: c?.node_name ?? null,
      stage: c?.stage ?? null,
      role: c?.role ?? null,
      exposure_pct: c?.exposure?.pct ?? null,
      evidence_kind: c?.evidence_kind ?? null,
      confidence: c?.confidence ?? null,
      as_of: c?.exposure?.as_of ?? null,
    }));

    return sanitizeLossless({
      symbol: p?.symbol ?? args.symbol,
      name: p?.name ?? null,
      count: chains.length,
      summary,
      chains,
      note: chains.length === 0
        ? '该标的未归入任何已策展链（链拓扑为人工策展，覆盖有限；不等于它不在产业链中）'
        : '环节归位证据：主营构成 > 行业分类 > 概念成分',
      source: res.source ?? null,
      as_of: p?.as_of ?? null,
    });
  }
}
