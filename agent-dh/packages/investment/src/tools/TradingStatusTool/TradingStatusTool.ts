/**
 * TradingStatusTool - 交易状态（可交易性硬校验）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { tradingStatusPrompt, type TradingStatusParams } from './prompt';

export class TradingStatusTool extends BaseTool<TradingStatusParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'trading_status',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = tradingStatusPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: TradingStatusParams): ValidationResult {
    if (!args?.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol',
        issue: `无效的股票代码: ${args?.symbol}`, expected: 'A股6位数字代码，如 600150', example: '600150',
      };
    }
    return { success: true };
  }

  protected async execute(args: TradingStatusParams, _context: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getTradingStatus(args.symbol);

    // fail-closed：状态查不到时必须显式失败，绝不能默认"可交易"
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      throw new Error(
        `交易状态查询失败（${args.symbol}）：${why}。**下单前禁止在状态未知的情况下委托**（fail-closed）`,
      );
    }

    const d: any = res.data ?? res;
    if (d?.tradeable === undefined) {
      throw new Error(`交易状态返回结构异常（${args.symbol}）：缺少 tradeable 字段，按 fail-closed 处理。`);
    }

    return sanitizeLossless({
      symbol: d.symbol ?? args.symbol,
      is_st: d.is_st ?? null,
      is_suspended: d.is_suspended ?? null,
      limit_up: d.limit_up ?? null,
      limit_down: d.limit_down ?? null,
      tradeable: d.tradeable,
      limit_ratio: d.limit_ratio ?? null,
      reason: d.reason ?? '',
      as_of: d.as_of ?? res.as_of ?? null,
      source: res.source ?? d.source ?? null,
      cross_source_conflict: res.cross_source_conflict ?? d.cross_source_conflict ?? null,
    });
  }
}
