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
    // 2026-08-23 重写：后端 /api/risk/trade-verify 路由在重构中丢失（404），
    // 改为本地对账（拉成交记录自查异常），不再依赖后端路由
    const result = await this.performLocalVerify(
      args.account_name || 'agent_virtual',
      args.date
    );
    return result as TradeVerifyResult;
  }

  /**
   * 本地对账业务逻辑
   * 2026-08-23: 后端 trade-verify 路由 404 丢失后的替代实现
   */
  private async performLocalVerify(accountName: string, date?: string): Promise<any> {
    const targetDate = date || new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
    const anomalies: any[] = [];

    // 1. 拉取成交记录（全量：pageSize 500，避免分页截断导致勾稽误报）
    const th: any = await this.qv2.getTradeHistory({ account_name: accountName, pageSize: 500 });
    // orders/items 双兼容（后端实际返回 items）
    const allTrades: any[] = th?.orders || th?.items || [];
    const dayTrades = allTrades.filter((t: any) => String(t.tradeDate ?? t.trade_date ?? '') === targetDate);

    // 2. 重复成交检测（同标的+同方向+同价+同量+同分钟）
    const seen = new Map<string, number>();
    for (const t of dayTrades) {
      const key = [t.symbol, t.action, t.price, t.quantity, String(t.createdAt ?? '').slice(0, 16)].join('|');
      const cnt = (seen.get(key) ?? 0) + 1;
      seen.set(key, cnt);
      if (cnt > 1) {
        anomalies.push({ type: 'duplicate_trade', detail: `疑似重复成交: ${t.symbol} ${t.action} ${t.quantity}股@${t.price}（第${cnt}次）`, trade_id: t.id ?? null });
      }
    }

    // 3. 关键字段缺失
    for (const t of dayTrades) {
      const missing = ['symbol', 'action', 'price', 'quantity'].filter(f => t[f] === undefined || t[f] === null);
      if (missing.length > 0) {
        anomalies.push({ type: 'missing_fields', detail: `成交记录缺字段 ${missing.join('/')}: id=${t.id ?? '?'}` , trade_id: t.id ?? null });
      }
      if (!(Number(t.price) > 0) || !(Number(t.quantity) > 0)) {
        anomalies.push({ type: 'invalid_value', detail: `成交价格/数量非法: ${t.symbol} @${t.price} x${t.quantity}`, trade_id: t.id ?? null });
      }
    }

    // 4. 持仓勾稽（全量历史：逐标的 买入-卖出 = 当前持仓）
    // 2026-08-23 验收修正：历史迁移缺买入腿的记录不算异常——
    // 只有"当前有持仓但与成交净额不符"才算真异常；net<0 或 held=0 的不符降级为 history_gap 提示
    const positions: any[] = await this.qv2.getPositions(accountName).catch(() => [] as any[]);
    const posMap = new Map<string, number>();
    for (const p of positions) {
      const sym = String(p.symbol ?? '').replace(/\.\w+$/, '');
      posMap.set(sym, Number(p.quantity ?? p.shares ?? 0));
    }
    const netMap = new Map<string, number>();
    for (const t of allTrades) {
      const sym = String(t.symbol ?? '').replace(/\.\w+$/, '');
      const q = Number(t.quantity ?? 0);
      const dir = String(t.action).toLowerCase() === 'buy' ? q : -q;
      netMap.set(sym, (netMap.get(sym) ?? 0) + dir);
    }
    const historyGaps: any[] = [];
    // 2026-08-25 修正：可见历史无买入记录的标的（迁移持仓缺买入腿），净额为负也降级为缺腿提示，
    // 否则熔断减仓日会把"只有卖出记录"误判为勾稽异常
    const hasBuy = new Set<string>();
    for (const t of allTrades) {
      if (String(t.action).toLowerCase() === 'buy') {
        hasBuy.add(String(t.symbol ?? '').replace(/\.\w+$/, ''));
      }
    }
    for (const [sym, net] of netMap) {
      const held = posMap.get(sym) ?? 0;
      if (held > 0 && held !== net && Math.abs(held - net) >= 100) {
        if (!hasBuy.has(sym)) {
          historyGaps.push({ symbol: sym, net_trades: net, note: '迁移持仓（可见历史无买入腿），不参与勾稽' });
        } else {
          anomalies.push({ type: 'position_mismatch', detail: `持仓勾稽不符 ${sym}: 账面 ${held} vs 成交净额 ${net}`, symbol: sym });
        }
      } else if (held === 0 && net !== 0) {
        historyGaps.push({ symbol: sym, net_trades: net, note: '历史迁移缺腿（买入/卖出记录不全），不参与勾稽' });
      }
    }

    const result: any = {
      date: targetDate,
      total_orders: dayTrades.length,
      matched: dayTrades.length - anomalies.filter(a => a.type === 'duplicate_trade' || a.type === 'missing_fields' || a.type === 'invalid_value').length,
      mismatched: anomalies.length,
      anomalies,
      note: '本地对账（后端 trade-verify 路由 404 丢失后的替代实现，2026-08-23）',
    };
    if (historyGaps.length > 0) result.history_gaps = historyGaps;  // undefined 字段会触发 not lossless JSON，按需拼装
    return result;
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
