import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataManagerPrompt, type DataManagerParams, type DataManagerResult } from './prompt';

export class DataManagerTool extends BaseTool<DataManagerParams, DataManagerResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_manager',
    category: 'data-manager',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = dataManagerPrompt;

  constructor(private quantsysClient: QuantsysV2Client) {
    super();
  }

  protected validate(params: DataManagerParams): ValidationResult {
    const errors: string[] = [];

    const validOperations = ['status', 'refresh', 'cleanup', 'backup'];
    if (!validOperations.includes(params.operation)) {
      errors.push(`operation 必须是 ${validOperations.join(', ')} 之一`);
    }

    if (params.data_type) {
      const validTypes = ['quote', 'kline', 'financial', 'all'];
      if (!validTypes.includes(params.data_type)) {
        errors.push(`data_type 必须是 ${validTypes.join(', ')} 之一`);
      }
    }

    if (params.symbol && !/^\d{6}$/.test(params.symbol)) {
      errors.push('symbol 必须是 6 位数字');
    }

    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (params.start_date && !dateRegex.test(params.start_date)) {
      errors.push('start_date 格式必须是 YYYY-MM-DD');
    }

    if (params.end_date && !dateRegex.test(params.end_date)) {
      errors.push('end_date 格式必须是 YYYY-MM-DD');
    }

    if (params.start_date && params.end_date) {
      if (params.start_date > params.end_date) {
        errors.push('start_date 不能晚于 end_date');
      }
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
    params: DataManagerParams,
    context: ToolContext
  ): Promise<DataManagerResult> {
    const requestParams: any = {
      operation: params.operation,
      data_type: params.data_type || 'all',
    };

    if (params.symbol) {
      requestParams.symbol = params.symbol;
    }

    if (params.start_date) {
      requestParams.start_date = params.start_date;
    }

    if (params.end_date) {
      requestParams.end_date = params.end_date;
    }

    const response = await this.quantsysClient.runQuantV2('data_manager', requestParams);

    return response as DataManagerResult;
  }

  protected wrap(data: DataManagerResult, context: ToolContext): ToolResponse<DataManagerResult> {
    const { operation, status, message } = data;

    return {
      success: status === 'success',
      data,
      message: `${operation} 操作${status === 'success' ? '成功' : '失败'}: ${message}`,
      metadata: {
        operation,
        status,
      },
    };
  }
}
