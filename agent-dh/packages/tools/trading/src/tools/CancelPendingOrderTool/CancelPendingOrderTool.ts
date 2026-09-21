/**
 * CancelPendingOrderTool - 撤销挂单工具
 *
 * 背景（2026-09-03）：002241 重复 SELL 挂单（id=18 限价版 + id=19 市价版）
 * 只能 curl 裸调 v2 cancel API 处置——工具层缺撤单能力。本工具封装
 * POST /api/simulation/accounts/{account}/pending-orders/{orderId}/cancel。
 */

import { BaseTool, ErrorType, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
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

    // 2026-09-13（用户裁定）：不做拦截——account_name 缺参时按工具层默认账户执行
    // （agent-dh = DEFAULT_AGENT_ACCOUNT = agent_brain；agent-ts 侧各自维护自己的默认值）。
    // 账户名不写死：任务/文档引用系统提示词 agent:identity 段的「本实例投资账户」。
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   *
   * 先查 pending 列表定位目标单（防误撤：单不存在/非 pending 时直接报错，
   * 不依赖后端兜底），确认后再调用 cancel，返回被撤单详情快照供审计。
   */
  protected async execute(args: CancelPendingOrderParams, _context: ToolContext): Promise<CancelPendingOrderResult> {
    // TODO: 处理非200响应 - 添加错误处理或降级逻辑（404/500等），参考 pe_percentile 改进方案
    // 每个工具的业务语义不同，需要根据具体场景设计降级策略
    const account = args.account_name || DEFAULT_AGENT_ACCOUNT;

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
