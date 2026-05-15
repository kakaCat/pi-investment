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
import { analyzeSessionsAndCalculateEfficiency } from './session-analyzer';
import {
  loadRecentEvolutions,
  evaluateLastEvolution,
  updateEvolutionOutcome,
  saveEvolutionHistory,
} from './evolution-history';
import {
  loadExperienceSummary,
  generateExperienceSummary,
  saveExperienceSummary,
} from './experience-learner';
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
    evolutionId?: string; // 新增
  };
}

// ─── 配置 ────────────────────────────────────────────────────────────────────

const DEFAULT_TARGET_RETURN = 10; // 默认年化目标 10%
const PI_DIR = path.join(process.cwd(), '.pi-invest');

/**
 * 进化配置
 */
export interface EvolutionConfig {
  targetReturn?: number;           // 目标收益率，默认 10%
  tradeWindowDays?: number;        // 交易记录时间窗口（天），undefined = 全部
  reviewWindowCount?: number;      // 复盘报告数量，默认 10
  evolutionWindowRecent?: number;  // 进化历史（决策参考），默认 3
  evolutionWindowLearning?: number; // 进化历史（经验学习），默认 100
}

const DEFAULT_CONFIG: Required<EvolutionConfig> = {
  targetReturn: 10,
  tradeWindowDays: 90,              // 默认只看最近 90 天（约 3 个月）
  reviewWindowCount: 10,
  evolutionWindowRecent: 3,
  evolutionWindowLearning: 100,
};

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

/**
 * 过滤交易记录（按时间窗口）
 */
function filterTradesByWindow(trades: Trade[], windowDays?: number): Trade[] {
  if (!windowDays) return trades; // undefined = 全部

  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - windowDays);
  const cutoffStr = cutoffDate.toISOString().split('T')[0];

  const filtered = trades.filter(t => t.date >= cutoffStr);

  console.log(`[进化] 交易记录过滤: ${trades.length} → ${filtered.length} (最近 ${windowDays} 天)`);

  return filtered;
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
    if (n && (n.includes('回退') || n.includes('撤回') || n.includes('纠正') || n.includes('误操作'))) return false;
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
  reviewWindowCount: number = 10,
): DecisionQualityMetrics {
  let stopLossExecutionRate = 0.5; // 默认

  try {
    const files = existsSync(reviewsDir)
      ? readdirSync(reviewsDir).filter(f => f.endsWith('.md')).sort()
      : [];
    const recent = files.slice(-reviewWindowCount);

    console.log(`[进化] 复盘报告扫描: ${files.length} 份，分析最近 ${recent.length} 份`);

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

export async function runWeeklyEvolution(config: EvolutionConfig = {}): Promise<EvolutionResult> {
  // 合并配置
  const finalConfig = { ...DEFAULT_CONFIG, ...config };

  console.log(`[进化] 配置参数:`);
  console.log(`  - 目标收益率: ${finalConfig.targetReturn}%`);
  console.log(`  - 交易窗口: ${finalConfig.tradeWindowDays ? `${finalConfig.tradeWindowDays} 天` : '全部'}`);
  console.log(`  - 复盘报告: 最近 ${finalConfig.reviewWindowCount} 份`);
  console.log(`  - 进化历史（决策）: 最近 ${finalConfig.evolutionWindowRecent} 次`);
  console.log(`  - 进化历史（学习）: 最近 ${finalConfig.evolutionWindowLearning} 次`);

  // ── 1. 读取真实数据 ────────────────────────────────────────────────────
  const holdings = loadPortfolio();
  const allTrades = loadTrades();
  const trades = filterTradesByWindow(allTrades, finalConfig.tradeWindowDays);
  const piDir = PI_DIR;

  // ── 数据检查 ────────────────────────────────────────────────────────────
  console.log(`[进化] 数据检查:`);
  console.log(`  - 持仓数量: ${holdings.length}`);
  console.log(`  - 交易记录: ${allTrades.length} 笔（窗口内: ${trades.length} 笔）`);

  // 检查 1: 是否有交易数据
  if (allTrades.length === 0) {
    throw new Error(
      '❌ 没有交易数据，无法运行进化分析。\n' +
      '请先添加交易记录到 .pi-invest/trades.json'
    );
  }

  // 检查 2: 窗口内是否有足够的交易
  if (trades.length === 0) {
    throw new Error(
      `❌ 时间窗口内没有交易数据（${finalConfig.tradeWindowDays ? `最近 ${finalConfig.tradeWindowDays} 天` : '全部'}）。\n` +
      `建议：\n` +
      `  - 使用 --all 分析全部交易\n` +
      `  - 或增加时间窗口（如 --days 180）`
    );
  }

  // 检查 3: 交易数量是否足够（至少 3 笔）
  if (trades.length < 3) {
    console.warn(`⚠️  交易数据较少（${trades.length} 笔），分析结果可能不准确。`);
    console.warn(`   建议至少有 3 笔交易才能产生有意义的统计结果。`);
  }

  // 检查 4: 是否有持仓数据（警告，不阻塞）
  if (holdings.length === 0) {
    console.warn(`⚠️  没有持仓数据，部分指标可能不完整。`);
  }

  console.log(`✅ 数据检查通过，开始分析...\n`);

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
  const target = finalConfig.targetReturn;
  const actual = realizedReturn;
  const market = 5; // 默认大盘参考（无实时数据时用 5%）

  // ── 新增：加载历史和经验 ──────────────────────────────────────────────
  const recentEvolutions = await loadRecentEvolutions(piDir, finalConfig.evolutionWindowRecent);
  const experienceSummary = await loadExperienceSummary(piDir);

  console.log(`[进化] 加载进化历史: ${recentEvolutions.length} 次（决策参考）`);

  // ── 新增：评估上次进化效果 ────────────────────────────────────────────
  if (recentEvolutions.length > 0) {
    const lastEvolution = recentEvolutions[0];
    const currentMetrics = {
      return: actual,
      winRate,
      maxDrawdown: tradeResults.length > 0
        ? Math.min(...tradeResults.map(r => r.pnlPct))
        : 0,
      toolStats: [],
    };

    try {
      const evaluation = await evaluateLastEvolution(lastEvolution, currentMetrics);
      await updateEvolutionOutcome(lastEvolution.evolutionId, currentMetrics, evaluation, piDir);
      console.log(`[进化] 已评估上次进化 ${lastEvolution.evolutionId}，评分: ${evaluation.score}/100`);
    } catch (e) {
      console.error('[进化] 评估上次进化失败:', e);
    }
  }

  // ── 4. 减法器：计算差距 + 归因 ─────────────────────────────────────────
  const gap = calculateGap(target, actual, market);

  // 历史收益序列（从交易结果提取）
  const historicalReturns = tradeResults.map(r => r.pnlPct);
  const marketVolatility = 15;

  // 决策质量（从复盘 + 交易统计估算）
  const reviewsDir = path.join(piDir, 'reviews');
  const decisionQuality = calcDecisionQuality(reviewsDir, winRate, historicalReturns, finalConfig.reviewWindowCount);

  const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality);

  // ── 5. Session 分析：计算工具效能 ──────────────────────────────────────
  console.log('[进化] 开始 Session 分析...');
  const toolStats = analyzeSessionsAndCalculateEfficiency(
    piDir,
    trades,
    finalConfig.tradeWindowDays
  );
  console.log(`[进化] Session 分析完成，评估了 ${toolStats.length} 个工具`);

  // ── 6. 补偿器：策略 + 建议（增强：传入历史和经验）─────────────────────
  const strategy = determineOptimizerStrategy(gap.gap);

  const weaknesses: string[] = [];
  if (winRate <= 0.5 && winCount + lossCount > 0) weaknesses.push('选股能力');
  if (decisionQuality.stopLossExecutionRate < 0.6) weaknesses.push('风控能力');
  if (lossCount > winCount && winCount + lossCount > 5) weaknesses.push('决策准确性');

  const suggestions = generateOptimizationSuggestions(
    {
      level: strategy.level,
      toolStats: toolStats, // 使用 Session 分析的结果
      weaknesses,
    },
    recentEvolutions,
    experienceSummary
  );

  // ── 7. 成功/失败模式 ────────────────────────────────────────────────────
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

  // ── 8. 生成报告 ────────────────────────────────────────────────────────
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
    toolStats: toolStats, // 使用 Session 分析的结果
    suggestions,
    successPatterns,
    failurePatterns,
  });

  // ── 9. 保存报告 ────────────────────────────────────────────────────────
  const markdown = formatReportAsMarkdown(report, recentEvolutions, experienceSummary ?? undefined);

  const evolutionDir = path.join(piDir, 'evolution');
  await fs.mkdir(evolutionDir, { recursive: true });

  // 使用日期 + 时间戳，避免同一天多次运行时覆盖
  const date = new Date();
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
  const reportPath = path.join(evolutionDir, `evolution-${dateStr}-${timeStr}.md`);

  await fs.writeFile(reportPath, markdown, 'utf-8');

  // ── 9. 执行优化建议（完全自动化）────────────────────────────────────────
  const executionResult = await executeOptimizationSuggestions(suggestions, piDir, {
    autoExecute: true,
    requireApproval: [], // 空数组 = 所有类型都自动执行
    maxRollbackHistory: 10,
    parameterRanges: {
      stop_loss_threshold: { min: 0.03, max: 0.15 },
      position_size_ratio: { min: 0.05, max: 0.3 },
      risk_preference: { min: 0.1, max: 1.0 },
    },
  });
  const executionResultPath = await saveExecutionResult(executionResult, evolutionDir);

  // ── 新增：保存本次进化历史 ────────────────────────────────────────────
  const appliedIds = executionResult.applied
    .filter(a => a.status === 'success')
    .map(a => a.suggestionId);

  const evolutionId = await saveEvolutionHistory(
    suggestions,
    appliedIds,
    {
      return: actual,
      winRate,
      maxDrawdown: lossTrades.length > 0
        ? Math.min(...lossTrades.map(r => r.pnlPct))
        : 0,
      toolStats: toolStats,
    },
    piDir
  );

  // ── 新增：更新版本历史 ────────────────────────────────────────────────
  await updateVersionHistory(evolutionDir, executionResult, suggestions);

  // ── 新增：更新经验总结 ────────────────────────────────────────────────
  try {
    const allHistory = await loadRecentEvolutions(piDir, finalConfig.evolutionWindowLearning);
    const newSummary = await generateExperienceSummary(allHistory);
    await saveExperienceSummary(newSummary, piDir);
    console.log(`[进化] 已更新经验总结，共 ${allHistory.length} 次进化（学习窗口）`);
  } catch (e) {
    console.error('[进化] 更新经验总结失败:', e);
  }

  // ── 输出统计信息 ──────────────────────────────────────────────────────
  console.log(`\n[进化] 本次进化完成:`);
  console.log(`  - 分析交易: ${trades.length} 笔 (${finalConfig.tradeWindowDays ? `最近 ${finalConfig.tradeWindowDays} 天` : '全部'})`);
  console.log(`  - 已实现收益: ${Math.round(actual * 100) / 100}% (目标: ${target}%)`);
  console.log(`  - 胜率: ${Math.round(winRate * 100)}% (${winCount}胜 ${lossCount}负)`);
  console.log(`  - 归因: ${attribution.rootCause === 'target_unrealistic' ? '目标不合理' : '能力需优化'}`);
  console.log(`  - 建议: ${suggestions.length} 条，已应用 ${executionResult.applied.filter(a => a.status === 'success').length} 条`);
  console.log(`  - 报告: ${reportPath}`);

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
      evolutionId,
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

/**
 * 更新版本历史
 */
async function updateVersionHistory(
  evolutionDir: string,
  executionResult: any,
  suggestions: any[]
): Promise<void> {
  const versionFile = path.join(evolutionDir, 'version-history.md');

  try {
    let content = '';
    let currentVersion = 'v1';

    // 读取现有版本历史
    if (existsSync(versionFile)) {
      content = await fs.readFile(versionFile, 'utf-8');
      const versionMatch = content.match(/\*\*当前版本\*\*: (v\d+)/);
      if (versionMatch) {
        const vNum = parseInt(versionMatch[1].substring(1));
        currentVersion = `v${vNum + 1}`;
      }
    }

    // 如果有成功应用的建议，才增加版本号
    const appliedCount = executionResult.applied.filter((a: any) => a.status === 'success').length;
    if (appliedCount === 0) {
      console.log('[版本] 无变更，不更新版本');
      return;
    }

    // 生成变更记录
    const changes: string[] = [];
    for (const applied of executionResult.applied) {
      if (applied.status === 'success') {
        changes.push(`- ${applied.type}: ${applied.message}`);
      }
    }

    // 更新版本历史
    const newEntry = `
## ${currentVersion} (${new Date().toISOString().split('T')[0]})

### 变更内容
${changes.join('\n')}

**应用建议**: ${appliedCount} 条
**手动任务**: ${executionResult.manualTasks.length} 条

---
`;

    // 插入到文件开头（在第一个 ## 之前）
    if (content) {
      const firstVersionIndex = content.indexOf('\n## v');
      if (firstVersionIndex > 0) {
        content = content.substring(0, firstVersionIndex) + newEntry + content.substring(firstVersionIndex);
      } else {
        content += newEntry;
      }
      // 更新当前版本号
      content = content.replace(/\*\*当前版本\*\*: v\d+/, `**当前版本**: ${currentVersion}`);
    }

    await fs.writeFile(versionFile, content, 'utf-8');
    console.log(`[版本] 已更新到 ${currentVersion}`);
  } catch (e) {
    console.error('[版本] 更新版本历史失败:', e);
  }
}
