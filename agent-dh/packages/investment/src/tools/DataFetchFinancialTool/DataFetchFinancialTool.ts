/**
 * DataFetchFinancialTool - 获取股票财务数据工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchFinancialPrompt, DataFetchFinancialParams, DataFetchFinancialResult } from './prompt';

export class DataFetchFinancialTool extends BaseTool<DataFetchFinancialParams, DataFetchFinancialResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_financial',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = dataFetchFinancialPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchFinancialParams): ValidationResult {
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
    return { success: true };
  }

  protected async execute(
    args: DataFetchFinancialParams,
    context: ToolContext
  ): Promise<DataFetchFinancialResult> {
    const result = await this.qv2.getFinancialData(args.symbol);
    return result as DataFetchFinancialResult;
  }

  protected wrap(data: DataFetchFinancialResult): ToolResponse<DataFetchFinancialResult> {
    return { success: true, data };
  }
}
