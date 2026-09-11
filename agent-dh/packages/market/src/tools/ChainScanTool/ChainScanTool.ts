import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { chainScanPrompt, type ChainScanParams } from './prompt';

export class ChainScanTool extends BaseTool<ChainScanParams, any> {
  protected readonly metadata: ToolMetadata = { name: 'chain_scan', category: 'market', version: '1.0.0', timeoutMs: 45000 };
  protected readonly prompt = chainScanPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }
  protected validate(args: ChainScanParams): ValidationResult {
    if (!args?.name || String(args.name).trim().length === 0) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'name', issue: 'name 必填', expected: "产业链名称，如 '玻纤'", guide: '先用 chain_list 查看可用链名' };
    }
    return { success: true };
  }
  protected async execute(args: ChainScanParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).scanIndustryChain(args.name, { include_quotes: args.include_quotes ?? false });
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      const att = res?.attempted_sources ? `（已尝试: ${(res.attempted_sources || []).join(', ')}）` : '';
      throw new Error(`链式扫描失败（${args.name}）：${why}${att}。若为『链不存在』请用 chain_list 确认可用链名——不得当作『该链无成员』`);
    }
    const p: any = res.data ?? res;
    const stages = p?.stages ?? p?.by_stage ?? {};
    const memberCount = p?.member_count ?? Object.values(stages).reduce((n: number, arr: any) => n + (Array.isArray(arr) ? arr.length : 0), 0);
    if (!memberCount) throw new Error(`链式扫描返回空成员（${args.name}）：该链尚未 build 或成员归位失败。`);
    return sanitizeLossless({ chain: p?.chain ?? args.name, member_count: memberCount, stages, evidence_note: p?.evidence_note ?? '成员证据口径：主营构成 > 行业分类 > 概念成分', source: res.source ?? null, as_of: p?.as_of ?? null });
  }
}
