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
   *
   * 修复（2026-09-10，w-23c70356）：原实现把缺失值统一填 `null`，而输出 schema 把
   * dimensions/raw 的子键声明为 `type: 'number'`、对象节点 additionalProperties:false
   * —— null 触发校验失败（value.dimensions.retail_flow_score must be a number），
   * 工具整体不可用。改为"无数据即不出键"：数值键只接受有限数字，null/NaN/字符串一律剔除；
   * 剔空后的嵌套对象也不再输出。render 侧已用 `?? 'N/A'` 兜底。
   */
  private _shape(d: any): RetailPanicIndexResult {
    const num = (v: any): number | undefined =>
      typeof v === 'number' && Number.isFinite(v) ? v : undefined;

    const compact = <T extends Record<string, any>>(obj: T): Record<string, any> => {
      const out: Record<string, any> = {};
      for (const [key, value] of Object.entries(obj)) {
        if (value === null || value === undefined) continue;
        if (typeof value === 'object' && !Array.isArray(value)) {
          const nested = compact(value as Record<string, any>);
          if (Object.keys(nested).length === 0) continue;
          out[key] = nested;
          continue;
        }
        out[key] = value;
      }
      return out;
    };

    return compact({
      trade_date: d?.trade_date ?? '',
      panic_index: num(d?.panic_index),
      level: d?.level ?? 'unknown',
      degraded: d?.degraded ?? true,
      dimensions: {
        retail_flow_score: num(d?.dimensions?.retail_flow_score),
        ad_ratio_score: num(d?.dimensions?.ad_ratio_score),
        volume_score: num(d?.dimensions?.volume_score),
        fear_greed_score: num(d?.dimensions?.fear_greed_score),
        volatility_score: num(d?.dimensions?.volatility_score),
      },
      raw: {
        retail_flow_yi: num(d?.raw?.retail_flow_yi),
        ad_ratio: num(d?.raw?.ad_ratio),
        volume_ratio: num(d?.raw?.volume_ratio),
        fear_greed_index: num(d?.raw?.fear_greed_index),
        volatility: num(d?.raw?.volatility),
      },
      reason: d?.reason,
    }) as RetailPanicIndexResult;
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
