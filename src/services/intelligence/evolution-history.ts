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
  currentMetrics: PerformanceMetrics
): Promise<EvolutionEvaluation> {
  // 1. 计算整体评分
  const score = calculateEvolutionScore(lastEvolution.baseline, currentMetrics);

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

  // 5. 生成评估原因
  const reasons: string[] = [];

  reasons.push(`整体评分: ${score}/100`);

  if (improvement.returnDelta > 0) {
    reasons.push(`收益率提升 ${improvement.returnDelta.toFixed(2)}%`);
  } else if (improvement.returnDelta < 0) {
    reasons.push(`收益率下降 ${Math.abs(improvement.returnDelta).toFixed(2)}%`);
  }

  if (improvement.winRateDelta > 0.02) {
    reasons.push(`胜率提升 ${(improvement.winRateDelta * 100).toFixed(1)}%`);
  } else if (improvement.winRateDelta < -0.02) {
    reasons.push(`胜率下降 ${Math.abs(improvement.winRateDelta * 100).toFixed(1)}%`);
  }

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
 * 计算进化总评分（0-100）
 */
function calculateEvolutionScore(
  baseline: PerformanceMetrics,
  outcome: PerformanceMetrics
): number {
  // 1. 收益率改善（权重40%）
  const returnImprovement = baseline.return !== 0
    ? (outcome.return - baseline.return) / Math.abs(baseline.return)
    : 0;
  const returnScore = Math.min(100, Math.max(0, 50 + returnImprovement * 100));

  // 2. 胜率改善（权重30%）
  const winRateImprovement = outcome.winRate - baseline.winRate;
  const winRateScore = Math.min(100, Math.max(0, 50 + winRateImprovement * 200));

  // 3. 回撤控制（权重20%）
  const drawdownImprovement = outcome.maxDrawdown - baseline.maxDrawdown;
  const drawdownScore = Math.min(100, Math.max(0, 50 + drawdownImprovement * 100));

  // 4. 工具质量（权重10%）
  const toolQualityScore = calculateToolQualityScore(outcome.toolStats);

  // 加权平均
  const totalScore =
    returnScore * 0.4 +
    winRateScore * 0.3 +
    drawdownScore * 0.2 +
    toolQualityScore * 0.1;

  return Math.round(totalScore);
}

/**
 * 计算工具质量评分
 */
function calculateToolQualityScore(toolStats: ToolEfficiency[]): number {
  if (toolStats.length === 0) return 50;

  const avgWinRate = toolStats.reduce((sum, t) => sum + t.win_rate, 0) / toolStats.length;
  const avgReturn = toolStats.reduce((sum, t) => sum + t.avg_return, 0) / toolStats.length;

  return Math.min(100, Math.max(0, 50 + avgWinRate * 50 + avgReturn * 10));
}

/**
 * 对单个建议打分
 */
function scoreSuggestion(
  suggestion: OptimizationSuggestion,
  toolStats: ToolEfficiency[]
): SuggestionScore {
  if (suggestion.type === 'add_tool') {
    const toolName = suggestion.data?.toolName || suggestion.data?.name || 'unknown';
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
    toolName: suggestion.data?.toolName || suggestion.data?.name || 'unknown',
    score: 50,
    metrics: null,
    verdict: 'neutral',
  };
}
