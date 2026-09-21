import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { klineDailySyncPrompt, type KlineDailySyncParams, type KlineDailySyncResult } from './prompt';

export class KlineDailySyncTool extends BaseTool<KlineDailySyncParams, KlineDailySyncResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'kline_daily_sync',
    category: 'data-manager',
    version: '1.0.0',
    timeoutMs: 300000, // 5分钟，全市场同步需要较长时间
  };

  protected readonly prompt = klineDailySyncPrompt;

  constructor(private quantsysClient: QuantsysV2Client) {
    super();
  }

  protected validate(params: KlineDailySyncParams): ValidationResult {
    const errors: string[] = [];

    if (params.date) {
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (!dateRegex.test(params.date)) {
        errors.push('date 格式必须是 YYYY-MM-DD');
      }
    }

    if (params.symbols) {
      if (!Array.isArray(params.symbols)) {
        errors.push('symbols 必须是数组');
      } else if (params.symbols.length === 0) {
        errors.push('symbols 不能为空数组');
      } else {
        const invalidSymbols = params.symbols.filter(s => !/^\d{6}$/.test(s));
        if (invalidSymbols.length > 0) {
          errors.push(`以下股票代码格式错误（必须是6位数字）: ${invalidSymbols.join(', ')}`);
        }
      }
    }

    if (params.force !== undefined && typeof params.force !== 'boolean') {
      errors.push('force 必须是布尔值');
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: KlineDailySyncParams,
    context: ToolContext
  ): Promise<KlineDailySyncResult> {
    const requestParams: any = {};

    if (params.date) {
      requestParams.date = params.date;
    }

    if (params.symbols) {
      requestParams.symbols = params.symbols;
    }

    if (params.force !== undefined) {
      requestParams.force = params.force;
    }

    const response = await this.quantsysClient.syncDailyKlines(requestParams);

    // 2026-08-30 修复：部分/全部失败时抛带明细的错误，避免 DSH 层吞成笼统的「工具执行失败」，
    // 让 Agent 知道具体哪些标的失败及后端提示。
    if (response && Number(response.failed_count) > 0) {
      const failed = Array.isArray(response.failed_symbols)
        ? response.failed_symbols.slice(0, 5).join(', ')
        : '';
      throw new Error(
        'K线同步未完全成功（' +
          (response.sync_date ?? '') +
          '）: ' +
          String(response.success_count ?? 0) +
          '/' +
          String(response.total_stocks ?? response.total_symbols ?? 0) +
          ' 成功，' +
          String(response.failed_count) +
          ' 失败' +
          (failed ? '（失败标的: ' + failed + '）' : '') +
          (response.message ? '。' + response.message : '')
      );
    }

    // 2026-09-11 修复（REQ-342799 P3）：后端契约是 {success, sync_date, success_count, failed_count,
    // total_stocks, total_rows, elapsed_time, message, failed_symbols}，而本工具 output.schema 为
    // additionalProperties:false 且声明的是 total_symbols/duration_seconds/skipped_count ——
    // 直接透传 → DSH 输出校验报「value.success is not a declared property」，工具明明做完了事却报失败
    // （实测同步 000300 已写入成功，调用方却收到错误）。此处显式归一化到声明字段。
    return {
      sync_date: String(response?.sync_date ?? requestParams.date ?? ''),
      total_symbols: Number(response?.total_stocks ?? response?.total_symbols ?? 0),
      success_count: Number(response?.success_count ?? 0),
      failed_count: Number(response?.failed_count ?? 0),
      skipped_count: Number(response?.skipped_count ?? 0),
      failed_symbols: Array.isArray(response?.failed_symbols) ? response.failed_symbols : [],
      duration_seconds: Number(response?.elapsed_time ?? response?.duration_seconds ?? 0),
      message: String(response?.message ?? ''),
      total_rows: Number(response?.total_rows ?? 0),
      backend_success: response?.success === true,
    } as KlineDailySyncResult;
  }

  protected wrap(data: KlineDailySyncResult, context: ToolContext): ToolResponse<KlineDailySyncResult> {
    const { sync_date, total_symbols, success_count, failed_count, duration_seconds } = data;

    let message = `K线同步完成（${sync_date}）: ${success_count}/${total_symbols} 成功`;
    if (failed_count > 0) message += `, ${failed_count} 失败`;
    message += `, 耗时 ${duration_seconds}s`;

    return {
      success: failed_count === 0,
      data,
      message,
      metadata: {
        sync_date,
        total_symbols,
        success_count,
        failed_count,
        duration_seconds,
      },
    };
  }
}
