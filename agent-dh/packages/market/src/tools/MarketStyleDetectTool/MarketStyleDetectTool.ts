/**
 * MarketStyleDetectTool - 市场风格检测工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { marketStyleDetectPrompt, MarketStyleDetectParams, MarketStyleDetectResult } from './prompt';

/**
 * 市场风格检测工具类
 */
export class MarketStyleDetectTool extends BaseTool<MarketStyleDetectParams, MarketStyleDetectResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'market_style_detect',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = marketStyleDetectPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: MarketStyleDetectParams): ValidationResult {
    // 无参数，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(_args: MarketStyleDetectParams, _context: ToolContext): Promise<MarketStyleDetectResult> {
    const result = await this.qv2.getMarketStyle();
    return result as MarketStyleDetectResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: MarketStyleDetectResult, _context: ToolContext): ToolResponse<MarketStyleDetectResult> {
    return {
      success: true,
      data: result,
    };
  }
}
