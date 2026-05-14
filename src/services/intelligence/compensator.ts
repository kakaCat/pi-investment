/**
 * Compensator - 补偿器（控制器）
 *
 * 根据误差信号产生控制动作,调整 Agent 能力
 */

import type {
  OptimizerStrategy,
  OptimizationSuggestion,
  ToolEfficiency
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
 * 生成优化建议
 */
export function generateOptimizationSuggestions(
  context: OptimizationContext
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];
  let idCounter = 1;

  // 1. 移除低效工具（ROI < 0 或 rating = 1）
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

  // 2. 根据弱点新增工具
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

  // 3. 更新经验库
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

  return suggestions;
}
