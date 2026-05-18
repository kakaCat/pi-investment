/**
 * Compensator - 补偿器（控制器）
 *
 * 根据误差信号产生控制动作,调整 Agent 能力
 */

import type {
  OptimizerStrategy,
  OptimizerAction,
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
      actions: ['adjust_parameter', 'update_experience']
    };
  } else if (absGap < 5) {
    return {
      level: 'moderate',
      actions: ['add_tool', 'remove_tool', 'update_experience']
    };
  } else {
    return {
      level: 'major',
      actions: ['update_code', 'add_tool', 'remove_tool', 'update_prompt']
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
        data: {
          name: tool.tool_name,
          reason: `ROI为${tool.roi.toFixed(1)}，胜率${(tool.win_rate * 100).toFixed(0)}%，表现不佳`,
          evidence: {
            callCount: tool.call_count,
            winRate: tool.win_rate,
            avgReturn: tool.avg_return
          }
        }
      });
    }
  }

  // ── 3. 智能分类：根据弱点类型生成不同建议 ────────────────────
  for (const weakness of context.weaknesses) {
    // 3.1 风控能力问题 - 可能是纪律问题或能力缺失
    if (weakness === '风控能力') {
      // 检查是否已有止损工具
      const hasStopLossTool = context.toolStats.some(t =>
        t.tool_name.includes('stop_loss') || t.tool_name.includes('risk')
      );

      if (!hasStopLossTool) {
        // 能力缺失 → 新增工具
        suggestions.push({
          id: `opt_${idCounter++}`,
          type: 'add_tool',
          priority: 'high',
          description: '新增工具：check_stop_loss_trigger（检查止损触发）',
          reason: '缺少止损检查能力，需要自动化风控工具',
          expectedImpact: '减少亏损扩大，改善最大回撤',
          data: {
            name: 'check_stop_loss_trigger',
            description: '检查持仓是否触发止损条件',
            reason: '缺少止损检查能力，需要自动化风控工具',
            expectedImpact: '减少亏损扩大，改善最大回撤'
          }
        });
      } else {
        // 有工具但执行不力 → 修改提示词（强化纪律）
        suggestions.push({
          id: `opt_${idCounter++}`,
          type: 'update_prompt',
          priority: 'high',
          description: '强化止损纪律提示词',
          reason: '已有止损工具但执行率不足，需要强化决策纪律',
          expectedImpact: '提升止损执行率，减少情绪化决策',
          promptUpdate: {
            file: 'SOUL.md',
            section: '止损止盈原则',
            modification: '强化止损纪律，明确触发即执行的原则',
            newContent: `## 止损止盈原则（强化版）

**止损是生存底线，必须无条件执行：**
- 当 check_stop_loss_trigger 工具报告触发止损时，必须立即执行卖出
- 不得以任何理由（技术反弹、基本面改善等）推迟或忽略止损信号
- 止损执行率目标：100%

**止损触发条件：**
- 价格跌破预设止损价
- 持仓亏损超过设定阈值
- 技术形态严重破坏

**执行流程：**
1. 每日开盘前检查所有持仓的止损状态
2. 发现触发立即生成卖出决策
3. 记录止损原因和执行情况`,
            reason: '止损执行率低于60%，需要强化纪律'
          }
        });
      }
    }

    // 3.2 选股能力问题 - 通常是能力缺失
    if (weakness === '选股能力') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'add_tool',
        priority: 'medium',
        description: '新增工具：analyze_sector_rotation',
        reason: '缺少宏观视角，可能错过行业轮动机会',
        expectedImpact: '提升选股质量，增加胜率2-3%',
        data: {
          name: 'analyze_sector_rotation',
          description: '分析当前市场的行业轮动趋势',
          reason: '缺少宏观视角，可能错过行业轮动机会',
          expectedImpact: '提升选股质量，增加胜率2-3%'
        }
      });
    }

    // 3.3 决策准确性问题 - 可能是逻辑偏差或工具缺陷
    if (weakness === '决策准确性') {
      // 检查是否有低效工具
      const poorTools = context.toolStats.filter(t => t.rating <= 2);

      if (poorTools.length > 0) {
        // 工具质量问题 → 修改代码
        for (const tool of poorTools.slice(0, 2)) { // 最多处理2个
          suggestions.push({
            id: `opt_${idCounter++}`,
            type: 'update_code',
            priority: 'high',
            description: `优化工具实现：${tool.tool_name}`,
            reason: `工具评分${tool.rating}/5，胜率${(tool.win_rate * 100).toFixed(0)}%，可能存在实现缺陷`,
            expectedImpact: '提升工具准确性，减少误导决策',
            codeUpdate: {
              file: `src/infrastructure/tools/${tool.tool_name.replace(/_/g, '-')}-tool.ts`,
              function: tool.tool_name,
              issue: `工具胜率低（${(tool.win_rate * 100).toFixed(0)}%），可能存在数据处理或逻辑问题`,
              modification: '优化数据获取、计算逻辑或结果解读',
              reason: `当前ROI为${tool.roi.toFixed(2)}，需要改进实现质量`
            }
          });
        }
      } else {
        // 决策逻辑问题 → 修改提示词
        suggestions.push({
          id: `opt_${idCounter++}`,
          type: 'update_prompt',
          priority: 'medium',
          description: '优化决策逻辑提示词',
          reason: '决策错误率过高，需要调整决策框架',
          expectedImpact: '提升决策质量，降低错误率',
          promptUpdate: {
            file: 'SOUL.md',
            section: '决策逻辑',
            modification: '强化多维度验证，增加决策检查点',
            newContent: `## 决策逻辑（优化版）

**多维度验证框架：**
1. 基本面验证：财务健康、行业地位、成长性
2. 技术面验证：趋势方向、支撑压力、量价配合
3. 风险评估：止损位置、仓位大小、市场环境

**决策检查点：**
- 买入前：至少2个维度支持 + 风险可控
- 持有中：定期复盘，条件变化及时调整
- 卖出时：明确触发条件，避免情绪化

**避免常见错误：**
- 不追高：涨幅>10%需谨慎
- 不抄底：下跌趋势中不轻易买入
- 不恋战：止损触发必须执行`,
            reason: '决策错误率超过40%，需要系统化决策流程'
          }
        });
      }
    }

    // 3.4 整体策略问题 - 需要更深层次的调整
    if (weakness === '整体策略') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'update_prompt',
        priority: 'high',
        description: '调整整体投资策略',
        reason: '收益率持续下降，需要重新审视策略方向',
        expectedImpact: '扭转下降趋势，重建盈利能力',
        promptUpdate: {
          file: 'SOUL.md',
          section: '投资策略',
          modification: '根据市场环境调整策略重心',
          newContent: `## 投资策略（调整版）

**当前市场环境评估：**
- 趋势判断：震荡/上升/下降
- 热点板块：识别资金流向
- 风险偏好：市场情绪指标

**策略调整方向：**
- 震荡市：降低仓位，高抛低吸，快进快出
- 上升市：顺势而为，持股为主，适度追涨
- 下降市：空仓为主，严格止损，等待转机

**执行原则：**
- 顺势而为，不逆势操作
- 控制回撤优先于追求收益
- 保持灵活，根据市场变化及时调整`,
          reason: '收益率持续下降，需要适应市场环境'
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
    context,
    recentEvolutions,
    experienceSummary
  );

  // ── 6. 优先级排序：按预期收益和优先级排序 ────────────────────────
  const sortedSuggestions = sortSuggestionsByPriority(filteredSuggestions, context);

  return sortedSuggestions;
}

/**
 * 应用智能过滤
 */
function applyIntelligentFilters(
  suggestions: OptimizationSuggestion[],
  context: OptimizationContext,
  recentEvolutions?: EvolutionHistory[],
  experienceSummary?: ExperienceSummary | null
): OptimizationSuggestion[] {
  let filtered = suggestions;

  // 过滤1: 智能去重（只过滤成功的建议，失败的允许重试）
  if (recentEvolutions && recentEvolutions.length > 0) {
    const recentSuggestions = recentEvolutions.flatMap(e => e.suggestions);
    console.log(`[补偿器] 历史建议数量: ${recentSuggestions.length}`, recentSuggestions.map(s => s.data?.toolName || s.type));

    filtered = filtered.filter(s => {
      // 查找历史中相同的建议
      const matchingHistory = recentEvolutions.filter(e =>
        e.suggestions.some(prev =>
          prev.type === s.type &&
          prev.data?.toolName === s.data?.toolName
        )
      );

      if (matchingHistory.length === 0) {
        return true; // 没有历史记录，保留
      }

      // 检查最近一次尝试的评分
      const lastAttempt = matchingHistory[0];
      const lastScore = lastAttempt.evaluation?.score;

      // 策略：
      // 1. 评分 >= 60: 成功，不重复尝试
      // 2. 评分 < 40: 失败，允许重试（可能是实现问题）
      // 3. 评分 40-60: 一般，检查尝试次数（最多重试1次）
      if (lastScore !== undefined) {
        if (lastScore >= 60) {
          console.log(`[补偿器] 过滤成功建议: ${s.description} (上次评分: ${lastScore})`);
          return false;
        } else if (lastScore < 40 && matchingHistory.length < 2) {
          console.log(`[补偿器] 允许重试失败建议: ${s.description} (上次评分: ${lastScore}, 尝试次数: ${matchingHistory.length})`);
          return true;
        } else if (lastScore >= 40 && lastScore < 60 && matchingHistory.length >= 2) {
          console.log(`[补偿器] 过滤多次尝试的一般建议: ${s.description} (上次评分: ${lastScore}, 尝试次数: ${matchingHistory.length})`);
          return false;
        }
      }

      // 没有评分信息，检查尝试次数（最多3次）
      if (matchingHistory.length >= 3) {
        console.log(`[补偿器] 过滤多次尝试建议: ${s.description} (尝试次数: ${matchingHistory.length})`);
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

  // 过滤3: 根据差距大小、历史评分和市场环境调整建议数量
  let maxSuggestions = 3; // 默认

  // 3.1 根据差距大小调整
  const gap = Math.abs(context.level === 'major' ? 10 : context.level === 'moderate' ? 5 : 2);
  if (gap > 20) {
    maxSuggestions = 5; // 差距大，需要激进调整
    console.log(`[补偿器] 差距 ${gap}% > 20%，采用激进策略（最多5个建议）`);
  } else if (gap < 5) {
    maxSuggestions = 2; // 差距小，只需微调
    console.log(`[补偿器] 差距 ${gap}% < 5%，采用保守策略（最多2个建议）`);
  }

  // 3.2 根据历史评分调整
  if (recentEvolutions && recentEvolutions.length > 0) {
    const recentScores = recentEvolutions
      .map(e => e.evaluation?.score)
      .filter(s => s !== undefined) as number[];

    if (recentScores.length > 0) {
      const avgRecentScore = recentScores.reduce((a, b) => a + b, 0) / recentScores.length;

      // 历史评分低，说明之前的建议效果不好，应该更保守
      if (avgRecentScore < 40) {
        maxSuggestions = Math.min(maxSuggestions, 2);
        console.log(`[补偿器] 最近平均评分: ${avgRecentScore.toFixed(1)}/100，限制为最多2个建议`);
      } else if (avgRecentScore > 70) {
        // 历史评分高，说明方向对了，可以更激进
        maxSuggestions = Math.min(maxSuggestions + 1, 5);
        console.log(`[补偿器] 最近平均评分: ${avgRecentScore.toFixed(1)}/100，允许最多${maxSuggestions}个建议`);
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

/**
 * 按优先级和预期收益排序建议
 */
function sortSuggestionsByPriority(
  suggestions: OptimizationSuggestion[],
  context: OptimizationContext
): OptimizationSuggestion[] {
  return suggestions.sort((a, b) => {
    // 1. 优先级权重
    const priorityWeight = { high: 3, medium: 2, low: 1 };
    const priorityDiff = priorityWeight[a.priority] - priorityWeight[b.priority];
    if (priorityDiff !== 0) return -priorityDiff; // 高优先级在前

    // 2. 类型权重（先移除低效，再添加新能力）
    const typeWeight: Record<OptimizerAction, number> = {
      remove_tool: 5,         // 移除低效工具优先（立即止损）
      update_code: 4,         // 修复现有工具次之
      add_tool: 3,            // 添加新工具
      adjust_parameter: 2,    // 调整参数
      update_prompt: 1,       // 调整提示词
      update_experience: 0    // 更新经验最后
    };
    const typeDiff = typeWeight[a.type] - typeWeight[b.type];
    if (typeDiff !== 0) return -typeDiff;

    // 3. 预期收益（从描述中提取数字）
    const extractImpact = (s: OptimizationSuggestion): number => {
      // 尝试从 expectedImpact 中提取百分比数字
      const match = s.expectedImpact?.match(/(\d+(?:\.\d+)?)\s*%/);
      if (match) return parseFloat(match[1]);

      // 尝试从 data 中提取 pnlImpact
      if (s.data?.pnlImpact) return s.data.pnlImpact / 1000; // 转换为百分比量级

      // 根据类型给默认权重
      if (s.type === 'remove_tool') return 2; // 移除低效工具预期收益2%
      if (s.type === 'add_tool') return 3;    // 添加新工具预期收益3%
      if (s.type === 'update_code') return 2.5;
      return 1;
    };

    const impactA = extractImpact(a);
    const impactB = extractImpact(b);
    return impactB - impactA; // 高收益在前
  });
}

