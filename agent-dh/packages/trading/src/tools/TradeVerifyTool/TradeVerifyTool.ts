/**
 * TradeVerifyTool - 交易对账工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { tradeVerifyPrompt, TradeVerifyParams, TradeVerifyResult } from './prompt';

/**
 * 交易对账工具类
 */
export class TradeVerifyTool extends BaseTool<TradeVerifyParams, TradeVerifyResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'trade_verify',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = tradeVerifyPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: TradeVerifyParams): ValidationResult {
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

    // date 可选，但如果提供必须符合格式 YYYY-MM-DD
    if (args.date !== undefined && args.date !== null) {
      if (typeof args.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(args.date)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'date',
          issue: 'date 必须是 YYYY-MM-DD 格式',
          received: args.date,
          expected: 'YYYY-MM-DD',
          example: '2026-08-28',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: TradeVerifyParams, _context: ToolContext): Promise<TradeVerifyResult> {
    // 2026-09-01 E-2 正规化：后端 /api/risk/trade-verify 已重建（服务端权威对账，
    // 逻辑与本地版一致：重复成交/字段缺失/非法值/持仓勾稽+迁移缺腿降级）。
    // 本地替代实现（2026-08-23 起的 performLocalVerify）已退役。
    const raw: any = await this.qv2.verifyTrades({
      account_name: args.account_name || 'agent_virtual',
      ...(args.date ? { date: args.date } : {}),
    });

    // 后端 api_response 统一 camelCase 转换（total_orders→totalOrders），
    // 工具契约为 snake_case——归一键名
    return {
      date: raw.date,
      total_orders: raw.totalOrders ?? raw.total_orders ?? 0,
      matched: raw.matched ?? 0,
      mismatched: raw.mismatched ?? 0,
      anomalies: Array.isArray(raw.anomalies) ? raw.anomalies : [],
      ...(Array.isArray(raw.history_gaps ?? raw.historyGaps)
        ? { history_gaps: raw.history_gaps ?? raw.historyGaps }
        : {}),
      note: raw.note,
    } as TradeVerifyResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: TradeVerifyResult, _context: ToolContext): ToolResponse<TradeVerifyResult> {
    // 检查必需字段
    const requiredFields = ['date', 'total_orders', 'matched', 'mismatched', 'anomalies'];
    const missingFields: string[] = [];

    for (const field of requiredFields) {
      if (result[field as keyof TradeVerifyResult] === undefined) {
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

    // 检查 anomalies 必须是数组
    if (!Array.isArray(result.anomalies)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          field: 'anomalies',
          issue: 'anomalies 必须是数组',
          received: typeof result.anomalies,
          expected: 'array',
        },
      };
    }

    return {
      success: true,
      data: result,
    };
  }
}
