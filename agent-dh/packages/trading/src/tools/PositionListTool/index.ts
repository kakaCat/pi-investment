/**
 * PositionListTool - 持仓列表工具（简单工具）
 *
 * 简单工具：validate/execute/wrap 都在 index.ts 中实现
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { positionListPrompt, PositionListParams, PositionListResult } from './prompt';

export { positionListPrompt } from './prompt';
export type { PositionListParams, PositionListResult, PositionItem } from './prompt';

/**
 * 持仓列表工具类
 */
class PositionListTool extends BaseTool<PositionListParams, PositionListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'position_list',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = positionListPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: PositionListParams): ValidationResult {
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
  protected async execute(args: PositionListParams, context: ToolContext): Promise<PositionListResult> {
    const accountName = args.account_name || 'agent_virtual';
    const result = await this.qv2.getPositions(accountName);
    return result as unknown as PositionListResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: PositionListResult, context: ToolContext): ToolResponse<PositionListResult> {
    // 检查是否为数组
    if (!Array.isArray(result)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'result',
          issue: '返回数据必须是数组',
          received: typeof result,
          expected: 'array',
        },
      };
    }

    // 空数组是合法的（无持仓）
    if (result.length === 0) {
      return {
        success: true,
        data: result,
      };
    }

    // 检查每个持仓项的必需字段
    const requiredFields = [
      'symbol',
      'name',
      'quantity',
      'shares_available',
      'cost_price',
      'current_price',
      'market_value',
      'pnl',
      'pnl_pct',
    ];

    for (let i = 0; i < result.length; i++) {
      const item = result[i];

      for (const field of requiredFields) {
        if (item[field as keyof typeof item] === undefined) {
          return {
            success: false,
            error: {
              success: false,
              errorType: ErrorType.OUTPUT_ERROR,
              field: `[${i}].${field}`,
              issue: `持仓项缺少必需字段 ${field}`,
              expected: `包含所有必需字段: ${requiredFields.join(', ')}`,
            },
          };
        }
      }

      // 检查 symbol 格式（6位数字）
      if (!/^\d{6}$/.test(item.symbol)) {
        return {
          success: false,
          error: {
            success: false,
            errorType: ErrorType.OUTPUT_ERROR,
            field: `[${i}].symbol`,
            issue: 'symbol 必须是6位数字',
            received: item.symbol,
            expected: '6位数字',
            example: '600519',
          },
        };
      }
    }

    return {
      success: true,
      data: result,
    };
  }
}

/**
 * 创建 DSH 工具
 */
export function createPositionListTool(qv2: QuantsysV2Client) {
  const tool = new PositionListTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
