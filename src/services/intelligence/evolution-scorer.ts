/**
 * 进化评分器 - 优化后的评分算法
 *
 * 评分结构：
 * - 基础分（60%）：收益率改善、胜率改善、回撤控制
 * - 市场调整分（20%）：Alpha生成、板块踏准、市场适应
 * - 能力提升分（20%）：工具效能、决策质量、错误率降低
 */

import type { ToolEfficiency } from '../../types/evolution.js';
import type { MarketContext } from '../../types/market-context.js';
import type { HoldingDimensionAnalysis } from '../../types/holding-analysis.js';

export interface PerformanceMetrics {
  return: number;
  winRate: number;
  maxDrawdown: number;
  toolStats: ToolEfficiency[];
}

export interface EnhancedPerformanceMetrics extends PerformanceMetrics {
  marketContext?: MarketContext;
  holdingAnalysis?: HoldingDimensionAnalysis;
  toolEfficiencyScore?: number;
  errorRate?: number;
}

export interface DetailedEvolutionScore {
  // 基础分（60%）
  baseScore: {
    returnImprovement: number;      // 收益率改善（25%）
    winRateImprovement: number;     // 胜率改善（20%）
    drawdownControl: number;        // 回撤控制（15%）
    subtotal: number;
  };

  // 市场调整分（20%）
  marketAdjustedScore: {
    alphaGeneration: number;        // Alpha 生成能力（10%）
    sectorTiming: number;           // 板块轮动踏准度（5%）
    marketAdaptation: number;       // 市场适应性（5%）
    subtotal: number;
  };

  // 能力提升分（20%）
  capabilityScore: {
    toolEfficiency: number;         // 工具效能提升（10%）
    decisionQuality: number;        // 决策质量提升（5%）
    errorReduction: number;         // 错误率降低（5%）
    subtotal: number;
  };

  // 总分
  totalScore: number;  // 0-100

  // 评级
  grade: 'S' | 'A' | 'B' | 'C' | 'D' | 'F';

  // 详细说明
  breakdown: string[];
}

/**
 * 计算优化后的进化评分
 */
export function calculateEnhancedEvolutionScore(
  baseline: EnhancedPerformanceMetrics,
  outcome: EnhancedPerformanceMetrics
): DetailedEvolutionScore {
  const breakdown: string[] = [];

  // ── 1. 基础分（60%）────────────────────────────────────────────────

  // 1.1 收益率改善（25%）
  const returnImprovement = baseline.return !== 0
    ? (outcome.return - baseline.return) / Math.abs(baseline.return)
    : (outcome.return > 0 ? 1 : outcome.return < 0 ? -1 : 0);

  const returnScore = Math.min(100, Math.max(0, 50 + returnImprovement * 100));
  breakdown.push(`收益率改善: ${returnScore.toFixed(0)}/100 (${outcome.return > baseline.return ? '+' : ''}${(outcome.return - baseline.return).toFixed(2)}%)`);

  // 1.2 胜率改善（20%）
  const winRateImprovement = outcome.winRate - baseline.winRate;
  const winRateScore = Math.min(100, Math.max(0, 50 + winRateImprovement * 200));
  breakdown.push(`胜率改善: ${winRateScore.toFixed(0)}/100 (${winRateImprovement > 0 ? '+' : ''}${(winRateImprovement * 100).toFixed(1)}%)`);

  // 1.3 回撤控制（15%）
  const drawdownImprovement = baseline.maxDrawdown - outcome.maxDrawdown; // 回撤降低是好事
  const drawdownScore = Math.min(100, Math.max(0, 50 + drawdownImprovement * 100));
  breakdown.push(`回撤控制: ${drawdownScore.toFixed(0)}/100 (${drawdownImprovement > 0 ? '降低' : '增加'}${Math.abs(drawdownImprovement).toFixed(2)}%)`);

  const baseSubtotal = returnScore * 0.25 + winRateScore * 0.20 + drawdownScore * 0.15;

  // ── 2. 市场调整分（20%）────────────────────────────────────────────

  // 2.1 Alpha 生成能力（10%）
  let alphaScore = 50; // 默认中性
  if (baseline.marketContext && outcome.marketContext) {
    const baselineMarketReturn = calculateMarketReturn(baseline.marketContext);
    const outcomeMarketReturn = calculateMarketReturn(outcome.marketContext);

    const baselineAlpha = baseline.return - baselineMarketReturn;
    const outcomeAlpha = outcome.return - outcomeMarketReturn;

    const alphaImprovement = outcomeAlpha - baselineAlpha;
    alphaScore = Math.min(100, Math.max(0, 50 + alphaImprovement * 50));
    breakdown.push(`Alpha生成: ${alphaScore.toFixed(0)}/100 (Alpha ${outcomeAlpha > 0 ? '+' : ''}${outcomeAlpha.toFixed(2)}%)`);
  } else {
    breakdown.push(`Alpha生成: ${alphaScore.toFixed(0)}/100 (无市场数据)`);
  }

  // 2.2 板块轮动踏准度（5%）
  let sectorTimingScore = 50; // 默认中性
  if (outcome.holdingAnalysis && outcome.marketContext && outcome.marketContext.sectorPerformance) {
    // 检查持仓行业是否与强势板块匹配
    const topSectors = outcome.marketContext.sectorPerformance
      .filter(s => s.return > 0)
      .slice(0, 5)
      .map(s => s.sector);

    const holdingSectors = outcome.holdingAnalysis.sectors.map(s => s.sector);
    const matchCount = holdingSectors.filter(hs => topSectors.includes(hs)).length;
    const matchRate = holdingSectors.length > 0 ? matchCount / holdingSectors.length : 0;

    sectorTimingScore = 50 + matchRate * 50;
    breakdown.push(`板块踏准: ${sectorTimingScore.toFixed(0)}/100 (${matchCount}/${holdingSectors.length}个行业在强势板块)`);
  } else {
    breakdown.push(`板块踏准: ${sectorTimingScore.toFixed(0)}/100 (无板块数据)`);
  }

  // 2.3 市场适应性（5%）
  let marketAdaptationScore = 50; // 默认中性
  if (baseline.marketContext && outcome.marketContext) {
    const baselineSentiment = baseline.marketContext.sentiment.sentiment;
    const outcomeSentiment = outcome.marketContext.sentiment.sentiment;

    // 根据市场情绪调整评分标准
    if (outcomeSentiment === 'bearish') {
      // 熊市：回撤控制更重要
      marketAdaptationScore = outcome.maxDrawdown < 10 ? 80 : outcome.maxDrawdown < 20 ? 60 : 40;
      breakdown.push(`市场适应: ${marketAdaptationScore.toFixed(0)}/100 (熊市回撤控制${outcome.maxDrawdown.toFixed(1)}%)`);
    } else if (outcomeSentiment === 'bullish') {
      // 牛市：Alpha 更重要
      const marketReturn = calculateMarketReturn(outcome.marketContext);
      const alpha = outcome.return - marketReturn;
      marketAdaptationScore = alpha > 5 ? 80 : alpha > 0 ? 60 : 40;
      breakdown.push(`市场适应: ${marketAdaptationScore.toFixed(0)}/100 (牛市Alpha ${alpha.toFixed(2)}%)`);
    } else {
      // 震荡市：胜率更重要
      marketAdaptationScore = outcome.winRate > 0.6 ? 80 : outcome.winRate > 0.5 ? 60 : 40;
      breakdown.push(`市场适应: ${marketAdaptationScore.toFixed(0)}/100 (震荡市胜率${(outcome.winRate * 100).toFixed(1)}%)`);
    }
  } else {
    breakdown.push(`市场适应: ${marketAdaptationScore.toFixed(0)}/100 (无市场数据)`);
  }

  const marketSubtotal = alphaScore * 0.10 + sectorTimingScore * 0.05 + marketAdaptationScore * 0.05;

  // ── 3. 能力提升分（20%）────────────────────────────────────────────

  // 3.1 工具效能提升（10%）
  let toolEfficiencyScore = 50;
  if (outcome.toolEfficiencyScore !== undefined) {
    toolEfficiencyScore = outcome.toolEfficiencyScore;
    breakdown.push(`工具效能: ${toolEfficiencyScore.toFixed(0)}/100`);
  } else {
    // 回退到旧算法
    toolEfficiencyScore = calculateToolQualityScore(outcome.toolStats);
    breakdown.push(`工具效能: ${toolEfficiencyScore.toFixed(0)}/100 (基于工具质量)`);
  }

  // 3.2 决策质量提升（5%）
  const baselineAvgReturn = baseline.toolStats.length > 0
    ? baseline.toolStats.reduce((sum, t) => sum + t.avg_return, 0) / baseline.toolStats.length
    : 0;
  const outcomeAvgReturn = outcome.toolStats.length > 0
    ? outcome.toolStats.reduce((sum, t) => sum + t.avg_return, 0) / outcome.toolStats.length
    : 0;

  const decisionQualityImprovement = outcomeAvgReturn - baselineAvgReturn;
  const decisionQualityScore = Math.min(100, Math.max(0, 50 + decisionQualityImprovement * 100));
  breakdown.push(`决策质量: ${decisionQualityScore.toFixed(0)}/100 (工具平均收益${outcomeAvgReturn > 0 ? '+' : ''}${(outcomeAvgReturn * 100).toFixed(2)}%)`);

  // 3.3 错误率降低（5%）
  let errorReductionScore = 50;
  if (baseline.errorRate !== undefined && outcome.errorRate !== undefined) {
    const errorReduction = baseline.errorRate - outcome.errorRate;
    errorReductionScore = Math.min(100, Math.max(0, 50 + errorReduction * 200));
    breakdown.push(`错误率降低: ${errorReductionScore.toFixed(0)}/100 (${errorReduction > 0 ? '降低' : '增加'}${Math.abs(errorReduction * 100).toFixed(1)}%)`);
  } else {
    breakdown.push(`错误率降低: ${errorReductionScore.toFixed(0)}/100 (无错误率数据)`);
  }

  const capabilitySubtotal = toolEfficiencyScore * 0.10 + decisionQualityScore * 0.05 + errorReductionScore * 0.05;

  // ── 4. 总分计算 ────────────────────────────────────────────────────
  const totalScore = Math.round(baseSubtotal + marketSubtotal + capabilitySubtotal);

  // ── 5. 评级 ────────────────────────────────────────────────────────
  let grade: 'S' | 'A' | 'B' | 'C' | 'D' | 'F';
  if (totalScore >= 90) grade = 'S';
  else if (totalScore >= 80) grade = 'A';
  else if (totalScore >= 70) grade = 'B';
  else if (totalScore >= 60) grade = 'C';
  else if (totalScore >= 50) grade = 'D';
  else grade = 'F';

  return {
    baseScore: {
      returnImprovement: returnScore,
      winRateImprovement: winRateScore,
      drawdownControl: drawdownScore,
      subtotal: baseSubtotal,
    },
    marketAdjustedScore: {
      alphaGeneration: alphaScore,
      sectorTiming: sectorTimingScore,
      marketAdaptation: marketAdaptationScore,
      subtotal: marketSubtotal,
    },
    capabilityScore: {
      toolEfficiency: toolEfficiencyScore,
      decisionQuality: decisionQualityScore,
      errorReduction: errorReductionScore,
      subtotal: capabilitySubtotal,
    },
    totalScore,
    grade,
    breakdown,
  };
}

/**
 * 计算市场平均收益率
 */
function calculateMarketReturn(marketContext: MarketContext): number {
  const indices = Object.values(marketContext.indices).filter(i => i !== null);
  if (indices.length === 0) return 0;

  const avgReturn = indices.reduce((sum, idx) => sum + (idx?.return || 0), 0) / indices.length;
  return avgReturn;
}

/**
 * 计算工具质量评分（回退算法）
 */
function calculateToolQualityScore(toolStats: ToolEfficiency[]): number {
  if (toolStats.length === 0) return 50;

  const avgWinRate = toolStats.reduce((sum, t) => sum + t.win_rate, 0) / toolStats.length;
  const avgReturn = toolStats.reduce((sum, t) => sum + t.avg_return, 0) / toolStats.length;

  return Math.min(100, Math.max(0, 50 + avgWinRate * 50 + avgReturn * 10));
}
