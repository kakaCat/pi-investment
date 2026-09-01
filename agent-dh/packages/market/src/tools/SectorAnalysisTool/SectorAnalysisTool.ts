/**
 * SectorAnalysisTool - 行业分析工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { sectorAnalysisPrompt, SectorAnalysisParams, SectorAnalysisResult } from './prompt';

/**
 * 行业分析工具类
 */
export class SectorAnalysisTool extends BaseTool<SectorAnalysisParams, SectorAnalysisResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'sector_analysis',
    category: 'market',
    version: '1.0.1',
    timeoutMs: 40000,
  };

  protected readonly prompt = sectorAnalysisPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: SectorAnalysisParams): ValidationResult {
    // 参数都是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: SectorAnalysisParams, _context: ToolContext): Promise<SectorAnalysisResult> {
    const result = await this.qv2.getSectorAnalysis({
      sector: args.sector,
      days: args.days || 5,
    });
    return result as SectorAnalysisResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: SectorAnalysisResult, _context: ToolContext): ToolResponse<SectorAnalysisResult> {
    return {
      success: true,
      data: result,
    };
  }
}
