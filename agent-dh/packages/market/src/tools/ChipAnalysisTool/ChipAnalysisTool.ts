/**
 * ChipAnalysisTool - 筹码分析工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { chipAnalysisPrompt, ChipAnalysisParams, ChipAnalysisResult } from './prompt';

/**
 * 筹码分析工具类
 */
export class ChipAnalysisTool extends BaseTool<ChipAnalysisParams, ChipAnalysisResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'chip_analysis',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = chipAnalysisPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: ChipAnalysisParams): ValidationResult {
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 是必填参数',
        expected: '6位数字股票代码',
        example: '600519',
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
        example: '600519',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: ChipAnalysisParams, _context: ToolContext): Promise<ChipAnalysisResult> {
    const result: any = await this.qv2.getChipDistribution(args.symbol);

    // 映射后端返回数据到 ChipAnalysisResult 类型
    return {
      symbol: result.symbol ?? args.symbol,
      avg_cost: result.avg_cost ?? result.avgCost ?? 0,
      profit_ratio: result.profit_ratio ?? result.profitRatio ?? 0,
      concentration: result.concentration ?? 0,
      support_levels: result.support_levels ?? result.supportLevels ?? [],
      resistance_levels: result.resistance_levels ?? result.resistanceLevels ?? [],
      chip_distribution: result.chip_distribution ?? result.chipDistribution ?? [],
      ...result,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: ChipAnalysisResult, _context: ToolContext): ToolResponse<ChipAnalysisResult> {
    return {
      success: true,
      data: result,
    };
  }
}
