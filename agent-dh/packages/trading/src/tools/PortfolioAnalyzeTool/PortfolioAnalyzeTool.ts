/**
 * PortfolioAnalyzeTool - 持仓健康一键分析
 *
 * 数据契约（2026-09-02 实测 /api/simulation/accounts/{account} 经 client.mapPosition）：
 * Position: { symbol, name, quantity, sharesAvailable, avgCost, currentPrice,
 *             profitLossPct（百分数，0.73=+0.73%；client.mapPosition 已把后端 profit_total_rate 小数 ×100）, priceStale? }
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { portfolioAnalyzePrompt, PortfolioAnalyzeParams } from './prompt';

// 止损线口径（与宪法/agent 惯例一致）：主板蓝筹 -8%、创业板/科创 -10%
const STOP_LOSS_MAIN = -8;
const STOP_LOSS_GROWTH = -10;
// 止盈参考线（v13 机械止盈惯例）
const TAKE_PROFIT = 10;

type Advice = 'stop_loss' | 'take_profit' | 'review' | 'wait_t1' | 'hold';

export class PortfolioAnalyzeTool extends BaseTool<PortfolioAnalyzeParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'portfolio_analyze',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = portfolioAnalyzePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(_args: PortfolioAnalyzeParams): ValidationResult {
    return { success: true };
  }

  private stopLossLine(symbol: string): number {
    return /^(30|68)/.test(symbol) ? STOP_LOSS_GROWTH : STOP_LOSS_MAIN;
  }

  private adviceFor(pnlPct: number, stopLine: number): { advice: Advice; priority: number; reason: string } {
    if (pnlPct <= stopLine) {
      return { advice: 'stop_loss', priority: 1, reason: `浮亏 ${pnlPct.toFixed(1)}% 触及止损线 ${stopLine}%（铁律：必须卖出）` };
    }
    if (pnlPct <= stopLine + 2) {
      return { advice: 'review', priority: 2, reason: `浮亏 ${pnlPct.toFixed(1)}% 距止损线 ${stopLine}% 不足 2 个点，评估逻辑是否还成立` };
    }
    if (pnlPct >= TAKE_PROFIT) {
      return { advice: 'take_profit', priority: 1, reason: `浮盈 +${pnlPct.toFixed(1)}% 达止盈线 +${TAKE_PROFIT}%（机械止盈纪律）` };
    }
    if (pnlPct < 0) {
      return { advice: 'review', priority: 3, reason: `浮亏 ${pnlPct.toFixed(1)}% 未触线，检查买入逻辑` };
    }
    return { advice: 'hold', priority: 4, reason: `浮盈 +${pnlPct.toFixed(1)}% 正常持有` };
  }

  protected async execute(args: PortfolioAnalyzeParams, _context: ToolContext): Promise<any> {
    const account = args.account_name || 'agent_virtual';
    const [positions, summary] = await Promise.all([
      this.qv2.getPositions(account),
      this.qv2.getPortfolioSummary(account),
    ]);

    const analyzed = (positions || []).map((p: any) => {
      // profitLossPct 契约：百分数（0.73 = +0.73%）。2026-09-04 修复：删除 ×100 启发式——
      // 该启发式把真实小百分比（如 +0.73%）错乘成 73% 造成假止盈信号（与 PositionListTool 口径对齐）
      const pnlPct = Number(p.profitLossPct ?? 0);
      const priceStale = p.priceStale === true;

      let advice: Advice;
      let priority: number;
      let reason: string;
      if (priceStale) {
        advice = 'review';
        priority = 2;
        reason = '行情陈旧（price_stale），价格不可信，不给止损/止盈结论，先刷新行情';
      } else if (Number(p.sharesAvailable ?? 0) <= 0) {
        advice = 'wait_t1';
        priority = 3;
        reason = '今日买入，T+1 限制明日才可卖';
      } else {
        const r = this.adviceFor(pnlPct, this.stopLossLine(p.symbol));
        advice = r.advice; priority = r.priority; reason = r.reason;
      }

      return {
        symbol: p.symbol,
        name: p.name,
        quantity: p.quantity,
        shares_available: p.sharesAvailable,
        avg_cost: p.avgCost,
        current_price: p.currentPrice,
        pnl_pct: Math.round(pnlPct * 100) / 100,
        stop_loss_line: this.stopLossLine(p.symbol),
        price_stale: priceStale || undefined,
        advice,
        priority,
        reason,
      };
    });

    analyzed.sort((a, b) => a.priority - b.priority || a.pnl_pct - b.pnl_pct);
    const urgent = analyzed.filter((p) => p.priority === 1);
    const winners = analyzed.filter((p) => p.pnl_pct > 0).length;
    const losers = analyzed.filter((p) => p.pnl_pct < 0).length;

    return sanitizeLossless({
      account,
      position_count: analyzed.length,
      urgent,
      positions: analyzed,
      health: {
        total_value: (summary as any)?.totalValue,
        total_pnl_pct: (summary as any)?.totalPnlPct,
        position_pct: (summary as any)?.totalValue > 0
          ? Math.round(((summary as any).totalMarketValue / (summary as any).totalValue) * 1000) / 10
          : null,
        winners,
        losers,
        win_loss_ratio: losers > 0 ? Math.round((winners / losers) * 100) / 100 : (winners > 0 ? Infinity : null),
      },
      summary: urgent.length > 0
        ? `⚠️ ${urgent.length} 只持仓需立即处理：${urgent.map((p) => `${p.symbol}(${p.advice})`).join('、')}`
        : '✅ 无触发止损/止盈的持仓',
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data, message: data.summary };
  }
}
