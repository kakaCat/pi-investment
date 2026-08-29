/**
 * DataFetchKlineTool - 获取股票K线数据工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchKlinePrompt, DataFetchKlineParams, DataFetchKlineResult } from './prompt';

export class DataFetchKlineTool extends BaseTool<DataFetchKlineParams, DataFetchKlineResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_kline',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = dataFetchKlinePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchKlineParams): ValidationResult {
    // 1. symbol 必填且格式校验
    if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位纯数字',
        received: args.symbol,
        expected: '6位数字（例如 600519）',
        example: '600519',
      };
    }

    // 2. start_date 必填且格式校验
    if (!args.start_date || !/^\d{4}-\d{2}-\d{2}$/.test(args.start_date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'start_date',
        issue: 'start_date 必须是 YYYY-MM-DD 格式',
        received: args.start_date,
        expected: 'YYYY-MM-DD',
        example: '2024-01-01',
      };
    }

    // 3. end_date 必填且格式校验
    if (!args.end_date || !/^\d{4}-\d{2}-\d{2}$/.test(args.end_date)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'end_date',
        issue: 'end_date 必须是 YYYY-MM-DD 格式',
        received: args.end_date,
        expected: 'YYYY-MM-DD',
        example: '2024-12-31',
      };
    }

    // 4. 日期范围校验
    const startDate = new Date(args.start_date);
    const endDate = new Date(args.end_date);
    if (startDate > endDate) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'start_date',
        issue: 'start_date 不能晚于 end_date',
        received: `${args.start_date} > ${args.end_date}`,
        expected: 'start_date <= end_date',
        guide: '请确保开始日期早于或等于结束日期',
      };
    }

    // 5. period 校验（可选）
    if (args.period !== undefined) {
      const validPeriods = ['daily', 'weekly', 'monthly'];
      if (!validPeriods.includes(args.period)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'period',
          issue: 'period 必须是 daily/weekly/monthly 之一',
          received: args.period,
          expected: 'daily | weekly | monthly',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: DataFetchKlineParams,
    context: ToolContext
  ): Promise<DataFetchKlineResult> {
    const period = args.period || 'daily';
    const result = await this.qv2.getKlines(
      args.symbol,
      args.start_date,
      args.end_date,
      period
    );
    return result as DataFetchKlineResult;
  }

  protected wrap(data: DataFetchKlineResult): ToolResponse<DataFetchKlineResult> {
    // K线数据应该是数组
    if (!Array.isArray(data)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'result',
          issue: '返回数据不是数组',
          expected: 'Array<KlineData>',
        },
      };
    }

    return {
      success: true,
      data,
    };
  }
}
