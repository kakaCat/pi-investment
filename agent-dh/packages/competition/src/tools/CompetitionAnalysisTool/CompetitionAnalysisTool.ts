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
    // TODO: 实现 getCompetitionAnalysis 方法
    // 暂时返回模拟数据
    return {
      symbol: args.symbol,
      company_name: '待实现',
      industry: {
        level1: '待实现',
        level2: '待实现',
      },
      competitors: [],
      competitive_advantages: [],
      competitive_disadvantages: [],
      summary: '竞争分析功能待后端实现',
    };
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
