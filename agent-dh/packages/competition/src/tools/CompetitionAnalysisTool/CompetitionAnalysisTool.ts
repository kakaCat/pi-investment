import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
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
      const response: any = await this.qv2.getCompetitionAnalysis(
        args.symbol,
        args.include_financial ?? true
      );

      // 2026-08-30 修复：后端返回 camelCase 字段（companyName/marketCap/competitivePosition…），
      // 输出 schema 要求 snake_case 且 additionalProperties:false、字段非空，
      // 直接透传会产生 undefined 键 → lossless 校验失败。在此显式映射并给默认值。
      const industry = {
        level1: response?.industry?.level1 ?? '',
        level2: response?.industry?.level2 ?? '',
        level3: response?.industry?.level3 ?? '',
      };
      const market_size = response?.marketSize ? {
        total_market_cap: typeof response.marketSize.totalMarketCap === 'number' ? response.marketSize.totalMarketCap : 0,
        industry_rank: typeof response.marketSize.industryRank === 'number' ? response.marketSize.industryRank : 0,
        market_share: typeof response.marketSize.marketShare === 'number' ? response.marketSize.marketShare : 0,
      } : undefined;
      const competitors = Array.isArray(response?.competitors)
        ? response.competitors.map((c: any) => ({
            symbol: c?.symbol ?? '',
            name: c?.name ?? '',
            market_cap: typeof c?.marketCap === 'number' ? c.marketCap : 0,
            market_share: typeof c?.marketShare === 'number' ? c.marketShare : 0,
            competitive_position: c?.competitivePosition ?? '',
          }))
        : [];
      const financial_comparison = response?.financialComparison ? {
        metrics: Array.isArray(response.financialComparison.metrics) ? response.financialComparison.metrics : [],
        data: Array.isArray(response.financialComparison.data) ? response.financialComparison.data : [],
      } : undefined;

      return sanitizeLossless({
        symbol: response?.symbol ?? args.symbol,
        company_name: response?.companyName ?? '',
        industry,
        market_size,
        competitors,
        financial_comparison,
        competitive_advantages: Array.isArray(response?.competitiveAdvantages) ? response.competitiveAdvantages : [],
        competitive_disadvantages: Array.isArray(response?.competitiveDisadvantages) ? response.competitiveDisadvantages : [],
        summary: response?.summary ?? '',
      });
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
