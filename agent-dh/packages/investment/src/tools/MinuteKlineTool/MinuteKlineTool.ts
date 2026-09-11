/**
 * MinuteKlineTool - 分钟线（多源故障转移）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { minuteKlinePrompt, type MinuteKlineParams } from './prompt';

const VALID_PERIODS = ['1m', '5m', '15m', '30m', '60m'];

export class MinuteKlineTool extends BaseTool<MinuteKlineParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'minute_kline',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = minuteKlinePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: MinuteKlineParams): ValidationResult {
    if (!args?.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol',
        issue: `无效的股票代码: ${args?.symbol}`, expected: 'A股6位数字代码，如 600150', example: '600150',
      };
    }
    if (args.period !== undefined && !VALID_PERIODS.includes(args.period)) {
      return {
        success: false, errorType: ErrorType.INPUT_ERROR, field: 'period',
        issue: `无效周期: ${args.period}`, expected: VALID_PERIODS.join(', '),
      };
    }
    if (args.limit !== undefined && (args.limit < 1 || args.limit > 1000)) {
      return {
        success: false, errorType: ErrorType.INPUT_ERROR, field: 'limit',
        issue: 'limit 必须在 1-1000 之间', received: String(args.limit), expected: '1-1000',
      };
    }
    return { success: true };
  }

  protected async execute(args: MinuteKlineParams, _context: ToolContext): Promise<any> {
    const period = args.period ?? '5m';
    const res: any = await (this.qv2 as any).getMinuteKlines(args.symbol, {
      period, date: args.date, limit: args.limit ?? 240,
    });

    // 多源失败语义：全部源失败 → 显式失败，不得把空当成"无成交"
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      const attempted = res?.attempted_sources ? `（已尝试: ${(res.attempted_sources || []).join(', ')}）` : '';
      throw new Error(`分钟线获取失败（${args.symbol} ${period}）：${why}${attempted}。禁止视为『无成交/无数据』`);
    }

    const payload: any = res.data ?? res;
    const rows: any[] = Array.isArray(payload) ? payload : (payload?.data ?? payload?.klines ?? []);
    if (rows.length === 0) {
      throw new Error(`分钟线为空（${args.symbol} ${period}）：上游返回空集，非交易时段或该股当日无成交，勿据此下结论。`);
    }

    return sanitizeLossless({
      symbol: args.symbol,
      period,
      count: rows.length,
      data: rows,
      source: res.source ?? payload?.source ?? null,
      attempted_sources: res.attempted_sources ?? null,
      degraded: res.degraded ?? false,
      stale: res.stale ?? false,
      as_of: res.as_of ?? payload?.as_of ?? null,
    });
  }
}
