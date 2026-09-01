import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { lhbPrompt, LhbParams, LhbResult } from './prompt';

export class LhbTool extends BaseTool<LhbParams, LhbResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'lhb_dragon_tiger',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 45000,
  };

  protected readonly prompt = lhbPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: LhbParams): ValidationResult {
    if (!args.date && !args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'date',
        issue: 'date 与 symbol 至少传一个',
        received: 'none',
        expected: 'date=YYYY-MM-DD 或 symbol=6位代码',
      };
    }
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
    if (args.symbol && !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 须为 6 位数字',
        received: args.symbol,
        expected: '6位数字',
      };
    }
    return { success: true };
  }

  protected async execute(args: LhbParams, _context: ToolContext): Promise<LhbResult> {
    if (args.symbol) {
      const res = await this.qv2.getLhbDetail(args.symbol);
      const records = res.success ? this.extractRows(res) : [];
      return {
        mode: `stock:${args.symbol}`,
        available: records.length > 0,
        records,
        summary: records.length ? `个股上榜记录 ${records.length} 条` : undefined,
        degraded_sources: res.success ? undefined : (res.attempted_sources ?? ['unknown']),
        note: records.length ? undefined : (res.error || '该股近期无上榜记录或数据源不可用'),
      };
    }

    const res = await this.qv2.getLhbDaily(args.date!);
    const records = res.success ? this.extractRows(res) : [];
    return {
      mode: `date:${args.date}`,
      available: records.length > 0,
      records,
      summary: records.length ? `${args.date} 龙虎榜 ${records.length} 条上榜记录` : undefined,
      degraded_sources: res.success ? undefined : (res.attempted_sources ?? ['unknown']),
      note: records.length ? undefined : (res.error || '当日无龙虎榜数据（非交易日或数据源不可用）'),
    };
  }

  private extractRows(res: any): Array<Record<string, any>> {
    const d = res?.data;
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d.data)) return d.data;
    if (Array.isArray(d.records)) return d.records;
    return [];
  }
}
