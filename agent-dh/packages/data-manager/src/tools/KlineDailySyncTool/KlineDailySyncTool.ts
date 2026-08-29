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

    const response = await this.quantsysClient.runQuantV2('kline_daily_sync', requestParams);

    return response as KlineDailySyncResult;
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
