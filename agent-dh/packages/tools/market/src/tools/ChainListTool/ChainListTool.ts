import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { chainListPrompt, type ChainListParams } from './prompt';

export class ChainListTool extends BaseTool<ChainListParams, any> {
  protected readonly metadata: ToolMetadata = { name: 'chain_list', category: 'market', version: '1.0.0', timeoutMs: 20000 };
  protected readonly prompt = chainListPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }
  protected validate(_args: ChainListParams): ValidationResult { return { success: true }; }
  protected async execute(_args: ChainListParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getIndustryChains();
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      throw new Error(`产业链清单查询失败：${why}。禁止视为『系统中没有产业链』`);
    }
    const p: any = res.data ?? res;
    const chains: any[] = Array.isArray(p) ? p : (p?.chains ?? p?.data ?? []);
    if (chains.length === 0) throw new Error('产业链清单为空：拓扑尚未策展或落库，请先执行 build/ingest。');
    return sanitizeLossless({ count: chains.length, chains, source: res.source ?? p?.source ?? null, as_of: p?.as_of ?? null });
  }
}
