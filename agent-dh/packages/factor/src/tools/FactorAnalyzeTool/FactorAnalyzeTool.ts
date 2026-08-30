import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { factorAnalyzePrompt, type FactorAnalyzeParams, type FactorAnalyzeResult } from './prompt';

export class FactorAnalyzeTool extends BaseTool<FactorAnalyzeParams, FactorAnalyzeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'factor_analyze',
    category: 'factor',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = factorAnalyzePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: FactorAnalyzeParams): ValidationResult {
    const { factor_name, start_date, end_date } = params;

    // 检查 factor_name 不为空
    if (!factor_name || factor_name.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'factor_name',
        issue: '因子名称不能为空',
      };
    }

    // 检查 start_date 格式
    if (start_date && !/^\d{4}-\d{2}-\d{2}$/.test(start_date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'start_date',
        issue: `无效的日期格式: ${start_date}`,
        expected: 'YYYY-MM-DD，如 2023-01-01',
      };
    }

    // 检查 end_date 格式
    if (end_date && !/^\d{4}-\d{2}-\d{2}$/.test(end_date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'end_date',
        issue: `无效的日期格式: ${end_date}`,
        expected: 'YYYY-MM-DD，如 2024-12-31',
      };
    }

    // 检查日期顺序
    if (start_date && end_date && start_date > end_date) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'start_date',
        issue: '开始日期不能晚于结束日期',
        expected: `start_date <= end_date`,
      };
    }

    return { success: true };
  }

  protected async execute(params: FactorAnalyzeParams, context: ToolContext): Promise<FactorAnalyzeResult> {
    const { factor_name } = params;

    // 2026-08-30 修复：prompt 文档承诺默认 1 年前~今天，但 execute 直接透传 undefined，
    // 后端校验"开始日期和结束日期不能为空"返回 400。此处补默认值。
    const end_date = params.end_date ?? new Date().toISOString().slice(0, 10);
    const start_date = params.start_date ?? new Date(Date.now() - 365 * 86400 * 1000).toISOString().slice(0, 10);

    return this.qv2.analyzeFactor({
      factor_name,
      start_date,
      end_date,
    }) as any;
  }

  protected wrap(data: FactorAnalyzeResult, _context: ToolContext): ToolResponse<FactorAnalyzeResult> {
    return {
      success: true,
      data,
    };
  }
}
