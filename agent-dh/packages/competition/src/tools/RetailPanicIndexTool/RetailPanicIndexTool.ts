/**
 * RetailPanicIndexTool
 *
 * M7-2 散户恐慌代理指标：查询连续恐慌指数（单日或序列）
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { retailPanicIndexPrompt } from './prompt';
import type { RetailPanicIndexParams, RetailPanicIndexResult } from './prompt';

/**
 * Retail Panic Index Tool (M7-2)
 *
 * 连续 0-100 散户恐慌指数，五维合成（资金流/涨跌比/恐慌贪婪/量能/波动率）
 */
export class RetailPanicIndexTool extends BaseTool<
  RetailPanicIndexParams,
  RetailPanicIndexResult
> {
  protected readonly metadata: ToolMetadata = {
    name: 'retail_panic_index',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = retailPanicIndexPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: RetailPanicIndexParams): ValidationResult {
    if (args.days != null && (typeof args.days !== 'number' || args.days < 1 || args.days > 60)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'days',
        issue: 'days 必须是 1-60 的整数',
        received: args.days,
        expected: '1-60',
      };
    }
    if (args.trade_date != null && !/^\d{4}-\d{2}-\d{2}$/.test(args.trade_date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'trade_date',
        issue: 'trade_date 格式必须是 YYYY-MM-DD',
        received: args.trade_date,
        expected: 'YYYY-MM-DD',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: RetailPanicIndexParams,
    _context: ToolContext
  ): Promise<RetailPanicIndexResult> {
    try {
      const response: any = await this.qv2.getRetailPanicIndex(args);

      // 序列模式（days 传入时）
      if (Array.isArray(response?.series)) {
        const first = response.series[0] ?? {};
        return this._shape(first);
      }

      return this._shape(response ?? {});
    } catch (e: any) {
      throw new Error(`散户恐慌指数查询失败: ${e.message}`);
    }
  }

  /**
   * 后端返回 → 输出 schema 显式映射（防 undefined 键）
   */
  private _shape(d: any): RetailPanicIndexResult {
    return {
      trade_date: d?.trade_date ?? '',
      panic_index: d?.panic_index ?? null,
      level: d?.level ?? 'unknown',
      degraded: d?.degraded ?? true,
      dimensions: {
        retail_flow_score: d?.dimensions?.retail_flow_score ?? null,
        ad_ratio_score: d?.dimensions?.ad_ratio_score ?? null,
        volume_score: d?.dimensions?.volume_score ?? null,
        fear_greed_score: d?.dimensions?.fear_greed_score ?? null,
        volatility_score: d?.dimensions?.volatility_score ?? null,
      },
      raw: {
        retail_flow_yi: d?.raw?.retail_flow_yi ?? null,
        ad_ratio: d?.raw?.ad_ratio ?? null,
        volume_ratio: d?.raw?.volume_ratio ?? null,
        fear_greed_index: d?.raw?.fear_greed_index ?? null,
        volatility: d?.raw?.volatility ?? null,
      },
      reason: d?.reason,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: RetailPanicIndexResult, context: ToolContext): ToolResponse<RetailPanicIndexResult> {
    return {
      success: true,
      data: result,
      context,
      timestamp: new Date().toISOString(),
    };
  }
}
