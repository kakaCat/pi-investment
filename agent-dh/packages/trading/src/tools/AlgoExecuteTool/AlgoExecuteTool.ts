/**
 * AlgoExecuteTool - 算法交易工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { algoExecutePrompt, AlgoExecuteParams, AlgoExecuteResult } from './prompt';

/**
 * 算法交易工具类
 */
export class AlgoExecuteTool extends BaseTool<AlgoExecuteParams, AlgoExecuteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'algo_execute',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = algoExecutePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: AlgoExecuteParams): ValidationResult {
    // 1. 检查 action
    if (!args.action) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 是必填参数',
        expected: 'BUY 或 SELL',
        example: 'BUY',
      };
    }

    if (!['BUY', 'SELL'].includes(args.action)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 必须是 BUY 或 SELL',
        received: args.action,
        expected: 'BUY 或 SELL',
        example: 'BUY',
      };
    }

    // 2. 检查 symbol
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 是必填参数',
        expected: '6位数字股票代码',
        example: '600519',
      };
    }

    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: args.symbol,
        expected: '6位数字',
        example: '600519',
      };
    }

    // 3. 检查 quantity
    if (!args.quantity) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 是必填参数',
        expected: '正整数',
        example: '1000',
      };
    }

    if (!Number.isInteger(args.quantity) || args.quantity <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'quantity',
        issue: 'quantity 必须是正整数',
        received: String(args.quantity),
        expected: '正整数',
        example: '1000',
      };
    }

    // 4. 检查 algo（可选）
    if (args.algo !== undefined && args.algo !== null) {
      if (!['TWAP', 'VWAP'].includes(args.algo)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'algo',
          issue: 'algo 必须是 TWAP 或 VWAP',
          received: args.algo,
          expected: 'TWAP 或 VWAP',
          example: 'TWAP',
        };
      }
    }

    // 5. 检查 duration（可选）
    if (args.duration !== undefined && args.duration !== null) {
      if (!Number.isInteger(args.duration) || args.duration <= 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'duration',
          issue: 'duration 必须是正整数',
          received: String(args.duration),
          expected: '正整数（分钟）',
          example: '30',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: AlgoExecuteParams, _context: ToolContext): Promise<AlgoExecuteResult> {
    // 交易时段检查（需要从 trading/src/utils/trading-hours.ts 导入）
    // assertTradingHours();

    const result = await this.qv2.executeAlgo({
      action: args.action.toLowerCase() as 'buy' | 'sell',
      symbol: args.symbol,
      quantity: args.quantity,
      algo: args.algo || 'TWAP',
      duration: args.duration || 30,
      account_name: args.account_name || 'agent_virtual',
    });
    return result as unknown as AlgoExecuteResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: AlgoExecuteResult, _context: ToolContext): ToolResponse<AlgoExecuteResult> {
    // 检查必需字段
    const requiredFields = ['algo_order_id', 'symbol', 'total_quantity', 'status'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if (result[field as keyof AlgoExecuteResult] === undefined) {
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
          issue: `返回数据缺少必需字段`,
          expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
