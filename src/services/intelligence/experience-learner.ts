/**
 * Experience Learner - 经验学习模块
 *
 * 从进化历史中提取经验规律、工具模式和反模式
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync } from 'fs';
import type {
  EvolutionHistory,
  ExperienceSummary,
  ToolPattern,
  SuggestionTypeStat,
  Learning,
  AntiPattern,
} from '../../types/evolution.js';

// ─── 生成经验总结 ────────────────────────────────────────────────────────────

/**
 * 从所有历史中生成经验总结
 */
export async function generateExperienceSummary(
  allHistory: EvolutionHistory[]
): Promise<ExperienceSummary> {
  // 只处理有评估结果的历史
  const evaluatedHistory = allHistory.filter(h => h.evaluation);

  const toolPatterns = extractToolPatterns(evaluatedHistory);
  const suggestionTypeStats = extractSuggestionTypeStats(evaluatedHistory);
  const learnings = extractLearnings(evaluatedHistory);
  const antiPatterns = extractAntiPatterns(evaluatedHistory);

  return {
    version: '1.0',
    lastUpdated: new Date().toISOString(),
    totalEvolutions: evaluatedHistory.length,
    toolPatterns,
    suggestionTypeStats,
    learnings,
    antiPatterns,
  };
}

/**
 * 加载经验总结
 */
export async function loadExperienceSummary(
  piDir: string
): Promise<ExperienceSummary | null> {
  const experiencePath = path.join(piDir, 'evolution/experience-summary.json');

  if (!existsSync(experiencePath)) {
    return null;
  }

  try {
    const content = await fs.readFile(experiencePath, 'utf-8');
    return JSON.parse(content) as ExperienceSummary;
  } catch (e) {
    console.error('[经验学习] 加载失败:', e);
    return null;
  }
}

/**
 * 保存经验总结
 */
export async function saveExperienceSummary(
  summary: ExperienceSummary,
  piDir: string
): Promise<void> {
  const experiencePath = path.join(piDir, 'evolution/experience-summary.json');

  try {
    await fs.writeFile(experiencePath, JSON.stringify(summary, null, 2), 'utf-8');
  } catch (e) {
    console.error('[经验学习] 保存失败:', e);
  }
}

// ─── 提取工具效果模式 ────────────────────────────────────────────────────────

/**
 * 提取工具效果模式
 */
function extractToolPatterns(history: EvolutionHistory[]): ToolPattern[] {
  const toolMap = new Map<string, {
    addedCount: number;
    removedCount: number;
    scores: number[];
  }>();

  for (const evolution of history) {
    if (!evolution.evaluation) continue;

    for (const suggestionScore of evolution.evaluation.suggestionScores) {
      const toolName = suggestionScore.toolName;

      if (!toolMap.has(toolName)) {
        toolMap.set(toolName, {
          addedCount: 0,
          removedCount: 0,
          scores: [],
        });
      }

      const toolData = toolMap.get(toolName)!;

      // 统计添加/移除次数
      const suggestion = evolution.suggestions.find(s => s.id === suggestionScore.suggestionId);
      if (suggestion?.type === 'add_tool') {
        toolData.addedCount++;
        toolData.scores.push(suggestionScore.score);
      } else if (suggestion?.type === 'remove_tool') {
        toolData.removedCount++;
      }
    }
  }

  // 转换为 ToolPattern 数组
  const patterns: ToolPattern[] = [];
  for (const [toolName, data] of Array.from(toolMap.entries())) {
    const avgScore = data.scores.length > 0
      ? data.scores.reduce((a, b) => a + b, 0) / data.scores.length
      : 0;

    const successRate = data.scores.length > 0
      ? data.scores.filter(s => s > 60).length / data.scores.length
      : 0;

    let recommendation: 'highly_recommended' | 'recommended' | 'neutral' | 'not_recommended';
    if (avgScore >= 80 && successRate >= 0.8) recommendation = 'highly_recommended';
    else if (avgScore >= 60 && successRate >= 0.6) recommendation = 'recommended';
    else if (avgScore >= 40) recommendation = 'neutral';
    else recommendation = 'not_recommended';

    patterns.push({
      toolName,
      addedCount: data.addedCount,
      removedCount: data.removedCount,
      avgScore: Math.round(avgScore),
      successRate,
      bestContext: 'unknown', // TODO: 从市场环境中推断
      recommendation,
    });
  }

  return patterns.sort((a, b) => b.avgScore - a.avgScore);
}

/**
 * 提取建议类型统计
 */
function extractSuggestionTypeStats(history: EvolutionHistory[]): SuggestionTypeStat[] {
  const typeMap = new Map<string, { scores: number[]; count: number }>();

  for (const evolution of history) {
    if (!evolution.evaluation) continue;

    for (const suggestionScore of evolution.evaluation.suggestionScores) {
      const suggestion = evolution.suggestions.find(s => s.id === suggestionScore.suggestionId);
      if (!suggestion) continue;

      const type = suggestion.type;
      if (!typeMap.has(type)) {
        typeMap.set(type, { scores: [], count: 0 });
      }

      const typeData = typeMap.get(type)!;
      typeData.scores.push(suggestionScore.score);
      typeData.count++;
    }
  }

  const stats: SuggestionTypeStat[] = [];
  for (const [type, data] of Array.from(typeMap.entries())) {
    if (type !== 'add_tool' && type !== 'remove_tool' && type !== 'update_experience') continue;

    const avgScore = data.scores.length > 0
      ? data.scores.reduce((a, b) => a + b, 0) / data.scores.length
      : 0;

    const successRate = data.scores.length > 0
      ? data.scores.filter(s => s > 60).length / data.scores.length
      : 0;

    stats.push({
      type: type as 'add_tool' | 'remove_tool' | 'update_experience',
      totalCount: data.count,
      avgScore: Math.round(avgScore),
      successRate,
    });
  }

  return stats;
}

/**
 * 提取经验规律
 */
function extractLearnings(history: EvolutionHistory[]): Learning[] {
  const learnings: Learning[] = [];

  // 规律1: 高评分工具的共性
  const excellentTools = history
    .flatMap(h => h.evaluation?.suggestionScores || [])
    .filter(s => s.verdict === 'excellent');

  if (excellentTools.length >= 2) {
    learnings.push({
      id: 'learning_001',
      rule: '高胜率工具（>70%）通常能显著提升整体收益',
      confidence: 0.85,
      evidence: excellentTools.map(t => t.suggestionId),
      examples: excellentTools.map(t =>
        `${t.toolName}: 胜率${t.metrics ? (t.metrics.winRate * 100).toFixed(1) : '?'}%, 评分${t.score}`
      ),
    });
  }

  // 规律2: 移除低效工具的效果
  const removedTools = history
    .filter(h => h.evaluation && h.evaluation.score > 60)
    .flatMap(h => h.suggestions.filter(s => s.type === 'remove_tool'));

  if (removedTools.length >= 2) {
    learnings.push({
      id: 'learning_002',
      rule: '及时移除低胜率工具（<50%）能减少噪音，提升决策质量',
      confidence: 0.75,
      evidence: removedTools.map(t => t.id),
      examples: removedTools.map(t => `移除 ${t.data?.toolName || t.data?.name || 'unknown'}`),
    });
  }

  return learnings;
}

/**
 * 识别反模式
 */
function extractAntiPatterns(history: EvolutionHistory[]): AntiPattern[] {
  const antiPatterns: AntiPattern[] = [];

  // 反模式1: 重复添加相同的无效工具
  const repeatedFailures = new Map<string, number>();

  for (const evolution of history) {
    if (!evolution.evaluation) continue;

    for (const score of evolution.evaluation.suggestionScores) {
      if (score.verdict === 'poor' || score.verdict === 'harmful') {
        repeatedFailures.set(
          score.toolName,
          (repeatedFailures.get(score.toolName) || 0) + 1
        );
      }
    }
  }

  for (const [toolName, count] of Array.from(repeatedFailures.entries())) {
    if (count >= 2) {
      antiPatterns.push({
        pattern: `重复添加低效工具: ${toolName}`,
        reason: `该工具在${count}次进化中均表现不佳`,
        occurrences: count,
        avgNegativeImpact: -5,
      });
    }
  }

  // 反模式2: 过度进化（单次添加过多工具）
  const overEvolutions = history.filter(h =>
    h.suggestions.filter(s => s.type === 'add_tool').length > 5
  );

  if (overEvolutions.length > 0) {
    antiPatterns.push({
      pattern: '单次进化添加过多工具（>5个）',
      reason: '难以评估单个工具的效果，增加系统复杂度',
      occurrences: overEvolutions.length,
      avgNegativeImpact: -3,
    });
  }

  return antiPatterns;
}
