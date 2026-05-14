/**
 * Evolution Service - 进化服务主入口
 *
 * 协调各组件完成完整的进化流程。
 * 数据来源：portfolio.json / trades.json / reviews/
 */

import * as fs from 'fs/promises';
import { readFileSync, existsSync, readdirSync } from 'fs';
import * as path from 'path';
import { calculateGap, attributeGap } from './comparator';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter';
import { executeOptimizationSuggestions, saveExecutionResult } from './evolution-executor';
import type {
  EvolutionReport,
  DecisionQualityMetrics,
} from '../../types/evolution.js';

// ─── 类型 ────────────────────────────────────────────────────────────────────

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
  time: string;
}

interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  market: string;
  total_invested: number;
  sector?: string;
  buy_reason?: string;
}

interface EvolutionResult {
  reportPath: string;
  report: EvolutionReport;
  executionResultPath?: string;
  summary: {
    targetReturn: number;
    realizedReturn: number;
    winRate: number;
    totalTrades: number;
    attribution: string;
    strategyLevel: string;
    suggestionCount: number;
    appliedCount: number;
    manualTaskCount: number;
  };
}

// ─── 配置 ────────────────────────────────────────────────────────────────────

const DEFAULT_TARGET_RETURN = 10; // 默认年化目标 10%
const PI_DIR = path.join(process.cwd(), '.pi-invest');

// ─── 数据读取 ────────────────────────────────────────────────────────────────

function loadJson<T>(filePath: string): T | null {
  try {
    if (!existsSync(filePath)) return null;
    return JSON.parse(readFileSync(filePath, 'utf-8'));
  } catch {
    return null;
  }
}

function loadPortfolio(): Holding[] {
  const data = loadJson<{ holdings: Holding[] }>(path.join(PI_DIR, 'portfolio.json'));
  return data?.holdings ?? [];
}

function loadTrades(): Trade[] {
  const data = loadJson<{ trades: Trade[] }>(path.join(PI_DIR, 'trades.json'));
  return data?.trades ?? [];
}

// ─── 指标计算 ────────────────────────────────────────────────────────────────

/**
 * 从交易记录计算已实现盈亏
 * 按「先买后卖」配对，FIFO 计算每笔已平仓交易的盈亏
 */
function calcRealizedPnL(trades: Trade[]): {
  totalRealizedPnL: number;
  totalInvested: number;
  realizedReturn: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  tradeResults: Array<{ symbol: string; pnl: number; pnlPct: number }>;
} {
  // 过滤掉明显的回退/纠错记录（notes 含 "回退" / "撤回" / "纠正" / "误操作" 等）
  const cleanTrades = trades.filter(t => {
    const n = t.notes;
    if (n.includes('回退') || n.includes('撤回') || n.includes('纠正') || n.includes('误操作')) return false;
    return true;
  });

  // 按 symbol 分组，FIFO 配对
  const bySymbol = new Map<string, Trade[]>();
  for (const t of cleanTrades) {
    const list = bySymbol.get(t.symbol) || [];
    list.push(t);
    bySymbol.set(t.symbol, list);
  }

  const tradeResults: Array<{ symbol: string; pnl: number; pnlPct: number }> = [];
  let totalRealizedPnL = 0;
  let totalInvested = 0;
  let winCount = 0;
  let lossCount = 0;

  for (const [symbol, symbolTrades] of bySymbol) {
    // FIFO: 用队列模拟
    const buyQueue: Trade[] = [];

    for (const t of symbolTrades) {
      if (t.action === 'buy') {
        buyQueue.push(t);
      } else {
        // sell: 从最早的买入队列中匹配
        let remainingSell = t.quantity;

        while (remainingSell > 0 && buyQueue.length > 0) {
          const buy = buyQueue[0];
          const matchedQty = Math.min(remainingSell, buy.quantity);

          const buyCost = buy.price * matchedQty;
          const sellProceeds = t.price * matchedQty;
          const pnl = sellProceeds - buyCost;
          const pnlPct = ((t.price - buy.price) / buy.price) * 100;

          totalRealizedPnL += pnl;
          totalInvested += buyCost;
          tradeResults.push({ symbol, pnl, pnlPct });

          if (pnl > 0) winCount++;
          else if (pnl < 0) lossCount++;

          buy.quantity -= matchedQty;
          remainingSell -= matchedQty;

          if (buy.quantity <= 0) buyQueue.shift();
        }

        // 如果还有剩余卖出但队列已空（可能是之前买的已全部卖出），忽略
      }
    }
  }

  const totalTrades = winCount + lossCount;
  const realizedReturn = totalInvested > 0 ? (totalRealizedPnL / totalInvested) * 100 : 0;

  return {
    totalRealizedPnL,
    totalInvested,
    realizedReturn,
    winCount,
    lossCount,
    winRate: totalTrades > 0 ? winCount / totalTrades : 0,
    tradeResults,
  };
}

/**
 * 从复盘报告中提取决策质量信号
 */
function calcDecisionQuality(
  reviewsDir: string,
  winRate: number,
  recentReturns: number[],
): DecisionQualityMetrics {
  let stopLossExecutionRate = 0.5; // 默认

  try {
    const files = existsSync(reviewsDir)
      ? readdirSync(reviewsDir).filter(f => f.endsWith('.md')).sort()
      : [];
    const recent = files.slice(-10);

    let totalStopLossSuggestions = 0;
    let totalSuggestions = 0;

    for (const file of recent) {
      const content = readFileSync(path.join(reviewsDir, file), 'utf-8');
      totalStopLossSuggestions += (content.match(/考虑止损/g) || []).length;
      totalSuggestions += (content.match(/操作建议/g) || []).length;
    }

    // 止损建议越少说明风控越好
    if (totalSuggestions > 0) {
      stopLossExecutionRate = Math.max(0, 1 - totalStopLossSuggestions / totalSuggestions);
    }
  } catch {
    // ignore
  }

  return {
    recentReturns: recentReturns.length > 0 ? recentReturns : [0],
    errorRate: winRate < 0.4 ? 0.6 : winRate < 0.6 ? 0.4 : 0.2,
    stopLossExecutionRate,
  };
}

// ─── 主入口 ──────────────────────────────────────────────────────────────────

export async function runWeeklyEvolution(): Promise<EvolutionResult> {
  // ── 1. 读取真实数据 ────────────────────────────────────────────────────
  const holdings = loadPortfolio();
  const trades = loadTrades();
  const piDir = PI_DIR;

  // ── 2. 计算已实现收益 ──────────────────────────────────────────────────
  const {
    totalRealizedPnL,
    totalInvested,
    realizedReturn,
    winCount,
    lossCount,
    winRate,
    tradeResults,
  } = calcRealizedPnL(trades);

  // 当前持仓总成本
  const holdingCost = holdings.reduce((sum, h) => sum + h.total_invested, 0);
  const totalCapital = totalInvested + holdingCost;

  // ── 3. 收益率 ──────────────────────────────────────────────────────────
  const target = DEFAULT_TARGET_RETURN;
  const actual = realizedReturn;
  const market = 5; // 默认大盘参考（无实时数据时用 5%）

  // ── 4. 减法器：计算差距 + 归因 ─────────────────────────────────────────
  const gap = calculateGap(target, actual, market);

  // 历史收益序列（从交易结果提取）
  const historicalReturns = tradeResults.map(r => r.pnlPct);
  const marketVolatility = 15;

  // 决策质量（从复盘 + 交易统计估算）
  const reviewsDir = path.join(piDir, 'reviews');
  const decisionQuality = calcDecisionQuality(reviewsDir, winRate, historicalReturns);

  const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality);

  // ── 5. 补偿器：策略 + 建议 ─────────────────────────────────────────────
  const strategy = determineOptimizerStrategy(gap.gap);

  const weaknesses: string[] = [];
  if (winRate <= 0.5 && winCount + lossCount > 0) weaknesses.push('选股能力');
  if (decisionQuality.stopLossExecutionRate < 0.6) weaknesses.push('风控能力');
  if (lossCount > winCount && winCount + lossCount > 5) weaknesses.push('决策准确性');

  const suggestions = generateOptimizationSuggestions({
    level: strategy.level,
    toolStats: [],
    weaknesses,
  });

  // ── 6. 成功/失败模式 ────────────────────────────────────────────────────
  const profitTrades = tradeResults.filter(r => r.pnl > 0);
  const lossTrades = tradeResults.filter(r => r.pnl < 0);

  const successPatterns = profitTrades.length > 0 ? [{
    pattern: '盈利交易',
    count: profitTrades.length,
    winRate: 1,
    avgReturn: profitTrades.reduce((s, r) => s + r.pnlPct, 0) / profitTrades.length,
  }] : [];

  const failurePatterns = lossTrades.length > 0 ? [{
    pattern: '亏损交易',
    count: lossTrades.length,
    winRate: 0,
    avgLoss: Math.abs(lossTrades.reduce((s, r) => s + r.pnlPct, 0) / lossTrades.length),
  }] : [];

  // ── 7. 生成报告 ────────────────────────────────────────────────────────
  const report = generateEvolutionReport({
    period: `${trades.length > 0 ? trades[0].date : '--'} ~ ${new Date().toISOString().split('T')[0]}`,
    performance: {
      target,
      actual: Math.round(actual * 100) / 100,
      gap: Math.round(gap.gap * 100) / 100,
      market,
      winRate,
      maxDrawdown: lossTrades.length > 0
        ? Math.round(Math.min(...lossTrades.map(r => r.pnlPct)) * 100) / 100
        : 0,
      sharpeRatio: historicalReturns.length > 1
        ? calcSharpe(historicalReturns)
        : 0,
    },
    attribution,
    toolStats: [],
    suggestions,
    successPatterns,
    failurePatterns,
  });

  // ── 8. 保存报告 ────────────────────────────────────────────────────────
  const markdown = formatReportAsMarkdown(report);

  const evolutionDir = path.join(piDir, 'evolution');
  await fs.mkdir(evolutionDir, { recursive: true });

  const timestamp = new Date().toISOString().split('T')[0];
  const reportPath = path.join(evolutionDir, `evolution-${timestamp}.md`);
  await fs.writeFile(reportPath, markdown, 'utf-8');

  // ── 9. 执行优化建议 ────────────────────────────────────────────────────
  const executionResult = await executeOptimizationSuggestions(suggestions, piDir);
  const executionResultPath = await saveExecutionResult(executionResult, evolutionDir);

  return {
    reportPath,
    report,
    executionResultPath,
    summary: {
      targetReturn: target,
      realizedReturn: Math.round(actual * 100) / 100,
      winRate: Math.round(winRate * 100),
      totalTrades: winCount + lossCount,
      attribution: attribution.rootCause,
      strategyLevel: strategy.level,
      suggestionCount: suggestions.length,
      appliedCount: executionResult.applied.filter(a => a.status === 'success').length,
      manualTaskCount: executionResult.manualTasks.length,
    },
  };
}

/** 简化的夏普比率计算 */
function calcSharpe(returns: number[]): number {
  const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((s, r) => s + (r - avg) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  return std > 0 ? (avg / std) * Math.sqrt(252) : 0;
}
