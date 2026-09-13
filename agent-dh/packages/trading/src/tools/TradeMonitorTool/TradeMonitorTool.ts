/**
 * TradeMonitorTool - 交易监控工具
 */

import { BaseTool, ErrorType, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
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
          example: 'agent_brain',
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
    const account = args.account_name || DEFAULT_AGENT_ACCOUNT;
    const result = await this.qv2.getTradeHistory({
      account_name: account,
      order_id: args.order_id,
    });

    // 2026-09-01：查询盘前挂单（execute_at='market_open' 的排队单）
    // 2026-09-13（w-a9ec14d7）按用户裁定调整输出口径：
    //   · queued_count **恒返回** —— 判断「我挂上了吗」只能看它；
    //   · pending_count 来自历史订单接口，语义是「历史订单里 pending 的笔数」，
    //     **不含盘前挂单**（实测常为 0），极易被误读成「没有挂单」（我本人就踩过）；
    //     故默认不返回，只在 include_pending=true 时连同明细一起给出；
    //   · 明细（含很长的 reason）默认不返回，避免输出膨胀。
    let pendingOrders: any[] = [];
    try {
      pendingOrders = await this.qv2.listPendingOrders(account, 'pending');
    } catch { /* 挂单查询失败不阻塞主流程；queued_count 会如实反映未取到 */ }

    const includePending = args.include_pending === true;
    const out: any = {
      orders: result.orders || [],
      filled_count: result.filledCount || 0,
      queued_count: pendingOrders.length,
    };
    if (includePending) {
      out.pending_count = result.pendingCount || 0;
      out.pending_orders = pendingOrders;
    }
    return out as unknown as TradeMonitorResult;
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

    // 2026-09-13：queued_count 恒返回且必须为数字；pending_count 改为可选（默认不返回）。
    if (typeof result.queued_count !== 'number' || typeof result.filled_count !== 'number') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'queued_count/filled_count',
          issue: 'queued_count 和 filled_count 必须是数字',
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
