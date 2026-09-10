/**
 * RecallAuditTool - 记忆召回审计
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { recallAuditPrompt, type RecallAuditParams } from './prompt';

export class RecallAuditTool extends BaseTool<RecallAuditParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'memory_recall_audit',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = recallAuditPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RecallAuditParams): ValidationResult {
    if (args?.action && !['stats', 'list'].includes(args.action)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: `无效的 action: ${args.action}`,
        expected: 'stats 或 list',
      };
    }
    const pageSize = args?.page_size;
    if (pageSize !== undefined && (pageSize < 1 || pageSize > 100)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'page_size',
        issue: 'page_size 必须在 1-100 之间',
        received: String(pageSize),
        expected: '1-100',
      };
    }
    return { success: true };
  }

  protected async execute(args: RecallAuditParams, _context: ToolContext): Promise<any> {
    const action = args.action ?? 'stats';

    if (action === 'list') {
      const res: any = await (this.qv2 as any).getRecallAudit({
        flow: args.flow,
        suppressed_only: args.suppressed_only,
        date_from: args.date_from,
        date_to: args.date_to,
        page: args.page ?? 1,
        page_size: args.page_size ?? 20,
      });
      if (!res || res.success === false || res.error) {
        throw new Error(`召回审计明细查询失败：${res?.error || res?.message || '未知原因'}`);
      }
      const items: any[] = res.items ?? [];
      return sanitizeLossless({
        action,
        count: items.length,
        total: res.total ?? null,
        items: items.map((it: any) => ({
          id: it?.id,
          ts: it?.ts,
          flow: it?.flow,
          query_text: it?.query_text,
          strategy: it?.strategy,
          degraded: it?.degraded,
          gate_result: it?.gate_result,
          suppress_reason: it?.suppress_reason,
          hits: (it?.hits ?? []).slice(0, 5),
        })),
        note: '命中分数偏低（<0.1）说明语义相关性弱，需结合 suppress_reason 判断是否等同零命中',
      });
    }

    const res: any = await (this.qv2 as any).getRecallAuditStats({
      date_from: args.date_from,
      date_to: args.date_to,
    });
    if (!res || res.error || typeof res.total !== 'number') {
      throw new Error(`召回审计统计查询失败：${res?.error || res?.message || '返回结构异常'}`);
    }

    // 口径解读：压制主因决定「无记忆」与「检索坏」的判定方向
    const suppressReasons: Record<string, number> = res.suppress_reasons ?? {};
    const topReason = Object.entries(suppressReasons).sort((a, b) => (b[1] as number) - (a[1] as number))[0];
    const interpretation = res.suppressed === 0
      ? '无压制记录：召回全部注入。'
      : topReason && topReason[0] === 'empty-result'
        ? `压制以 empty-result 为主（${topReason[1]} 条，占压制 ${((topReason[1] as number) / res.suppressed * 100).toFixed(1)}%）：说明被压制的查询在库中确无相关内容，不等于检索故障。`
        : `压制主因为 ${topReason?.[0] ?? '未知'}（${topReason?.[1] ?? 0} 条）：非 empty-result 的压制需排查检索链路。`;

    return sanitizeLossless({
      action,
      total: res.total,
      injected: res.injected,
      suppressed: res.suppressed,
      injection_rate: res.injection_rate,
      by_flow: res.by_flow ?? {},
      suppress_reasons: suppressReasons,
      score_histogram: res.score_histogram ?? [],
      interpretation,
      window: { date_from: args.date_from ?? null, date_to: args.date_to ?? null },
      note: '数据源 quantsys-v2 /api/memory/recall-audit/stats（裸 JSON）',
    });
  }
}
