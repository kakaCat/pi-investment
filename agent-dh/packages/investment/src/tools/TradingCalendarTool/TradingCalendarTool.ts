import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { tradingCalendarPrompt, TradingCalendarParams, TradingCalendarResult } from './prompt';

export class TradingCalendarTool extends BaseTool<TradingCalendarParams, TradingCalendarResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'trading_calendar',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = tradingCalendarPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: TradingCalendarParams): ValidationResult {
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

  protected async execute(args: TradingCalendarParams, _context: ToolContext): Promise<TradingCalendarResult> {
    const dateStr = args.date || this.todayStr();
    const d = new Date(dateStr + 'T12:00:00');
    const dow = d.getDay(); // 0=周日 6=周六
    const isWeekend = dow === 0 || dow === 6;

    // 先试后端日历源
    try {
      const res = await this.qv2.getTradingCalendar();
      if (res.success) {
        const days = this.extractDates(res);
        if (days.length > 0) {
          return {
            date: dateStr,
            is_trading_day: days.includes(dateStr),
            is_weekend: isWeekend,
            source: 'akshare(交易日历)',
          };
        }
      }
    } catch {
      // 落入周末兜底
    }

    // 降级：周末排除法（法定节假日无法覆盖，注明）
    return {
      date: dateStr,
      is_trading_day: !isWeekend,
      is_weekend: isWeekend,
      source: 'fallback(周末排除)',
      note: isWeekend
        ? '周末非交易日'
        : '日历源不可用，按周一~周五判定为交易日；法定节假日请以交易所公告为准',
    };
  }

  private extractDates(res: any): string[] {
    const d = res?.data?.data ?? res?.data ?? [];
    if (!Array.isArray(d)) return [];
    return d
      .map((r: any) => (typeof r === 'string' ? r : r?.trade_date || r?.date || r?.['交易日']))
      .filter((s: any) => typeof s === 'string')
      .map((s: string) => s.slice(0, 10));
  }

  private todayStr(): string {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }
}
