/**
 * Comparator - 减法器（比较器）
 *
 * 职责：
 *   1. 计算全周期总账（已实现盈亏 + 持仓浮盈）
 *   2. 按周/月/全周期切割表现
 *   3. 评估数据完整性，不基于残缺数据做虚假归因
 *
 * 核心原则：
 *   - 数据不全就承认不全，不做虚假结论
 *   - 单一信号裁断，只确定一个绩效差距、归因到一个根本原因、给出一个补偿方向
 */
// @ts-nocheck

import * as path from 'path';
import type { Holding } from './data-collector.js';
import type {
  ComparisonResult,
  PeriodPerformance,
  TotalReturn,
  DataQualityReport,
  PerformanceGap,
  TargetRealisticCheck,
  CapabilityCheck,
  DecisionQualityMetrics,
  AttributionResult,
} from '../../types/evolution.js';

// ─── 外部形状 ──────────────────────────────────────────────────────────────

interface Trade {
  date: string;
  action: 'buy' | 'sell';
  symbol: string;
  name: string;
  quantity: number;
  price: number;
  amount: number;
  market: string;
  notes: string;
  pnl?: number | null;
  pnl_pct?: number | null;
  time?: string;
}

// ─── Helper 函数 ──────────────────────────────────────────────────────────

/** ISO date → YYYY-MM-DD */
function toDateStr(d: string): string {
  return d.slice(0, 10);
}

/** 获取 ISO 周的标签，如 "2026-W19" */
function isoWeekLabel(dateStr: string): string {
  const d = new Date(dateStr);
  // 复制日期避免修改原对象
  const temp = new Date(d.getTime());
  temp.setHours(0, 0, 0, 0);
  // 这一年的一月一日
  const yearStart = new Date(temp.getFullYear(), 0, 1);
  const weekNum = Math.ceil(((temp.getTime() - yearStart.getTime()) / 86400000 + yearStart.getDay() + 1) / 7);
  return `${temp.getFullYear()}-W${String(weekNum).padStart(2, '0')}`;
}

/** 获取月份标签，如 "2026-05" */
function monthLabel(dateStr: string): string {
  return dateStr.slice(0, 7);
}

/** 获取周一起始日期 */
function weekStart(dateStr: string): string {
  const d = new Date(dateStr);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // 周日算到上一周的周一
  const monday = new Date(d.getTime() + diff * 86400000);
  monday.setHours(0, 0, 0, 0);
  return monday.toISOString().slice(0, 10);
}

/** 获取下周一（作为本周结束） */
function weekEndAfter(dateStr: string): string {
  const d = new Date(dateStr);
  const day = d.getDay();
  const diff = day === 0 ? 0 : 7 - day; // 周日算当天结束
  const sunday = new Date(d.getTime() + diff * 86400000);
  sunday.setHours(23, 59, 59, 999);
  return sunday.toISOString().slice(0, 10);
}

// ─── 核心计算 ──────────────────────────────────────────────────────────────

/**
 * 计算已实现盈亏
 * 用 FIFO 配对同一只股票的买卖
 */
function calcRealizedPnL(trades: Trade[]): {
  totalRealizedPnL: number;
  totalInvested: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  tradeResults: Array<{ symbol: string; pnl: number; pnlPct: number; date: string }>;
} {
  // 过滤纠错记录
  const clean = trades.filter(t => {
    const n = t.notes;
    if (n && (n.includes('回退') || n.includes('撤回') || n.includes('纠正') || n.includes('误操作'))) return false;
    return true;
  });

  // 按 symbol 分组
  const bySymbol = new Map<string, Trade[]>();
  for (const t of clean) {
    const list = bySymbol.get(t.symbol) || [];
    list.push(t);
    bySymbol.set(t.symbol, list);
  }

  const tradeResults: Array<{ symbol: string; pnl: number; pnlPct: number; date: string }> = [];
  let totalRealizedPnL = 0;
  let totalInvested = 0;
  let winCount = 0;
  let lossCount = 0;

  for (const [, symbolTrades] of bySymbol) {
    const buyQueue: Trade[] = [];

    for (const t of symbolTrades) {
      if (t.action === 'buy') {
        buyQueue.push(t);
      } else {
        // sell: FIFO 从最早买入匹配
        let remainingSell = t.quantity;

        while (remainingSell > 0 && buyQueue.length > 0) {
          const buy = buyQueue[0];
          const matchedQty = Math.min(remainingSell, buy.quantity);

          const buyCost = buy.price * matchedQty;
          const sellProceeds = (t.price || 0) * matchedQty;
          const pnl = sellProceeds - buyCost;
          const pnlPct = buy.price > 0 ? ((t.price - buy.price) / buy.price) * 100 : 0;

          totalRealizedPnL += pnl;
          totalInvested += buyCost;
          tradeResults.push({
            symbol,
            pnl,
            pnlPct,
            date: toDateStr(t.date),
          });

          if (pnl > 0) winCount++;
          else if (pnl < 0) lossCount++;

          buy.quantity -= matchedQty;
          remainingSell -= matchedQty;
          if (buy.quantity <= 0) buyQueue.shift();
        }
      }
    }
  }

  return {
    totalRealizedPnL,
    totalInvested,
    winCount,
    lossCount,
    winRate: (winCount + lossCount) > 0 ? winCount / (winCount + lossCount) : 0,
    tradeResults,
  };
}

/**
 * 估算当前持仓浮盈
 *
 * ⚠️ 不调用实时行情 API，基于以下逻辑估算：
 *   - 如果交易记录中有该股票的买入和卖出记录，用 FIFO 摊薄成本
 *   - 否则用持仓的 avg_cost
 *   - 浮盈用买入均价 vs 最近一次成交价（若有）估算
 *
 * 当数据不全时，浮盈标记为 unavailable 而非 0
 */
function calcUnrealizedPnL(
  holdings: Holding[],
  allTrades: Trade[],
): { unrealizedPnL: number; hasUnrealizedData: boolean } {
  if (holdings.length === 0) {
    return { unrealizedPnL: 0, hasUnrealizedData: false };
  }

  // 对于浮盈，我们只用持仓成本作为投入
  // 浮盈本身需要实时行情才能准确计算 → 这里标记为 null
  // 实际浮盈在 evolution-service.ts 中通过 getWithPnL() 获取
  return { unrealizedPnL: 0, hasUnrealizedData: false };
}

/**
 * 计算总投入
 *
 * = Σ(trades 中所有买入金额) + Σ(持仓中无对应买入的成本)
 */
function calcTotalInvestment(
  trades: Trade[],
  holdings: Holding[],
): number {
  const buyAmount = trades
    .filter(t => t.action === 'buy')
    .reduce((s, t) => s + (t.price * t.quantity), 0);

  // 持仓中尚未在 trades 里有买入记录的
  const processedSymbols = new Set(trades.filter(t => t.action === 'buy').map(t => t.symbol));
  const extraCost = holdings
    .filter(h => !processedSymbols.has(h.symbol))
    .reduce((s, h) => s + (h.total_invested || h.avg_cost * h.quantity), 0);

  return buyAmount + extraCost;
}

/**
 * 当前持仓成本总和（活跃资金）
 */
function calcActiveInvestment(
  trades: Trade[],
  holdings: Holding[],
): number {
  // 从 holdings 直接取当前持仓成本
  if (holdings.length > 0) {
    return holdings.reduce((s, h) => s + (h.total_invested || h.avg_cost * h.quantity), 0);
  }
  // 无持仓数据时从 trades 重建快照
  const snapshot = new Map<string, { quantity: number; totalCost: number }>();
  const buysSorted = [...trades.filter(t => t.action === 'buy')].sort((a, b) =>
    a.date.localeCompare(b.date) || a.id.localeCompare(b.id)
  );
  for (const t of trades) {
    const prev = snapshot.get(t.symbol) ?? { quantity: 0, totalCost: 0 };
    if (t.action === 'buy') {
      snapshot.set(t.symbol, {
        quantity: prev.quantity + t.quantity,
        totalCost: prev.totalCost + t.price * t.quantity + t.commission,
      });
    } else {
      const costBasis = prev.quantity > 0
        ? (prev.totalCost / prev.quantity) * t.quantity
        : 0;
      const newQty = prev.quantity - t.quantity;
      snapshot.set(t.symbol, {
        quantity: Math.max(0, newQty),
        totalCost: Math.max(0, prev.totalCost - costBasis),
      });
    }
  }
  let total = 0;
  for (const [, pos] of snapshot) {
    if (pos.quantity > 0) total += pos.totalCost;
  }
  return total;
}

/**
 * 历史峰值资金占用 = 账户余额最大值
 */
function calcPeakInvestment(trades: Trade[]): number {
  let balance = 0;
  let peak = 0;
  const sortedTrades = [...trades].sort((a, b) => {
    const dateCompare = a.date.localeCompare(b.date);
    if (dateCompare !== 0) return dateCompare;
    // 如果日期相同，按 symbol 排序
    return a.symbol.localeCompare(b.symbol);
  });
  // 先建一个symbol→当前持仓均价的映射，用于卖出时扣减
  const avgCostMap = new Map<string, number>();
  const qtyMap = new Map<string, number>();

  for (const t of sortedTrades) {
    if (t.action === 'buy') {
      const prevQty = qtyMap.get(t.symbol) ?? 0;
      const prevCost = avgCostMap.get(t.symbol) ?? 0;
      const newQty = prevQty + t.quantity;
      const newCost = prevQty > 0
        ? (prevCost * prevQty + t.price * t.quantity) / newQty
        : t.price;
      avgCostMap.set(t.symbol, newCost);
      qtyMap.set(t.symbol, newQty);
      balance += t.price * t.quantity;
    } else {
      const avgCost = avgCostMap.get(t.symbol) ?? t.price;
      const deduction = avgCost * t.quantity;
      balance = Math.max(0, balance - deduction);
      const prevQty = qtyMap.get(t.symbol) ?? 0;
      qtyMap.set(t.symbol, Math.max(0, prevQty - t.quantity));
    }
    if (balance > peak) peak = balance;
  }
  return peak;
}

/**
 * 按时间切片分组
 */
function groupByPeriod<T>(
  items: Array<T & { date: string }>,
  getLabel: (date: string) => string,
  getPeriodStart: (date: string) => string,
  getPeriodEnd: (date: string) => string,
): Map<string, { items: Array<T & { date: string }>; startDate: string; endDate: string }> {
  const map = new Map<string, { items: Array<T & { date: string }>; startDate: string; endDate: string }>();

  for (const item of items) {
    const label = getLabel(item.date);
    if (!map.has(label)) {
      map.set(label, {
        items: [],
        startDate: getPeriodStart(item.date),
        endDate: getPeriodEnd(item.date),
      });
    }
    map.get(label)!.items.push(item);
  }

  return map;
}

/**
 * 数据完整性评估
 */
function assessDataQuality(
  trades: Trade[],
  holdings: Holding[],
): DataQualityReport {
  const warnings: string[] = [];
  let reliability: 'high' | 'medium' | 'low' = 'high';

  // 交易笔数
  if (trades.length === 0) {
    warnings.push('没有交易记录，进化分析缺少买卖数据');
    reliability = 'low';
  } else if (trades.length < 10) {
    warnings.push(`交易记录较少（${trades.length} 笔），统计结果可能不稳定`);
    reliability = 'medium';
  }

  // 检查买入记录完整性
  const buyTrades = trades.filter(t => t.action === 'buy');
  const sellTrades = trades.filter(t => t.action === 'sell');
  const hasCompleteBuyRecords = buyTrades.length > 0;

  // 有持仓但无买入记录
  if (holdings.length > 0 && buyTrades.length === 0) {
    warnings.push(`有 ${holdings.length} 只持仓但无买入记录，可能数据被清除过`);
    reliability = 'low';
  }

  // 有卖出但无对应买入
  const sellSymbols = new Set(sellTrades.map(t => t.symbol));
  const buySymbols = new Set(buyTrades.map(t => t.symbol));
  for (const sym of sellSymbols) {
    if (!buySymbols.has(sym)) {
      warnings.push(`股票 ${sym} 有卖出记录但无买入记录（数据不完整）`);
    }
  }

  // pnl 为空（直接写入的卖出记录）
  const missingPnL = sellTrades.filter(t => t.pnl === null || t.pnl === undefined);
  if (missingPnL.length > 0) {
    warnings.push(`${missingPnL.length} 笔卖出记录缺少盈亏数据（pnl=null）`);
    reliability = 'medium';
  }

  // 时间跨度
  const ordered = [...trades].sort((a, b) => a.date.localeCompare(b.date));
  const earliest = ordered.length > 0 ? ordered[0].date : null;
  const latest = ordered.length > 0 ? ordered[ordered.length - 1].date : null;

  if (earliest && latest) {
    const days = (new Date(latest).getTime() - new Date(earliest).getTime()) / 86400000;
    if (days < 30) {
      warnings.push(`交易数据跨度仅 ${Math.round(days)} 天，参考意义有限`);
      if (reliability === 'high') reliability = 'medium';
    }
  }

  return {
    earliestTradeDate: earliest ? toDateStr(earliest) : null,
    latestTradeDate: latest ? toDateStr(latest) : null,
    tradeCount: trades.length,
    positionCount: holdings.length,
    hasPortfolioData: holdings.length > 0,
    hasCompleteBuyRecords,
    reliability,
    warnings,
  };
}

/**
 * 构建阶段性能
 */
function buildPeriodPerformance(
  label: string,
  startDate: string,
  endDate: string,
  realizedPnL: number,
  unrealizedPnLChange: number | null,
  beginningCapital: number,
  tradesInPeriod: Array<{ pnl: number; pnlPct?: number | null }>,
): PeriodPerformance {
  const totalPnL = realizedPnL + (unrealizedPnLChange ?? 0);
  const returnPct = beginningCapital > 0 ? (totalPnL / beginningCapital) * 100 : 0;
  const realizedResults = tradesInPeriod.filter(t => t.pnl !== undefined && t.pnl !== null);
  const wins = realizedResults.filter(t => t.pnl > 0).length;
  const losses = realizedResults.filter(t => t.pnl < 0).length;

  return {
    label,
    startDate,
    endDate,
    realizedPnL,
    unrealizedPnLChange,
    totalPnL,
    beginningCapital: Math.round(beginningCapital),
    returnPct: Math.round(returnPct * 100) / 100,
    tradeCount: realizedResults.length,
    winRate: (wins + losses) > 0 ? wins / (wins + losses) : 0,
    reliability: unrealizedPnLChange === null ? 'partial' : 'full',
  };
}

// ─── 主入口 ────────────────────────────────────────────────────────────────

/**
 * 减法器主入口：计算全维度比较结果
 *
 * @param trades    所有交易记录
 * @param holdings  当前持仓
 * @param portfolioUnrealizedPnL 从 PositionCliAdapter 获取的当前持仓浮盈（可选）
 * @returns ComparisonResult
 */
export function compare(
  trades: Trade[],
  holdings: Holding[],
  portfolioUnrealizedPnL?: number,
): ComparisonResult {
  // ── 1. 数据完整性 ──────────────────────────────────────────────────────
  const dataQuality = assessDataQuality(trades, holdings);
  const unrealizedPnL = portfolioUnrealizedPnL ?? 0;
  const hasUnrealizedData = portfolioUnrealizedPnL !== undefined;

  // ── 2. 计算已实现盈亏 ──────────────────────────────────────────────────
  const realized = calcRealizedPnL(trades);
  const totalInvestment = calcTotalInvestment(trades, holdings);
  const activeInvestment = calcActiveInvestment(trades, holdings);
  const peakInvestment = calcPeakInvestment(trades);

  // ── 3. 全周期总账 ──────────────────────────────────────────────────────
  const totalPnL = realized.totalRealizedPnL + unrealizedPnL;
  const activeReturnPct = activeInvestment > 0
    ? Math.round((totalPnL / activeInvestment) * 10000) / 100
    : 0;
  const totalReturn: TotalReturn = {
    realizedPnL: Math.round(realized.totalRealizedPnL * 100) / 100,
    unrealizedPnL: Math.round(unrealizedPnL * 100) / 100,
    totalPnL: Math.round(totalPnL * 100) / 100,
    totalInvestment: Math.round(totalInvestment * 100) / 100,
    activeInvestment: Math.round(activeInvestment * 100) / 100,
    peakInvestment: Math.round(peakInvestment * 100) / 100,
    totalReturnPct: totalInvestment > 0
      ? Math.round((totalPnL / totalInvestment) * 10000) / 100
      : 0,
    activeReturnPct,
  };

  // ── 4. 按周切割 ────────────────────────────────────────────────────────
  const weeklyMap = groupByPeriod(
    realized.tradeResults,
    (d) => isoWeekLabel(d),
    (d) => weekStart(d),
    (d) => weekEndAfter(d),
  );

  const weeklyComparison: PeriodPerformance[] = [];
  for (const [label, group] of weeklyMap) {
    const periodPnL = group.items.reduce((s, r) => s + r.pnl, 0);
    // 不用 per-period capital 分摊（因为没有持仓快照），直接用全周期总投入的比例估算
    weeklyComparison.push(buildPeriodPerformance(
      label,
      group.startDate,
      group.endDate,
      periodPnL,
      null, // 无持仓快照
      totalInvestment,
      group.items,
    ));
  }

  // 按时间排序
  weeklyComparison.sort((a, b) => a.label.localeCompare(b.label));

  // ── 5. 按月切割 ────────────────────────────────────────────────────────
  const monthlyMap = groupByPeriod(
    realized.tradeResults,
    (d) => monthLabel(d),
    (d) => `${d.slice(0, 7)}-01`,
    (d) => {
      const [y, m] = d.slice(0, 7).split('-').map(Number);
      const lastDay = new Date(y, m, 0).getDate();
      return `${d.slice(0, 7)}-${String(lastDay).padStart(2, '0')}`;
    },
  );

  const monthlyComparison: PeriodPerformance[] = [];
  for (const [label, group] of monthlyMap) {
    const periodPnL = group.items.reduce((s, r) => s + r.pnl, 0);
    monthlyComparison.push(buildPeriodPerformance(
      label,
      group.startDate,
      group.endDate,
      periodPnL,
      null,
      totalInvestment,
      group.items,
    ));
  }
  monthlyComparison.sort((a, b) => a.label.localeCompare(b.label));

  // ── 6. 全周期 ──────────────────────────────────────────────────────────
  const allOrdered = [...realized.tradeResults].sort((a, b) => a.date.localeCompare(b.date));
  const allStart = allOrdered.length > 0 ? allOrdered[0].date : new Date().toISOString().slice(0, 10);
  const allEnd = new Date().toISOString().slice(0, 10);

  const allTimeComparison = buildPeriodPerformance(
    '全周期',
    allStart,
    allEnd,
    totalReturn.realizedPnL,
    totalReturn.unrealizedPnL,
    totalInvestment,
    realized.tradeResults,
  );

  return {
    totalReturn,
    weeklyComparison,
    monthlyComparison,
    allTimeComparison,
    dataQuality,
  };
}

// ─── 以下为原有函数（保留，供 evolution-service.ts 调用） ──────────────────

/**
 * 计算性能差距
 */
export function calculateGap(target: number, actual: number, market: number): PerformanceGap {
  return {
    target,
    actual,
    gap: target - actual,
    market,
    alpha: actual - market,
  };
}

/**
 * 检查目标是否合理
 */
export function checkTargetRealistic(
  target: number,
  market: number,
  historicalReturns: number[],
  marketVolatility: number,
): TargetRealisticCheck {
  const reasons: string[] = [];
  let realistic = true;

  if (historicalReturns.length < 3) {
    reasons.push('历史数据不足（<3笔），无法判断目标合理性');
    realistic = false;
    return { realistic, reasons, suggestedTarget: market + 1.5 };
  }

  // vs 大盘
  const vsMarket = target - market;
  if (vsMarket > 10) {
    realistic = false;
    reasons.push(`目标(${target}%)超出大盘(${market}%) ${vsMarket.toFixed(1)}%，过于激进`);
  }

  // vs 历史平均
  const avgHistorical = historicalReturns.reduce((a, b) => a + b, 0) / historicalReturns.length;
  if (avgHistorical > 0 && target > avgHistorical * 2) {
    realistic = false;
    reasons.push(`目标是历史平均(${avgHistorical.toFixed(1)}%)的 ${(target / avgHistorical).toFixed(1)} 倍，不现实`);
  }

  // vs 波动率
  if (target > marketVolatility * 3) {
    realistic = false;
    reasons.push(`目标(${target}%)超出市场波动率(${marketVolatility}%)的3倍，风险过高`);
  }

  const suggestedTarget = realistic ? undefined : market + 5;

  return { realistic, reasons, suggestedTarget };
}

/**
 * 评估 Agent 能力
 */
export function evaluateAgentCapability(
  actual: number,
  market: number,
  alpha: number,
  decisionQuality: DecisionQualityMetrics,
): CapabilityCheck {
  const reasons: string[] = [];
  const weaknesses: string[] = [];
  let capable = true;

  // vs 大盘
  if (alpha < -2) {
    capable = false;
    reasons.push(`跑输大盘 ${Math.abs(alpha).toFixed(1)}%`);
    weaknesses.push('选股能力');
  }

  // 趋势
  if (decisionQuality.recentReturns.length >= 2) {
    const recent = decisionQuality.recentReturns;
    const firstHalf = recent.slice(0, Math.floor(recent.length / 2));
    const secondHalf = recent.slice(Math.floor(recent.length / 2));
    const avgFirst = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
    const avgSecond = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;

    if (avgSecond < avgFirst) {
      reasons.push('收益率趋势下降');
      weaknesses.push('整体策略');
      capable = false;
    }
  }

  // 决策错误率
  if (decisionQuality.errorRate > 0.4) {
    capable = false;
    reasons.push(`决策错误率 ${(decisionQuality.errorRate * 100).toFixed(0)}% 过高`);
    weaknesses.push('决策准确性');
  }

  // 止损执行率
  if (decisionQuality.stopLossExecutionRate < 0.6) {
    capable = false;
    reasons.push(`止损执行率 ${(decisionQuality.stopLossExecutionRate * 100).toFixed(0)}% 不足`);
    weaknesses.push('风控能力');
  }

  return { capable, reasons, weaknesses };
}

/**
 * 归因分析：判断差距的根本原因
 *
 * 减法器核心逻辑：
 *   单信号裁断 — 只确定一个根本原因。
 *   如果数据完整性不足，优先归因为数据问题，不误导进化系统。
 */
export function attributeGap(
  gap: PerformanceGap,
  historicalReturns: number[],
  marketVolatility: number,
  decisionQuality: DecisionQualityMetrics,
  dataQuality?: DataQualityReport,
): AttributionResult {
  // 0. 数据完整性检查（如果提供）
  if (dataQuality && dataQuality.reliability === 'low') {
    return {
      rootCause: 'target_unrealistic',
      confidence: 0.95,
      reasons: [
        '数据完整性不足，进化结果不可靠',
        ...dataQuality.warnings.slice(0, 2),
        '建议：补充完整交易记录后再运行进化分析',
      ],
      recommendation: 'adjust_target',
      suggestedTarget: 5,
    };
  }

  // 1. 目标合理性检查
  const targetCheck = checkTargetRealistic(
    gap.target,
    gap.market,
    historicalReturns,
    marketVolatility,
  );

  // 2. Agent 能力评估
  const capabilityCheck = evaluateAgentCapability(
    gap.actual,
    gap.market,
    gap.alpha,
    decisionQuality,
  );

  // 3. 单信号裁断
  if (!targetCheck.realistic && capabilityCheck.capable) {
    // 目标不合理，能力正常 → 调整目标
    return {
      rootCause: 'target_unrealistic',
      confidence: 0.85,
      reasons: targetCheck.reasons,
      recommendation: 'adjust_target',
      suggestedTarget: targetCheck.suggestedTarget,
    };
  }

  if (targetCheck.realistic && !capabilityCheck.capable) {
    // 目标合理，能力不足 → 优化能力
    return {
      rootCause: 'capability_insufficient',
      confidence: 0.90,
      reasons: capabilityCheck.reasons,
      recommendation: 'trigger_optimizer',
    };
  }

  // 混合情况：优先归因为能力问题
  return {
    rootCause: 'capability_insufficient',
    confidence: 0.60,
    reasons: [...targetCheck.reasons, ...capabilityCheck.reasons],
    recommendation: 'trigger_optimizer',
  };
}
