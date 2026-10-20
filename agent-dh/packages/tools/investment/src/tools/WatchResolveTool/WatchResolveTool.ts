import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchResolvePrompt, type WatchResolveParams } from './prompt';

/** 处置盯盘触发（2026-10-20 框架适配）：agent 的「信号收敛」动作 */
export class WatchResolveTool extends BaseTool<WatchResolveParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_resolve', category: 'action', version: '1.0.0', timeoutMs: 20000,
  };
  protected readonly prompt = watchResolvePrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }

  protected validate(args: WatchResolveParams): ValidationResult {
    const tid = Number(args?.trigger_id);
    if (!Number.isInteger(tid) || tid <= 0) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'trigger_id',
               issue: `trigger_id 非法: ${args?.trigger_id}`, expected: '正整数', example: 3483 };
    }
    if (!['handled', 'ignored', 'expired'].includes(String(args?.disposition))) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'disposition',
               issue: `disposition 非法: ${args?.disposition}`, expected: 'handled|ignored|expired' };
    }
    if (String(args?.disposition) === 'ignored' && !String(args?.reason || '').trim()) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'reason',
               issue: 'ignored 必须填写 reason（为什么不动 + 下次什么条件下才动）' };
    }
    return { success: true };
  }

  protected async execute(args: WatchResolveParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).resolveWatchTrigger(Number(args.trigger_id), {
      disposition: String(args.disposition),
      reason: args?.reason ? String(args.reason) : undefined,
      by: 'agent',
    });
    if (!res || res.success !== true) {
      throw new Error(`触发处置失败：${res?.error || res?.message || '未知原因'}`);
    }
    return res;
  }
}

export function createWatchResolveTool(qv2: QuantsysV2Client) {
  const tool = new WatchResolveTool(qv2);
  return tool.toDSHToolDefinition();
}
