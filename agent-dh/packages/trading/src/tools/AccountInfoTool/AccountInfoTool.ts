/**
 * AccountInfoTool - 账户信息工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { accountInfoPrompt, AccountInfoParams, AccountInfoResult } from './prompt';

/**
 * 账户信息工具类
 */
export class AccountInfoTool extends BaseTool<AccountInfoParams, AccountInfoResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'account_info',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = accountInfoPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: AccountInfoParams): ValidationResult {
    // account_name 可选，但如果提供必须是字符串
    if (args.account_name !== undefined && args.account_name !== null) {
      if (typeof args.account_name !== 'string') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'account_name',
          issue: 'account_name 必须是字符串',
          received: typeof args.account_name,
          expected: 'string',
          example: 'agent_virtual',
        };
      }

      if (args.account_name.trim() === '') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'account_name',
          issue: 'account_name 不能为空字符串',
          received: '""',
          expected: '非空字符串',
          example: 'agent_virtual',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: AccountInfoParams, _context: ToolContext): Promise<AccountInfoResult> {
    const accountName = args.account_name || 'agent_virtual';
    const result = await this.qv2.getPortfolioSummary(accountName);
    return result as AccountInfoResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: AccountInfoResult, _context: ToolContext): ToolResponse<AccountInfoResult> {
    // 检查必需字段
    const requiredFields = [
      'accountName',
      'totalValue',
      'totalCost',
      'totalMarketValue',
      'totalPnl',
      'totalPnlPct',
      'dailyChange',
      'positions',
      'cash',
      'liquidAssets',
      'profitCount',
      'lossCount',
      'lastUpdated',
    ];

    const missingFields: string[] = [];
    for (const field of requiredFields) {
      if (result[field as keyof AccountInfoResult] === undefined) {
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
