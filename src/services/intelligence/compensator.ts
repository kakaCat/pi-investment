/**
 * Compensator - 补偿器（控制器）
 *
 * 根据误差信号产生控制动作,调整 Agent 能力
 */

import type {
  OptimizerStrategy,
  OptimizationSuggestion,
  ToolEfficiency,
  EvolutionHistory,
  ExperienceSummary,
} from '../../types/evolution.js';

/**
 * 确定优化策略
 */
export function determineOptimizerStrategy(gap: number): OptimizerStrategy {
  const absGap = Math.abs(gap);

  if (absGap < 2) {
    return {
      level: 'minor',
      actions: ['adjust_parameters', 'update_experience']
    };
  } else if (absGap < 5) {
    return {
      level: 'moderate',
      actions: ['add_tools', 'remove_tools', 'update_experience']
    };
  } else {
    return {
      level: 'major',
      actions: ['redesign_strategy', 'add_tools', 'remove_tools', 'update_algorithms']
    };
  }
}

interface OptimizationContext {
  level: 'minor' | 'moderate' | 'major';
  toolStats: ToolEfficiency[];
  weaknesses: string[];
  newPatterns?: Array<{
    pattern: string;
    winRate: number;
    avgReturn: number;
  }>;
}

/**
 * 生成优化建议（增强版：基于历史学习）
 */
export function generateOptimizationSuggestions(
  context: OptimizationContext,
  recentEvolutions?: EvolutionHistory[],
  experienceSummary?: ExperienceSummary | null
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];
  let idCounter = 1;

  // ── 1. 基于历史：优先移除上次评分低的工具 ──────────────────────────
  if (recentEvolutions && recentEvolutions.length > 0) {
    const lastEvolution = recentEvolutions[0];
    const lastEvaluation = lastEvolution.evaluation;

    if (lastEvaluation?.ineffectiveTools && lastEvaluation.ineffectiveTools.length > 0) {
      for (const toolName of lastEvaluation.ineffectiveTools) {
        const toolScore = lastEvaluation.suggestionScores.find(s => s.toolName === toolName);

        suggestions.push({
          id: `opt_${idCounter++}`,
          type: 'remove_tool',
          priority: 'high',
          description: `移除无效工具：${toolName}`,
          reason: `上次进化评分: ${toolScore?.score || 0}/100，${toolScore?.verdict || 'poor'}`,
          expectedImpact: '减少噪音，提升决策质量',
          data: { toolName, evidence: toolScore?.metrics }
        });
      }
    }
  }

  // ── 2. 移除低效工具（ROI < 0 或 rating = 1）──────────────────────
  for (const tool of context.toolStats) {
    if (tool.roi < 0 || tool.rating === 1) {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'remove_tool',
        priority: 'high',
        description: `移除工具：${tool.tool_name}`,
        reason: `ROI为${tool.roi.toFixed(1)}，胜率${(tool.win_rate * 100).toFixed(0)}%，表现不佳`,
        expectedImpact: '减少噪音，降低决策错误率',
        data: { toolName: tool.tool_name, evidence: tool }
      });
    }
  }

  // ── 3. 根据弱点新增工具 ────────────────────────────────────────
  for (const weakness of context.weaknesses) {
    if (weakness === '风控能力') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'add_tool',
        priority: 'high',
        description: '新增工具：check_stop_loss_trigger（检查止损触发）',
        reason: '止损执行率不足，需要自动检查止损条件',
        expectedImpact: '减少亏损扩大，改善最大回撤',
        data: {
          toolName: 'check_stop_loss_trigger',
          description: '检查持仓是否触发止损条件'
        }
      });
    }

    if (weakness === '选股能力') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'add_tool',
        priority: 'medium',
        description: '新增工具：analyze_sector_rotation',
        reason: '缺少宏观视角，可能错过行业轮动机会',
        expectedImpact: '提升选股质量，增加胜率2-3%',
        data: {
          toolName: 'analyze_sector_rotation',
          description: '分析当前市场的行业轮动趋势'
        }
      });
    }
  }

  // ── 4. 更新经验库 ──────────────────────────────────────────────
  if (context.newPatterns && context.newPatterns.length > 0) {
    for (const pattern of context.newPatterns) {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'update_experience',
        priority: pattern.winRate < 0.4 ? 'high' : 'medium',
        description: `更新经验：${pattern.pattern}`,
        reason: `发现新模式，胜率${(pattern.winRate * 100).toFixed(0)}%，平均收益${(pattern.avgReturn * 100).toFixed(1)}%`,
        expectedImpact: pattern.winRate < 0.4 ? '避免重复错误' : '复制成功经验',
        data: { pattern }
      });
    }
  }

  // ── 5. 智能过滤：基于历史和经验 ────────────────────────────────
  const filteredSuggestions = applyIntelligentFilters(
    suggestions,
    recentEvolutions,
    experienceSummary
  );

  return filteredSuggestions;
}

/**
 * 应用智能过滤
 */
function applyIntelligentFilters(
  suggestions: OptimizationSuggestion[],
  recentEvolutions?: EvolutionHistory[],
  experienceSummary?: ExperienceSummary | null
): OptimizationSuggestion[] {
  let filtered = suggestions;

  // 过滤1: 避免重复建议（检查最近3次）
  if (recentEvolutions && recentEvolutions.length > 0) {
    const recentSuggestions = recentEvolutions.flatMap(e => e.suggestions);

    filtered = filtered.filter(s => {
      const alreadyTried = recentSuggestions.some(prev =>
        prev.type === s.type &&
        prev.data?.toolName === s.data?.toolName
      );

      if (alreadyTried) {
        console.log(`[补偿器] 过滤重复建议: ${s.description}`);
        return false;
      }

      return true;
    });
  }

  // 过滤2: 过滤不推荐的工具（根据经验总结）
  if (experienceSummary) {
    const notRecommendedTools = experienceSummary.toolPatterns
      .filter(p => p.recommendation === 'not_recommended')
      .map(p => p.toolName);

    filtered = filtered.filter(s => {
      if (s.type === 'add_tool') {
        const toolName = s.data?.toolName;
        if (notRecommendedTools.includes(toolName)) {
          console.log(`[补偿器] 过滤不推荐工具: ${toolName} (历史平均评分: ${
            experienceSummary.toolPatterns.find(p => p.toolName === toolName)?.avgScore
          })`);
          return false;
        }
      }
      return true;
    });
  }

  // 过滤3: 根据最近3次评分调整激进程度并限制数量
  let maxSuggestions = 3; // 默认

  if (recentEvolutions && recentEvolutions.length > 0) {
    const recentScores = recentEvolutions
      .map(e => e.evaluation?.score)
      .filter(s => s !== undefined) as number[];

    if (recentScores.length > 0) {
      const avgRecentScore = recentScores.reduce((a, b) => a + b, 0) / recentScores.length;

      if (avgRecentScore < 40) {
        maxSuggestions = 2; // 保守
        console.log(`[补偿器] 最近平均评分: ${avgRecentScore.toFixed(1)}/100，采用保守策略（最多2个建议）`);
      } else if (avgRecentScore > 70) {
        maxSuggestions = 5; // 激进
        console.log(`[补偿器] 最近平均评分: ${avgRecentScore.toFixed(1)}/100，采用激进策略（最多5个建议）`);
      } else {
        console.log(`[补偿器] 最近平均评分: ${avgRecentScore.toFixed(1)}/100，采用正常策略（最多3个建议）`);
      }
    }
  }

  // 限制建议数量
  if (filtered.length > maxSuggestions) {
    console.log(`[补偿器] 限制建议数量: ${filtered.length} → ${maxSuggestions}`);
    filtered = filtered.slice(0, maxSuggestions);
  }

  return filtered;
}

