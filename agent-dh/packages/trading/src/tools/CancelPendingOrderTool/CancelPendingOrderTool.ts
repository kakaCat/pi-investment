/**
 * CancelPendingOrderTool - 撤销挂单工具
 *
 * 背景（2026-09-03）：002241 重复 SELL 挂单（id=18 限价版 + id=19 市价版）
 * 只能 curl 裸调 v2 cancel API 处置——工具层缺撤单能力。本工具封装
 * POST /api/simulation/accounts/{account}/pending-orders/{orderId}/cancel。
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { cancelPendingOrderPrompt, CancelPendingOrderParams, CancelPendingOrderResult } from './prompt';

/**
 * 撤销挂单工具类
 */
export class CancelPendingOrderTool extends BaseTool<CancelPendingOrderParams, CancelPendingOrderResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'cancel_pending_order',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = cancelPendingOrderPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: CancelPendingOrderParams): ValidationResult {
    if (args.order_id === undefined || args.order_id === null ||
        typeof args.order_id !== 'number' || !Number.isInteger(args.order_id) || args.order_id <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'order_id',
        issue: 'order_id 必须是正整数（trade_monitor 返回的 pending_orders[].id）',
        received: args.order_id,
        expected: 'positive integer',
        example: 19,
      };
    }

    // R-019（2026-09-13 w-c8cae280）：写操作必须显式指定账户。
    // agent-dh 自有账户 = agent_brain；agent_virtual 属 agent-ts（fin-agent），禁止写入。
    const acct = args.account_name;
    if (acct === undefined || acct === null || String(acct).trim() === '') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'account_name',
        issue: '写操作必须显式传 account_name（agent-dh 自有账户 = agent_brain）',
        received: acct,
        expected: "'agent_brain'",
        example: 'agent_brain',
        guide: '默认账户不再隐式作用于写操作；agent_virtual 属 agent-ts，禁止写入',
      };
    }
    if (String(acct).trim() === 'agent_virtual') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'account_name',
        issue: 'agent_virtual 属 agent-ts（fin-agent），agent-dh 禁止对其写入',
        received: acct,
        expected: "'agent_brain'",
        example: 'agent_brain',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   *
   * 先查 pending 列表定位目标单（防误撤：单不存在/非 pending 时直接报错，
   * 不依赖后端兜底），确认后再调用 cancel，返回被撤单详情快照供审计。
   */
  protected async execute(args: CancelPendingOrderParams, _context: ToolContext): Promise<CancelPendingOrderResult> {
    const account = args.account_name || 'agent_brain';

    // 前置确认：目标单必须存在且处于 pending
    const pending = await this.qv2.listPendingOrders(account, 'pending');
    const target = (pending || []).find((o: any) => Number(o?.id) === args.order_id);
    if (!target) {
      throw new Error(
        `挂单 id=${args.order_id} 不在账户 ${account} 的 pending 列表中（可能已成交/已撤/过期）。` +
        `当前 pending 挂单：${(pending || []).map((o: any) => `id=${o.id} ${o.symbol} ${o.action} ${o.shares}股`).join('；') || '无'}`,
      );
    }

    const result = await this.qv2.cancelPendingOrder(account, args.order_id);

    return {
      status: result?.status ?? 'cancelled',
      pending_order_id: result?.pending_order_id ?? args.order_id,
      cancelled_order: {
        symbol: target.symbol,
        action: target.action,
        shares: target.shares,
        price_limit: target.price_limit ?? null,
        reason: args.reason ?? undefined,
      },
    } as unknown as CancelPendingOrderResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: CancelPendingOrderResult, _context: ToolContext): ToolResponse<CancelPendingOrderResult> {
    if (result.status !== 'cancelled') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'status',
          issue: `撤单结果异常：status=${result.status}`,
          expected: 'cancelled',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
