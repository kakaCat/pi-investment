import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchBriefPrompt, type WatchBriefParams } from './prompt';

/** 单标的盯盘简报（2026-10-20 框架适配）：一屏聚合，不用自己拼 5 个端点 */
export class WatchBriefTool extends BaseTool<WatchBriefParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_brief', category: 'data', version: '1.0.0', timeoutMs: 20000,
  };
  protected readonly prompt = watchBriefPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }

  protected validate(args: WatchBriefParams): ValidationResult {
    const s = String(args?.symbol || '').trim();
    if (!/^\d{6}(\.(SH|SZ))?$/.test(s)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol',
               issue: `无效的股票代码: ${args?.symbol}`, expected: '6 位数字，可带 .SH/.SZ',
               example: '000999' };
    }
    return { success: true };
  }

  protected async execute(args: WatchBriefParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getWatchBrief(String(args.symbol).trim());
    if (!res || res.success !== true) {
      throw new Error(`盯盘简报获取失败：${res?.error || res?.message || '未知原因'}（禁止当作"该标的无盯盘信息"）`);
    }
    return res;
  }
}

export function createWatchBriefTool(qv2: QuantsysV2Client) {
  return new WatchBriefTool(qv2) as any;
}
