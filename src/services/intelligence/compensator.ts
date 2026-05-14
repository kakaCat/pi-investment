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

