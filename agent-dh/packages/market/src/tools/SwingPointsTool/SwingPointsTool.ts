/**
 * SwingPointsTool - ZigZag 波段买卖点分析工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { swingPointsPrompt, SwingPointsParams, SwingPointsResult } from './prompt';

/**
 * ZigZag 波段分析工具类
 */
export class SwingPointsTool extends BaseTool<SwingPointsParams, SwingPointsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'swing_points',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = swingPointsPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: SwingPointsParams): ValidationResult {
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 是必填参数',
        expected: '6位数字股票代码',
        example: '601857',
      };
    }

    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: args.symbol,
        expected: '6位数字',
        example: '601857',
      };
    }

    if (args.min_change !== undefined) {
      const mc = Number(args.min_change);
      if (!Number.isFinite(mc) || mc < 1 || mc > 30) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'min_change',
          issue: 'min_change 必须在 1 ~ 30 之间',
          received: String(args.min_change),
          expected: '1 ~ 30 的数字',
          example: '5',
        };
      }
    }

    for (const f of ['start_date', 'end_date'] as const) {
      const v = args[f];
      if (v !== undefined && !/^\d{4}-\d{2}-\d{2}$/.test(v)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: f,
          issue: `${f} 格式必须是 YYYY-MM-DD`,
          received: String(v),
          expected: 'YYYY-MM-DD',
          example: '2026-01-01',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: SwingPointsParams, _context: ToolContext): Promise<SwingPointsResult> {
    const result: any = await this.qv2.analyzeSwingPoints({
      symbol: args.symbol,
      startDate: args.start_date,
      endDate: args.end_date,
      minChange: args.min_change,
    });

    // 后端返回 camelCase（convert_keys_to_camel），映射为工具层 snake_case 契约
    const swingPoints = (result.swingPoints ?? result.swing_points ?? []).map((p: any) => ({
      date: p.date,
      price: p.price,
      type: p.type,
      change_pct: p.changePct ?? p.change_pct ?? 0,
    }));
    const trades = (result.trades ?? []).map((t: any) => ({
      buy_date: t.buyDate ?? t.buy_date,
      buy_price: t.buyPrice ?? t.buy_price,
      sell_date: t.sellDate ?? t.sell_date,
      sell_price: t.sellPrice ?? t.sell_price,
      profit_pct: t.profitPct ?? t.profit_pct,
      holding_days: t.holdingDays ?? t.holding_days,
    }));
    const s = result.summary ?? {};
    const latest = swingPoints.length > 0 ? swingPoints[swingPoints.length - 1] : undefined;

    return {
      symbol: result.symbol ?? args.symbol,
      period: result.period ?? { start: args.start_date ?? '', end: args.end_date ?? '' },
      min_change: result.minChange ?? result.min_change ?? args.min_change ?? 5,
      kline_count: result.klineCount ?? result.kline_count,
      swing_points: swingPoints,
      trades,
      summary: {
        total_trades: s.totalTrades ?? s.total_trades ?? 0,
        win_count: s.winCount ?? s.win_count ?? 0,
        loss_count: s.lossCount ?? s.loss_count ?? 0,
        win_rate: s.winRate ?? s.win_rate ?? 0,
        total_return: s.totalReturn ?? s.total_return ?? 0,
        avg_return: s.avgReturn ?? s.avg_return ?? 0,
        max_return: s.maxReturn ?? s.max_return ?? 0,
        max_loss: s.maxLoss ?? s.max_loss ?? 0,
        avg_holding_days: s.avgHoldingDays ?? s.avg_holding_days ?? 0,
      },
      latest_swing: latest ? { date: latest.date, price: latest.price, type: latest.type } : undefined,
      message: result.message,
      error: result.error,
      suggestions: result.suggestions,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: SwingPointsResult, _context: ToolContext): ToolResponse<SwingPointsResult> {
    return {
      success: !result.error,
      data: result,
    };
  }
}
