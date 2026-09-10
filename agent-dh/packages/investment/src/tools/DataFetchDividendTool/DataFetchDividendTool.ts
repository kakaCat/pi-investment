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
    const result: any = await this.qv2.getDividends(args.symbol!, args.min_years ?? 5);
    // 2026-09-11 修复（REQ-342799）：实测后端 /api/provider/dividend/{symbol} 返回 success=true，
    // 但每行 dividend_per_share=0.0、日期全 null——上游 akshare 分红源失效被映射成『全 0 有效行』。
    // 全 0/全空必须显式失败：否则会被误读为『该公司不分红』这一事实结论。
    const rows: any[] = Array.isArray(result) ? result : (result?.data ?? []);
    const usable = rows.filter((r: any) => Number(r?.dividend_per_share) > 0 || r?.ex_dividend_date);
    if (rows.length === 0 || usable.length === 0) {
      throw new Error(
        'data_fetch_dividend(history) 无有效分红数据：后端返回 ' + rows.length + ' 行、有效 0 行' +
        '（dividend_per_share 全为 0 且除权/派息日期全为 null）。根因：上游 akshare 分红源失效，' +
        '后端未报错而是填充 0 值。禁止据此判断『该公司不分红』；请改用 stock_intel 公告或外部源核对。',
      );
    }
    return sanitizeLossless({ mode: 'history', symbol: args.symbol, data: usable, raw_rows: rows.length });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
