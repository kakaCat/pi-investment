import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { competitionAnalysisPrompt, CompetitionAnalysisParams, CompetitionAnalysisResult } from './prompt';

/**
 * Competition Analysis Tool
 *
 * 分析股票所在行业的竞争格局
 */
export class CompetitionAnalysisTool extends BaseTool<
  CompetitionAnalysisParams,
  CompetitionAnalysisResult
> {
  protected readonly metadata: ToolMetadata = {
    name: 'competition_analysis',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = competitionAnalysisPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: CompetitionAnalysisParams): ValidationResult {
    if (!args.symbol || typeof args.symbol !== 'string') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是字符串',
        received: typeof args.symbol,
        expected: 'string',
        example: '600519',
      };
    }

    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是 6 位数字',
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
  protected async execute(
    args: CompetitionAnalysisParams,
    _context: ToolContext
  ): Promise<CompetitionAnalysisResult> {
    try {
      const response = await this.qv2.getCompetitionAnalysis(
        args.symbol,
        args.include_financial ?? true
      );

      return {
        symbol: response.symbol,
        company_name: response.company_name,
        industry: response.industry,
        market_size: response.market_size,
        competitors: response.competitors,
        financial_comparison: response.financial_comparison,
        competitive_advantages: response.competitive_advantages,
        competitive_disadvantages: response.competitive_disadvantages,
        summary: response.summary,
      };
    } catch (error) {
      throw new Error(`竞争分析失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: CompetitionAnalysisResult, _context: ToolContext): ToolResponse<CompetitionAnalysisResult> {
    return {
      success: true,
      data: result,
    };
  }
}
