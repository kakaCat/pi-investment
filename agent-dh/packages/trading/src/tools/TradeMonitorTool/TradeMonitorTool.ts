/**
 * TradeMonitorTool - 交易监控工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { tradeMonitorPrompt, TradeMonitorParams, TradeMonitorResult } from './prompt';

/**
 * 交易监控工具类
 */
export class TradeMonitorTool extends BaseTool<TradeMonitorParams, TradeMonitorResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'trade_monitor',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = tradeMonitorPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: TradeMonitorParams): ValidationResult {
    // account_name 可选，但如果提供必须是字符串
    if (args.account_name !== undefined && args.account_name !== null) {
      if (typeof args.account_name !== 'string' || args.account_name.trim() === '') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'account_name',
          issue: 'account_name 必须是非空字符串',
          received: args.account_name,
          expected: 'string',
          example: 'agent_virtual',
        };
      }
    }

    // order_id 可选，但如果提供必须是字符串
    if (args.order_id !== undefined && args.order_id !== null) {
      if (typeof args.order_id !== 'string' || args.order_id.trim() === '') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'order_id',
          issue: 'order_id 必须是非空字符串',
          received: args.order_id,
          expected: 'string',
          example: 'ORD-20260828-001',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: TradeMonitorParams, _context: ToolContext): Promise<TradeMonitorResult> {
    const account = args.account_name || 'agent_virtual';
    const result = await this.qv2.getTradeHistory({
      account_name: account,
      order_id: args.order_id,
    });

    // 2026-09-01：附带盘前挂单列表（execute_at='market_open' 的 pending 单）
    let pendingOrders: any[] = [];
    try {
      pendingOrders = await this.qv2.listPendingOrders(account, 'pending');
    } catch { /* 挂单查询失败不阻塞主流程 */ }

    // 转换驼峰命名为下划线命名以匹配工具的输出格式
    return {
      orders: result.orders || [],
      pending_count: result.pendingCount || 0,
      filled_count: result.filledCount || 0,
      pending_orders: pendingOrders,
    } as unknown as TradeMonitorResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: TradeMonitorResult, _context: ToolContext): ToolResponse<TradeMonitorResult> {
    // 检查必需字段
    if (!result.orders || !Array.isArray(result.orders)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'orders',
          issue: 'orders 必须是数组',
          expected: 'array',
        },
      };
    }

    if (typeof result.pending_count !== 'number' || typeof result.filled_count !== 'number') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'pending_count/filled_count',
          issue: 'pending_count 和 filled_count 必须是数字',
          expected: 'number',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
