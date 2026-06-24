/**
 * Evolution History - 进化历史管理
 *
 * 负责进化历史的保存、加载、评估和打分
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync } from 'fs';
import type {
  EvolutionHistory,
  OptimizationSuggestion,
  ToolEfficiency,
  SuggestionScore,
} from '../../types/evolution.js';
import type { MarketContext } from '../../types/market-context.js';
import type { HoldingDimensionAnalysis } from '../../types/holding-analysis.js';
import {
  calculateEnhancedEvolutionScore,
  type EnhancedPerformanceMetrics,
  type DetailedEvolutionScore,
} from './evolution-scorer.js';

// ─── 类型定义 ────────────────────────────────────────────────────────────────

interface PerformanceMetrics {
  return: number;
  winRate: number;
  maxDrawdown: number;
  toolStats: ToolEfficiency[];
}

interface EvolutionEvaluation {
  score: number;
  effective: boolean;
  effectiveTools: string[];
  ineffectiveTools: string[];
  reasons: string[];
  suggestionScores: SuggestionScore[];
  improvement: {
    returnDelta: number;
    winRateDelta: number;
    maxDrawdownDelta: number;
  };
}

// ─── 保存进化历史 ────────────────────────────────────────────────────────────

/**
 * 保存本次进化历史（baseline）
 */
export async function saveEvolutionHistory(
  suggestions: OptimizationSuggestion[],
  applied: string[],
  baseline: PerformanceMetrics,
  piDir: string
): Promise<string> {
  const evolutionId = new Date().toISOString().split('T')[0];
  const branchName = `evolution/${evolutionId}`;

  const historyDir = path.join(piDir, 'evolution/history');
  await fs.mkdir(historyDir, { recursive: true });

  const historyPath = path.join(historyDir, `${evolutionId}.json`);

  // 检查文件是否已存在（同一天多次运行的情况）
  let existingHistory: EvolutionHistory | null = null;
  if (existsSync(historyPath)) {
    try {
      const content = await fs.readFile(historyPath, 'utf-8');
      existingHistory = JSON.parse(content) as EvolutionHistory;
    } catch (e) {
      console.warn('[进化历史] 读取现有历史失败，将覆盖:', e);
    }
  }

  const history: EvolutionHistory = {
    evolutionId,
    date: new Date().toISOString(),
    branchName,
    suggestions,
    applied,
    baseline: {
      return: baseline.return,
      winRate: baseline.winRate,
      maxDrawdown: baseline.maxDrawdown,
      toolStats: baseline.toolStats,
    },
    // 保留已有的 outcome 和 evaluation（如果存在）
    outcome: existingHistory?.outcome,
    evaluation: existingHistory?.evaluation,
  };

  await fs.writeFile(historyPath, JSON.stringify(history, null, 2), 'utf-8');

  return evolutionId;
}

// ─── 加载进化历史 ────────────────────────────────────────────────────────────

/**
 * 加载最近N次进化历史
 */
export async function loadRecentEvolutions(
  piDir: string,
  limit: number = 3
): Promise<EvolutionHistory[]> {
  const historyDir = path.join(piDir, 'evolution/history');

  if (!existsSync(historyDir)) {
    return [];
  }

  try {
    const files = await fs.readdir(historyDir);
    const jsonFiles = files.filter(f => f.endsWith('.json')).sort().reverse();

    const recentFiles = jsonFiles.slice(0, limit);
    const histories: EvolutionHistory[] = [];

    for (const file of recentFiles) {
      const content = await fs.readFile(path.join(historyDir, file), 'utf-8');
      const history = JSON.parse(content) as EvolutionHistory;
      histories.push(history);
    }

    return histories;
  } catch (e) {
    console.error('[进化历史] 加载失败:', e);
    return [];
  }
}

// ─── 评估进化效果 ────────────────────────────────────────────────────────────

/**
 * 评估并打分最近一次进化
 */
export async function evaluateLastEvolution(
  lastEvolution: EvolutionHistory,
  currentMetrics: PerformanceMetrics,
  marketContext?: MarketContext,
  holdingAnalysis?: HoldingDimensionAnalysis,
  toolEfficiencyScore?: number,
  errorRate?: number
): Promise<EvolutionEvaluation> {
  // 构建增强的性能指标
  const baselineEnhanced: EnhancedPerformanceMetrics = {
    ...lastEvolution.baseline,
  };

  const outcomeEnhanced: EnhancedPerformanceMetrics = {
    ...currentMetrics,
    marketContext,
    holdingAnalysis,
    toolEfficiencyScore,
    errorRate,
  };

  // 1. 使用优化后的评分算法
  const detailedScore = calculateEnhancedEvolutionScore(baselineEnhanced, outcomeEnhanced);
  const score = detailedScore.totalScore;

  // 2. 计算指标变化
  const improvement = {
    returnDelta: currentMetrics.return - lastEvolution.baseline.return,
    winRateDelta: currentMetrics.winRate - lastEvolution.baseline.winRate,
    maxDrawdownDelta: currentMetrics.maxDrawdown - lastEvolution.baseline.maxDrawdown,
  };

  // 3. 判断整体效果
  const effective = score >= 60;

  // 4. 评估每个建议的效果并打分
  const suggestionScores: SuggestionScore[] = [];
  const effectiveTools: string[] = [];
  const ineffectiveTools: string[] = [];

  for (const suggestionId of lastEvolution.applied) {
    const suggestion = lastEvolution.suggestions.find(s => s.id === suggestionId);
    if (!suggestion) continue;

    const suggestionScore = scoreSuggestion(suggestion, currentMetrics.toolStats);
    suggestionScores.push(suggestionScore);

    if (suggestion.type === 'add_tool') {
      if (suggestionScore.verdict === 'excellent' || suggestionScore.verdict === 'good') {
        effectiveTools.push(suggestionScore.toolName);
      } else if (suggestionScore.verdict === 'poor' || suggestionScore.verdict === 'harmful') {
        ineffectiveTools.push(suggestionScore.toolName);
      }
    }
  }

  // 5. 生成评估原因（使用详细评分的breakdown）
  const reasons: string[] = [];

  reasons.push(`整体评分: ${score}/100`);
  reasons.push(...detailedScore.breakdown);

  if (effectiveTools.length > 0) {
    reasons.push(`有效工具: ${effectiveTools.join(', ')}`);
  }

  if (ineffectiveTools.length > 0) {
    reasons.push(`无效工具: ${ineffectiveTools.join(', ')}`);
  }

  return {
    score,
    effective,
    effectiveTools,
    ineffectiveTools,
    reasons,
    improvement,
    suggestionScores,
  };
}

/**
 * 更新历史记录的outcome和evaluation
 */
export async function updateEvolutionOutcome(
  evolutionId: string,
  outcome: PerformanceMetrics,
  evaluation: EvolutionEvaluation,
  piDir: string
): Promise<void> {
  const historyPath = path.join(piDir, 'evolution/history', `${evolutionId}.json`);

  if (!existsSync(historyPath)) {
    console.warn(`[进化历史] 历史文件不存在: ${evolutionId}`);
    return;
  }

  try {
    const content = await fs.readFile(historyPath, 'utf-8');
    const history = JSON.parse(content) as EvolutionHistory;

    history.outcome = {
      return: outcome.return,
      winRate: outcome.winRate,
      maxDrawdown: outcome.maxDrawdown,
      toolStats: outcome.toolStats,
      improvement: evaluation.improvement,
    };

    history.evaluation = {
      score: evaluation.score,
      effective: evaluation.effective,
      effectiveTools: evaluation.effectiveTools,
      ineffectiveTools: evaluation.ineffectiveTools,
      reasons: evaluation.reasons,
      suggestionScores: evaluation.suggestionScores,
    };

    await fs.writeFile(historyPath, JSON.stringify(history, null, 2), 'utf-8');
  } catch (e) {
    console.error('[进化历史] 更新失败:', e);
  }
}

// ─── 评分算法 ────────────────────────────────────────────────────────────────

/**
 * 对单个建议打分
 */
function scoreSuggestion(
  suggestion: OptimizationSuggestion,
  toolStats: ToolEfficiency[]
): SuggestionScore {
  if (suggestion.type === 'add_tool') {
    const toolName = (suggestion as any).data?.toolName || (suggestion as any).data?.name || 'unknown';
    const toolStat = toolStats.find(t => t.tool_name === toolName);

    if (!toolStat) {
      return {
        suggestionId: suggestion.id,
        toolName,
        score: 0,
        metrics: null,
        verdict: 'poor',
      };
    }

    // 评分因素：调用次数、胜率、平均收益
    const callScore = Math.min(30, toolStat.call_count * 2); // 最多30分
    const winRateScore = toolStat.win_rate * 40; // 最多40分
    const returnScore = Math.min(30, Math.max(0, 15 + toolStat.avg_return * 30)); // 最多30分

    const score = callScore + winRateScore + returnScore;

    let verdict: 'excellent' | 'good' | 'neutral' | 'poor' | 'harmful';
    if (score >= 80) verdict = 'excellent';
    else if (score >= 60) verdict = 'good';
    else if (score >= 40) verdict = 'neutral';
    else if (score >= 20) verdict = 'poor';
    else verdict = 'harmful';

    return {
      suggestionId: suggestion.id,
      toolName,
      score: Math.round(score),
      metrics: {
        callCount: toolStat.call_count,
        winRate: toolStat.win_rate,
        avgReturn: toolStat.avg_return,
        contribution: toolStat.avg_return * toolStat.call_count,
      },
      verdict,
    };
  }

  // remove_tool 和其他类型的评分逻辑（简化处理）
  return {
    suggestionId: suggestion.id,
    toolName: (suggestion as any).data?.toolName || (suggestion as any).data?.name || 'unknown',
    score: 50,
    metrics: null,
    verdict: 'neutral',
  };
}
