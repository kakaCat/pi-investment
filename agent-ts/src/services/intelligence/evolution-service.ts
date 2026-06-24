/**
 * Evolution Service - 进化服务主入口
 *
 * 协调各组件完成完整的进化流程。
 * 数据来源：PostgreSQL (via CLI Adapters) / reviews/
 */

import * as fs from 'fs/promises';
import { readFileSync, existsSync, readdirSync } from 'fs';
import * as path from 'path';
import { Subtractor } from './subtractor.js';
import { calculateGap, attributeGap } from './comparator.js';
import { PositionCliAdapter } from '../../infrastructure/adapters/cli/position-cli-adapter.js';
import { TradeCliAdapter } from '../../infrastructure/adapters/cli/trade-cli-adapter.js';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator.js';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter.js';
import { executeOptimizationSuggestions, saveExecutionResult } from './evolution-executor.js';
import { analyzeSessionsAndCalculateEfficiency } from './session-analyzer.js';
import {
  loadRecentEvolutions,
  evaluateLastEvolution,
  updateEvolutionOutcome,
  saveEvolutionHistory,
} from './evolution-history.js';
import {
  loadExperienceSummary,
  generateExperienceSummary,
  saveExperienceSummary,
} from './experience-learner.js';
// market-data-collector 已删除
import { parseSessionLog } from './session-log-parser.js';
import { analyzeToolEfficiency } from './tool-efficiency-analyzer.js';
import { analyzeHoldingDimensions } from './holding-dimension-analyzer.js';
import type { Holding } from './data-collector.js';
import type {
  EvolutionReport,
  DecisionQualityMetrics,
} from '../../types/evolution.js';
import type { MarketContext } from '../../types/market-context.js';
import type { SessionAnalysis } from '../../types/session-log.js';
import type { HoldingDimensionAnalysis } from '../../types/holding-analysis.js';

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

// ─── 数据读取 (CLI → PostgreSQL) ────────────────────────────────────────────

async function loadPortfolio(): Promise<Holding[]> {
  const adapter = new PositionCliAdapter();
  const positions = await adapter.list({ status: 'open' });
  return positions.map(p => ({
    symbol: p.symbol,
    name: p.name || p.symbol,
    quantity: p.quantity,
    avg_cost: p.costBasis ?? 0,
    market: 'A' as 'A' | 'HK',
    notes: p.notes || '',
    added_date: p.entryDate || '',
    original_cost: p.costBasis ?? 0,
    total_invested: (p.costBasis ?? 0) * p.quantity,
    stop_loss: null,
    target_price: null,
    batch_plan: null,
    sector: '',
    buy_reason: p.notes || null,
  } as Holding));
}

async function loadTrades(): Promise<Trade[]> {
  const adapter = new TradeCliAdapter();
  const trades = await adapter.list();
  return trades.map(t => ({
    date: t.timestamp || '',
    action: t.action,
    symbol: t.symbol,
    name: t.name,
    quantity: t.quantity,
    price: t.price,
    amount: t.price * t.quantity,
    market: 'A',
    notes: t.notes || '',
    time: t.timestamp || '',
  } as Trade));
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
  const holdings = await loadPortfolio();
  const allTrades = await loadTrades();
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
      '请先添加交易记录（通过 manage_portfolio 工具或 CLI）'
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

  // ── 2. 减法器：全维度比较 ────────────────────────────────────────────────
  const positionAdapter = new PositionCliAdapter();

  // 获取完整的持仓数据（包含当前价格和浮盈）
  let portfolioSnapshot: any;
  let currentPrices: Record<string, number> = {};

  try {
    const summary = await positionAdapter.getSummary();
    const positions = await positionAdapter.list({ status: 'open' });
    portfolioSnapshot = {
      total_pnl: summary!.totalPnl ?? 0,
      total_pnl_pct: summary!.totalPnlPct ?? 0,
      holdings: positions.map(p => ({
        symbol: p.symbol,
        name: p.name,
        current_price: p.currentPrice ?? 0,
        quantity: p.quantity,
        cost_basis: p.costBasis ?? 0,
      })),
    };
    console.log(`[进化] 持仓浮盈: ¥${portfolioSnapshot.total_pnl.toFixed(2)} (${portfolioSnapshot.total_pnl_pct.toFixed(2)}%)`);

    // 构建当前价格映射
    positions.forEach(p => {
      currentPrices[p.symbol] = p.currentPrice ?? 0;
    });
  } catch (e) {
    console.warn('[进化] 获取持仓浮盈失败，仅使用已实现盈亏:', e);
  }

  // 使用 Subtractor（减法器）进行全维度账本分析
  const subtractor = new Subtractor();

  // 将 evolution-service 的 Trade 类型转换为 subtractor 的 TradeRecord 类型
  const tradeRecords = trades.map((t, idx) => ({
    id: idx,
    symbol: t.symbol,
    name: t.name,
    action: t.action,
    price: t.price,
    quantity: t.quantity,
    amount: t.amount,
    fee: 0, // evolution-service 的 Trade 没有 fee 字段
    pnl: null,
    pnl_pct: null,
    date: t.date,
    reason: t.notes,
  }));

  // 将 holdings 转换为 subtractor 的 HoldingPosition 类型
  const holdingPositions = holdings.map(h => ({
    symbol: h.symbol,
    name: h.name,
    quantity: h.quantity,
    avg_cost: h.avg_cost,
    market: h.market as 'A' | 'HK',
    total_invested: h.total_invested,
    added_date: h.added_date,
    original_cost: h.original_cost,
    notes: h.notes,
  }));

  // 注入数据并运行减法器
  subtractor.injectData(tradeRecords, holdingPositions);
  const comparison = await subtractor.run(currentPrices);
  const {
    totalReturn,
    weeklyComparison,
    monthlyComparison,
    allTimeComparison,
    dataQuality,
  } = comparison;

  // 导出关键指标
  const realizedReturn = totalReturn.totalReturnPct;
  const winRate = allTimeComparison.tradeCount > 0
    ? allTimeComparison.winRate
    : 0;

  // 从周/月切片中提取损益序列
  const tradeResults = comparison.monthlyComparison.length > 0
    ? comparison.monthlyComparison.map(p => p.returnPct)
    : comparison.weeklyComparison.map(p => p.returnPct);

  // ── 3. 收集市场环境数据 ──────────────────────────────────────────────────
  console.log('[进化] 收集市场环境数据...');
  let marketContext: MarketContext | undefined;
  let market = 5; // 默认大盘参考（无实时数据时用 5%）

  // market-data-collector 已删除，跳过市场环境收集
  console.warn('[进化] 市场环境数据收集功能已禁用（服务已删除）');
  marketContext = undefined;

  // ── 4. 收益率 ──────────────────────────────────────────────────────────
  const target = finalConfig.targetReturn;
  const actual = realizedReturn;

  // ── 新增：加载历史和经验 ──────────────────────────────────────────────
  const recentEvolutions = await loadRecentEvolutions(piDir, finalConfig.evolutionWindowRecent);
  const experienceSummary = await loadExperienceSummary(piDir);

  console.log(`[进化] 加载进化历史: ${recentEvolutions.length} 次（决策参考）`);

  // ── 4.1 解析 Session 日志 ────────────────────────────────────────────
  console.log('[进化] 解析 Session 日志...');
  let sessionAnalysis: SessionAnalysis | undefined;

  try {
    const sessionsDir = path.join(piDir, 'sessions');
    const sessionDirs = existsSync(sessionsDir) ? readdirSync(sessionsDir) : [];

    if (sessionDirs.length > 0) {
      // 获取最新的 session 目录
      const latestSession = sessionDirs
        .filter(dir => existsSync(path.join(sessionsDir, dir, 'metadata.json')))
        .sort()
        .reverse()[0];

      if (latestSession) {
        const sessionDir = path.join(sessionsDir, latestSession);
        sessionAnalysis = await parseSessionLog(sessionDir);
        console.log(`[进化] Session 分析完成: ${sessionAnalysis.totalToolCalls} 次工具调用，错误率 ${(sessionAnalysis.overallErrorRate * 100).toFixed(2)}%`);
      }
    }
  } catch (error) {
    console.warn('[进化] 解析 Session 日志失败:', error);
  }

  // ── 4.2 持仓维度分析 ────────────────────────────────────────────────────
  console.log('[进化] 分析持仓维度...');
  let holdingAnalysis: HoldingDimensionAnalysis | undefined;

  try {
    if (holdings.length > 0) {
      // 使用之前已获取的持仓数据和当前价格
      const currentPricesMap = new Map<string, number>();
      const stockInfo = new Map<string, { name: string; sector?: string; marketCap?: number }>();

      const positions = await positionAdapter.list({ status: 'open' });
      positions.forEach(p => {
        currentPricesMap.set(p.symbol, p.currentPrice ?? 0);
        stockInfo.set(p.symbol, {
          name: p.name || p.symbol,
          sector: undefined, // TODO: 从数据源获取行业信息
          marketCap: undefined, // TODO: 从数据源获取市值信息
        });
      });

      holdingAnalysis = await analyzeHoldingDimensions(holdings, currentPricesMap, stockInfo);
      console.log(`[进化] 持仓分析完成: ${holdingAnalysis.stocks.length} 只个股，${holdingAnalysis.sectors.length} 个行业`);
      console.log(`[进化] 发现 ${holdingAnalysis.issues.length} 个持仓问题`);
    } else {
      console.log('[进化] 无持仓数据，跳过持仓维度分析');
    }
  } catch (error) {
    console.warn('[进化] 持仓维度分析失败:', error);
  }

  // ── 5. 归因分析 ──────────────────────────────────────────────────────
  const gap = calculateGap(target, actual, market);

  // 历史收益序列（从交易结果提取）
  const historicalReturns = tradeResults.length > 0 ? tradeResults : [0];
  const marketVolatility = 15;

  // 决策质量（从复盘 + 交易统计估算）
  const reviewsDir = path.join(piDir, 'reviews');
  const decisionQuality = calcDecisionQuality(reviewsDir, winRate, historicalReturns, finalConfig.reviewWindowCount);

  const attribution = attributeGap(gap, historicalReturns, marketVolatility, decisionQuality, dataQuality);

  // ── 6. Session 分析：计算工具效能 ──────────────────────────────────────
  console.log('[进化] 开始 Session 分析...');
  const toolStats = analyzeSessionsAndCalculateEfficiency(
    piDir,
    trades,
    finalConfig.tradeWindowDays
  );
  console.log(`[进化] Session 分析完成，评估了 ${toolStats.length} 个工具`);

  // ── 6.5 工具效能分析 ──────────────────────────────────────────────────────
  console.log('[进化] 分析工具效能...');
  const toolEfficiencyAssessment = sessionAnalysis
    ? analyzeToolEfficiency(sessionAnalysis)
    : undefined;

  if (toolEfficiencyAssessment) {
    console.log(`[进化] 工具效能评分: ${toolEfficiencyAssessment.overallScore}/100`);
    if (toolEfficiencyAssessment.problematicTools.length > 0) {
      console.log(`[进化] 发现 ${toolEfficiencyAssessment.problematicTools.length} 个高失败率工具`);
    }
    if (toolEfficiencyAssessment.slowTools.length > 0) {
      console.log(`[进化] 发现 ${toolEfficiencyAssessment.slowTools.length} 个性能瓶颈工具`);
    }
  }

  // ── 评估上次进化效果 ────────────────────────────────────────────────
  if (recentEvolutions.length > 0) {
    const lastEvolution = recentEvolutions[0];
    const currentMetrics = {
      return: actual,
      winRate: allTimeComparison.winRate,
      maxDrawdown: allTimeComparison.returnPct < 0 ? Math.abs(allTimeComparison.returnPct) : 0,
      toolStats: [], // Session 日志的 ToolStats 与 ToolEfficiency 结构不同，暂时使用空数组
    };

    try {
      const evaluation = await evaluateLastEvolution(
        lastEvolution,
        currentMetrics,
        marketContext,
        holdingAnalysis,
        toolEfficiencyAssessment?.overallScore,
        sessionAnalysis?.overallErrorRate
      );
      await updateEvolutionOutcome(lastEvolution.evolutionId, currentMetrics, evaluation, piDir);
      console.log(`[进化] 已评估上次进化 ${lastEvolution.evolutionId}，评分: ${evaluation.score}/100`);
    } catch (e) {
      console.error('[进化] 评估上次进化失败:', e);
    }
  }

  // ── 7. 补偿器：策略 + 建议（增强：传入历史和经验）─────────────────────
  const strategy = determineOptimizerStrategy(gap.gap);

  const totalTradeCount = monthlyComparison.reduce((s, m) => s + m.tradeCount, 0) ||
                           weeklyComparison.reduce((s, w) => s + w.tradeCount, 0);
  const weaknesses: string[] = [];
  if (winRate <= 0.5 && totalTradeCount > 0) weaknesses.push('选股能力');
  if (decisionQuality.stopLossExecutionRate < 0.6) weaknesses.push('风控能力');
  if (winRate < 0.5 && totalTradeCount > 5) weaknesses.push('决策准确性');

  const suggestions = generateOptimizationSuggestions(
    {
      level: strategy.level,
      toolStats: toolStats, // 使用 Session 分析的结果
      weaknesses,
    },
    recentEvolutions,
    experienceSummary
  );

  // 合并工具效能建议
  const allSuggestions = toolEfficiencyAssessment
    ? [...suggestions, ...toolEfficiencyAssessment.suggestions]
    : suggestions;

  console.log(`[进化] 生成优化建议: ${allSuggestions.length} 条（基础 ${suggestions.length} + 工具效能 ${toolEfficiencyAssessment?.suggestions.length || 0}）`);


  // ── 8. 成功/失败模式（从周切片提取） ──────────────────────────────────────
  const positiveWeeks = weeklyComparison.filter(w => w.totalPnL > 0);
  const negativeWeeks = weeklyComparison.filter(w => w.totalPnL < 0);

  const successPatterns = positiveWeeks.length > 0 ? [{
    pattern: '盈利周',
    count: positiveWeeks.length,
    winRate: Math.round((positiveWeeks.length / weeklyComparison.length) * 100) / 100,
    avgReturn: positiveWeeks.reduce((s, w) => s + w.returnPct, 0) / positiveWeeks.length,
  }] : [];

  const failurePatterns = negativeWeeks.length > 0 ? [{
    pattern: '亏损周',
    count: negativeWeeks.length,
    winRate: 0,
    avgLoss: Math.abs(negativeWeeks.reduce((s, w) => s + w.returnPct, 0) / negativeWeeks.length),
  }] : [];

  // ── 9. 生成报告 ────────────────────────────────────────────────────────
  const monthlyReturns = monthlyComparison.map(m => m.returnPct);
  const allReturns = weeklyComparison.map(w => w.returnPct);

  const report = generateEvolutionReport({
    period: `${dataQuality.earliestTradeDate ?? '--'} ~ ${dataQuality.latestTradeDate ?? new Date().toISOString().slice(0, 10)}`,
    performance: {
      target,
      actual: Math.round(actual * 100) / 100,
      gap: Math.round(gap.gap * 100) / 100,
      market,
      winRate,
      maxDrawdown: allReturns.length > 0
        ? Math.round(Math.min(...allReturns, 0 as number) * 100) / 100
        : 0,
      sharpeRatio: monthlyReturns.length > 1
        ? calcSharpe(monthlyReturns)
        : 0,
    },
    attribution,
    toolStats: toolStats, // 使用 Session 分析的结果
    marketContext, // 新增：传入市场环境数据
    sessionAnalysis, // 新增：传入 Session 日志分析
    toolEfficiencyAssessment, // 新增：传入工具效能评估
    holdingAnalysis, // 新增：传入持仓维度分析
    suggestions: allSuggestions,
    successPatterns,
    failurePatterns,
    comparisonResult: comparison, // 传入减法器全量数据
  });

  // ── 9. 保存报告 ────────────────────────────────────────────────────────
  const markdown = formatReportAsMarkdown(report, recentEvolutions, experienceSummary ?? undefined, comparison);

  const evolutionDir = path.join(piDir, 'evolution');
  await fs.mkdir(evolutionDir, { recursive: true });

  // 使用日期 + 时间戳，避免同一天多次运行时覆盖
  const date = new Date();
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
  const reportPath = path.join(evolutionDir, `evolution-${dateStr}-${timeStr}.md`);

  await fs.writeFile(reportPath, markdown, 'utf-8');

  // ── 9. 执行优化建议（完全自动化）────────────────────────────────────────
  const executionResult = await executeOptimizationSuggestions(allSuggestions, piDir, {
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
    allSuggestions,
    appliedIds,
    {
      return: actual,
      winRate,
      maxDrawdown: allTimeComparison.returnPct < 0 ? Math.abs(allTimeComparison.returnPct) : 0,
      toolStats: toolStats,
    },
    piDir
  );

  // ── 新增：更新版本历史 ────────────────────────────────────────────────
  await updateVersionHistory(evolutionDir, executionResult, allSuggestions);

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
  console.log(`  - 数据可靠性: ${dataQuality.reliability}`);
  console.log(`  - 交易记录: ${trades.length} 笔，持仓 ${holdings.length} 只`);
  console.log(`  - 总账: 已实现 ¥${totalReturn.realizedPnL} | 浮盈 ¥${totalReturn.unrealizedPnL} | 总收益 ¥${totalReturn.totalPnL} | 收益率 ${actual}% (目标: ${target}%)`);
  console.log(`  - 周切片: ${weeklyComparison.length} 周 | 月切片: ${monthlyComparison.length} 月`);
  console.log(`  - 归因: ${attribution.rootCause === 'target_unrealistic' ? '目标不合理' : '能力需优化'}`);
  console.log(`  - 建议: ${allSuggestions.length} 条，已应用 ${executionResult.applied.filter(a => a.status === 'success').length} 条`);
  console.log(`  - 报告: ${reportPath}`);

  return {
    reportPath,
    report,
    executionResultPath,
    summary: {
      targetReturn: target,
      realizedReturn: Math.round(actual * 100) / 100,
      winRate: Math.round(winRate * 100),
      totalTrades: totalTradeCount,
      attribution: attribution.rootCause,
      strategyLevel: strategy.level,
      suggestionCount: allSuggestions.length,
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
