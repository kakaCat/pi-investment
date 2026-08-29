/**
 * DataFetchQuoteTool - 获取股票实时行情工具（简单工具）
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchQuotePrompt, DataFetchQuoteParams, DataFetchQuoteResult } from './prompt';

export class DataFetchQuoteTool extends BaseTool<DataFetchQuoteParams, DataFetchQuoteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_quote',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = dataFetchQuotePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: DataFetchQuoteParams): ValidationResult {
    // 1. symbol 必填
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: '缺少必填字段 symbol',
        expected: '6位数字股票代码',
        example: '600519',
        guide: '请提供A股6位数字代码，如 600519（贵州茅台）',
      };
    }

    // 2. symbol 必须是字符串
    if (typeof args.symbol !== 'string') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是字符串',
        received: typeof args.symbol,
        expected: 'string',
        guide: '请提供字符串格式的股票代码',
      };
    }

    // 3. symbol 格式校验（6位数字）
    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位纯数字',
        received: args.symbol,
        expected: '6位数字（例如 600519）',
        example: '600519',
        guide: '不要带 SH/SZ 前缀，不要带 .XSHG 后缀',
      };
    }

    // 4. source 校验（可选）
    if (args.source !== undefined) {
      const validSources = ['auto', 'realtime', 'db'];
      if (!validSources.includes(args.source)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'source',
          issue: 'source 必须是 auto/realtime/db 之一',
          received: args.source,
          expected: 'auto | realtime | db',
          guide: 'auto: 自动选择；realtime: 强制实时；db: 数据库缓存',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: DataFetchQuoteParams,
    context: ToolContext
  ): Promise<DataFetchQuoteResult> {
    const source = args.source || 'auto';
    const result = await this.qv2.getQuote(args.symbol, source);
    return result as DataFetchQuoteResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(data: DataFetchQuoteResult): ToolResponse<DataFetchQuoteResult> {
    // 检查必需字段
    const requiredFields = [
      'symbol',
      'name',
      'price',
      'open',
      'high',
      'low',
      'prevClose',
      'change',
      'changePct',
      'volume',
      'amount',
      'timestamp',
    ];

    const missingFields: string[] = [];
    for (const field of requiredFields) {
      if (data[field as keyof DataFetchQuoteResult] === undefined) {
        missingFields.push(field);
      }
    }

    if (missingFields.length > 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: missingFields.join(', '),
          issue: `返回数据缺少必需字段: ${missingFields.join(', ')}`,
          expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
        },
      };
    }

    return {
      success: true,
      data,
    };
  }
}
