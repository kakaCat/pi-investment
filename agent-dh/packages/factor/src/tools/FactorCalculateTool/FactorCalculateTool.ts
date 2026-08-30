import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { factorCalculatePrompt, type FactorCalculateParams, type FactorCalculateResult } from './prompt';

export class FactorCalculateTool extends BaseTool<FactorCalculateParams, FactorCalculateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'factor_calculate',
    category: 'factor',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = factorCalculatePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: FactorCalculateParams): ValidationResult {
    const { symbol, factors } = params;

    // 检查 symbol 格式
    if (!symbol || !/^\d{6}$/.test(symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: `无效的股票代码格式: ${symbol}`,
        expected: 'A股6位数字代码，如 600519',
      };
    }

    // 检查 factors 数组（如果提供）
    const validFactors = ['rsi', 'macd', 'pe', 'pb', 'roe', 'turnover', 'volatility'];
    if (factors && factors.length > 0) {
      const invalidFactors = factors.filter(f => !validFactors.includes(f));
      if (invalidFactors.length > 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'factors',
          issue: `无效的因子: ${invalidFactors.join(', ')}`,
          expected: validFactors.join(', '),
        };
      }
    }

    return { success: true };
  }

  protected async execute(params: FactorCalculateParams, context: ToolContext): Promise<FactorCalculateResult> {
    const { symbol, factors } = params;

    const raw: any = await this.qv2.calculateFactors({
      symbol,
      factors,
    });

    // 后端实际返回 factors 为数组 [{factor_name, factor_value, factor_date, symbol}]，
    // 与输出契约的「因子值字典」不符。在边界处归一化：同名因子取最新日期的值，
    // 并附带 factor_dates 便于识别陈旧数据（如技术指标滞后数月）。
    if (Array.isArray(raw?.factors)) {
      const dict: Record<string, unknown> = {};
      const dates: Record<string, string> = {};
      for (const f of raw.factors) {
        const name = f?.factor_name;
        if (!name) continue;
        const date = String(f?.factor_date ?? '');
        if (!(name in dates) || date > dates[name]) {
          dates[name] = date;
          dict[name] = f?.factor_value;
        }
      }

      // 2026-08-28 根本性修复：因子数据 freshness 校验，防止静默毒化选股质量
      const now = new Date();
      const warnings: string[] = [];
      const errors: string[] = [];
      for (const [name, dateStr] of Object.entries(dates)) {
        if (!dateStr) continue;
        const factorDate = new Date(dateStr);
        const staleDays = Math.floor((now.getTime() - factorDate.getTime()) / 86400000);
        if (staleDays > 7) {
          errors.push(`${name} 数据过期 ${staleDays} 天（${dateStr}），超过 7 天阈值`);
        } else if (staleDays > 3) {
          warnings.push(`${name} 数据陈旧 ${staleDays} 天（${dateStr}）`);
        }
      }

      if (errors.length > 0) {
        throw new Error(`因子数据过期拒绝服务：${errors.join('; ')}。请触发因子计算管道补录或联系后端排查。`);
      }

      // 2026-08-30 修复：freshness_warnings: undefined 显式键会导致 lossless 校验失败，改条件展开
      return sanitizeLossless({
        ...raw,
        factors: dict,
        factor_dates: dates,
        ...(warnings.length > 0 ? { freshness_warnings: warnings, degraded: true } : { degraded: false }),
      });
    }

    return raw;
  }

  protected wrap(data: FactorCalculateResult, _context: ToolContext): ToolResponse<FactorCalculateResult> {
    return {
      success: true,
      data,
    };
  }
}
