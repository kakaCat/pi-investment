/**
 * DataFetchDividendTool - 股息/分红数据工具
 *
 * 2026-09-02：akshare 夜间不可用，响应结构未经实测——透明透传不做字段映射
 * （工程纪律：字段假设必须用真实数据验证；白天数据源恢复后验证契约再细化）。
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchDividendPrompt, DataFetchDividendParams } from './prompt';

export class DataFetchDividendTool extends BaseTool<DataFetchDividendParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_dividend',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = dataFetchDividendPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchDividendParams): ValidationResult {
    if (args.mode === 'history') {
      if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'symbol',
          issue: 'history 模式必须传 6 位数字股票代码',
          received: String(args.symbol ?? ''),
          expected: '6位数字',
          example: '601857',
        };
      }
    }
    return { success: true };
  }

  protected async execute(args: DataFetchDividendParams, _context: ToolContext): Promise<any> {
    if (args.mode === 'screen') {
      const result = await this.qv2.screenHighDividend({
        minYield: args.min_yield ?? 3,
        minYears: args.min_years ?? 5,
      });
      return sanitizeLossless({ mode: 'screen', filters: { min_yield: args.min_yield ?? 3, min_years: args.min_years ?? 5 }, data: result });
    }
    const result = await this.qv2.getDividends(args.symbol!, args.min_years ?? 5);
    return sanitizeLossless({ mode: 'history', symbol: args.symbol, data: result });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
