import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchTriggersPrompt, type WatchTriggersParams } from './prompt';

/** 盯盘触发查询/增量轮询（2026-10-20 框架适配：agent 的"信号感知"通道） */
export class WatchTriggersTool extends BaseTool<WatchTriggersParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_triggers', category: 'data', version: '1.0.0', timeoutMs: 20000,
  };
  protected readonly prompt = watchTriggersPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }

  protected validate(args: WatchTriggersParams): ValidationResult {
    if (args?.symbol && !/^\d{6}(\.(SH|SZ))?$/.test(String(args.symbol).trim())) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol',
               issue: `无效的股票代码: ${args.symbol}`, expected: '6 位数字', example: '000999' };
    }
    if (args?.since && Number.isNaN(Date.parse(String(args.since)))) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'since',
               issue: `since 不是合法时间: ${args.since}`, expected: 'ISO 时间',
               example: '2026-10-20T10:00:00' };
    }
    return { success: true };
  }

  protected async execute(args: WatchTriggersParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getWatchTriggers({
      symbol: args?.symbol ? String(args.symbol).split('.')[0] : undefined,
      disposition: args?.disposition, since: args?.since, limit: args?.limit ?? 50,
    });
    if (!res || res.success !== true) {
      throw new Error(`盯盘触发查询失败：${res?.error || res?.message || '未知原因'}（禁止当作"没有新信号"）`);
    }
    return res;
  }
}

export function createWatchTriggersTool(qv2: QuantsysV2Client) {
  return new WatchTriggersTool(qv2) as any;
}
