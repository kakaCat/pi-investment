import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { limitUpPoolPrompt, LimitUpPoolParams, LimitUpPoolResult } from './prompt';

export class LimitUpPoolTool extends BaseTool<LimitUpPoolParams, LimitUpPoolResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'limit_up_pool',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 45000,
  };

  protected readonly prompt = limitUpPoolPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: LimitUpPoolParams): ValidationResult {
    if (args.date && !/^\d{4}-\d{2}-\d{2}$/.test(args.date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'date',
        issue: 'date 格式应为 YYYY-MM-DD',
        received: args.date,
        expected: 'YYYY-MM-DD',
      };
    }
    return { success: true };
  }

  protected async execute(args: LimitUpPoolParams, _context: ToolContext): Promise<LimitUpPoolResult> {
    const date = args.date || this.todayStr();
    const res = await this.qv2.getLimitUpPool(date);

    if (!res.success) {
      return {
        date,
        available: false,
        note: res.error || '涨停池数据源暂不可用（非交易日或 akshare 源异常）',
      };
    }

    let records = this.extractRows(res);
    const total = records.length;
    const maxStreak = records.reduce((m, r) => Math.max(m, Number(r['连板数']) || 1), 0);

    // 连板分布
    const dist: Record<string, number> = {};
    for (const r of records) {
      const s = String(Number(r['连板数']) || 1);
      dist[s] = (dist[s] || 0) + 1;
    }

    // 连板过滤
    if (args.min_streak && args.min_streak > 1) {
      records = records.filter(r => (Number(r['连板数']) || 1) >= args.min_streak!);
    }

    // 情绪判断
    let sentiment = '冰点';
    if (total >= 80) sentiment = '亢奋';
    else if (total >= 50) sentiment = '活跃';
    else if (total >= 20) sentiment = '平稳';

    return {
      date,
      available: true,
      total,
      max_streak: maxStreak,
      streak_distribution: dist,
      records,
      summary: `涨停 ${total} 家，最高 ${maxStreak} 连板，情绪：${sentiment}${args.min_streak ? `（已过滤 ≥${args.min_streak} 连板 ${records.length} 家）` : ''}`,
    };
  }

  private extractRows(res: any): Array<Record<string, any>> {
    const d = res?.data;
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d.data?.records)) return d.data.records;
    if (Array.isArray(d.records)) return d.records;
    if (Array.isArray(d.data)) return d.data;
    return [];
  }

  private todayStr(): string {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
}
