/**
 * Evolution Reporter - 进化报告生成器
 *
 * 生成结构化的进化报告
 */

import type {
  EvolutionReport,
  AttributionResult,
  ToolEfficiency,
  OptimizationSuggestion,
  EvolutionHistory,
  ExperienceSummary
} from '../../types/evolution.js';

interface ReportInput {
  period: string;
  performance: {
    target: number;
    actual: number;
    gap: number;
    market: number;
    winRate: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  attribution: AttributionResult;
  toolStats: ToolEfficiency[];
  suggestions: OptimizationSuggestion[];
  successPatterns?: Array<{
    pattern: string;
    count: number;
    winRate: number;
    avgReturn: number;
  }>;
  failurePatterns?: Array<{
    pattern: string;
    count: number;
    winRate: number;
    avgLoss: number;
  }>;
  recentHistories?: EvolutionHistory[];
  experience?: ExperienceSummary;
}

/**
 * 生成进化报告
 */
export function generateEvolutionReport(input: ReportInput): EvolutionReport {
  return {
    period: input.period,
    performance: input.performance,
    attribution: input.attribution,
    sessionAnalysis: {
      totalSessions: input.toolStats.reduce((sum, t) => sum + t.decisions_after_call, 0),
      successPatterns: input.successPatterns || [],
      failurePatterns: input.failurePatterns || []
    },
    toolEfficiency: input.toolStats,
    suggestions: input.suggestions
  };
}

/**
 * 格式化为 Markdown
 */
export function formatReportAsMarkdown(report: EvolutionReport, recentHistories?: EvolutionHistory[], experience?: ExperienceSummary): string {
  const lines: string[] = [];

  // 标题
  lines.push(`# 进化报告 ${report.period}`);
  lines.push('');

  // 历史评分趋势（如果有历史数据）
  if (recentHistories && recentHistories.length > 0) {
    lines.push('## 📈 进化历史趋势');
    lines.push('');

    const historiesWithScores = recentHistories.filter(h => h.evaluation?.score !== undefined);
    if (historiesWithScores.length > 0) {
      lines.push('| 日期 | 评分 | 收益变化 | 胜率变化 | 回撤变化 |');
      lines.push('|------|------|----------|----------|----------|');

      for (const h of historiesWithScores) {
        const eval_ = h.evaluation!;
        const outcome = h.outcome;

        // 格式化日期（只显示日期部分）
        const dateStr = h.date.split('T')[0];

        if (outcome?.improvement) {
          const returnDelta = outcome.improvement.returnDelta >= 0
            ? `+${outcome.improvement.returnDelta.toFixed(1)}%`
            : `${outcome.improvement.returnDelta.toFixed(1)}%`;
          const winRateDelta = outcome.improvement.winRateDelta >= 0
            ? `+${(outcome.improvement.winRateDelta * 100).toFixed(0)}%`
            : `${(outcome.improvement.winRateDelta * 100).toFixed(0)}%`;
          const drawdownDelta = outcome.improvement.maxDrawdownDelta >= 0
            ? `+${outcome.improvement.maxDrawdownDelta.toFixed(1)}%`
            : `${outcome.improvement.maxDrawdownDelta.toFixed(1)}%`;

          const scoreEmoji = eval_.score >= 80 ? '🌟' : eval_.score >= 60 ? '✅' : eval_.score >= 40 ? '➖' : '⚠️';

          lines.push(`| ${dateStr} | ${scoreEmoji} ${eval_.score} | ${returnDelta} | ${winRateDelta} | ${drawdownDelta} |`);
        } else {
          // 即使没有 improvement 数据，也显示评分
          const scoreEmoji = eval_.score >= 80 ? '🌟' : eval_.score >= 60 ? '✅' : eval_.score >= 40 ? '➖' : '⚠️';
          lines.push(`| ${dateStr} | ${scoreEmoji} ${eval_.score} | - | - | - |`);
        }
      }
      lines.push('');

      // 趋势分析
      if (historiesWithScores.length >= 2) {
        const scores = historiesWithScores.map(h => h.evaluation!.score);
        const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
        const trend = scores[0] > scores[scores.length - 1] ? '📈 上升' : '📉 下降';
        lines.push(`**趋势**：${trend}（平均评分：${avgScore.toFixed(0)}）`);
        lines.push('');
      }
    }
  }

  // 工具效果排行榜（基于历史经验）
  if (experience && experience.toolPatterns.length > 0) {
    lines.push('## 🏆 工具效果排行榜（基于历史）');
    lines.push('');
    lines.push('| 工具名称 | 平均评分 | 成功率 | 添加次数 | 移除次数 | 推荐度 |');
    lines.push('|---------|---------|--------|---------|---------|--------|');

    const patterns = experience.toolPatterns
      .sort((a, b) => b.avgScore - a.avgScore)
      .slice(0, 10);

    for (const p of patterns) {
      const recommendEmoji = {
        'highly_recommended': '🌟🌟',
        'recommended': '✅',
        'neutral': '➖',
        'not_recommended': '⚠️'
      }[p.recommendation] || '❓';

      lines.push(`| ${p.toolName} | ${p.avgScore} | ${(p.successRate * 100).toFixed(0)}% | ${p.addedCount} | ${p.removedCount} | ${recommendEmoji} |`);
    }
    lines.push('');
  }

  // 经验规律
  if (experience && experience.learnings.length > 0) {
    lines.push('## 💡 经验规律');
    lines.push('');

    const topLearnings = experience.learnings
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 5);

    for (const learning of topLearnings) {
      const confidenceBar = '█'.repeat(Math.round(learning.confidence * 10));
      lines.push(`### ${learning.rule}`);
      lines.push(`- **置信度**：${confidenceBar} ${(learning.confidence * 100).toFixed(0)}%`);
      lines.push(`- **证据**：${learning.evidence.join('; ')}`);
      if (learning.examples.length > 0) {
        lines.push(`- **示例**：${learning.examples.slice(0, 2).join('; ')}`);
      }
      lines.push('');
    }
  }

  // 反模式警告
  if (experience && experience.antiPatterns.length > 0) {
    lines.push('## ⚠️ 反模式警告');
    lines.push('');

    for (const ap of experience.antiPatterns) {
      lines.push(`### ${ap.pattern}`);
      lines.push(`- **原因**：${ap.reason}`);
      lines.push(`- **出现次数**：${ap.occurrences}`);
      lines.push(`- **平均负面影响**：${ap.avgNegativeImpact.toFixed(1)}%`);
      lines.push('');
    }
  }

  // 本月表现
  lines.push('## 📊 本月表现');
  lines.push('');
  lines.push('| 指标 | 目标 | 实际 | 差距 | 大盘 |');
  lines.push('|------|------|------|------|------|');
  lines.push(`| 月收益率 | +${report.performance.target}% | +${report.performance.actual}% | +${report.performance.gap}% | +${report.performance.market}% |`);
  lines.push(`| 胜率 | - | ${(report.performance.winRate * 100).toFixed(0)}% | - | - |`);
  lines.push(`| 最大回撤 | - | ${report.performance.maxDrawdown}% | - | - |`);
  lines.push(`| 夏普比率 | - | ${report.performance.sharpeRatio.toFixed(1)} | - | - |`);
  lines.push('');
  lines.push(`**减法器信号**：${report.performance.gap < 2 ? '微调' : report.performance.gap < 5 ? '中度调整' : '重大调整'}（差距 ${report.performance.gap}%）`);
  lines.push('');

  // 归因分析
  lines.push('## 🔍 减法器归因分析');
  lines.push('');
  lines.push(`### 差距：+${report.performance.gap}%（${report.performance.gap > 0 ? '未达标' : '超额完成'}）`);
  lines.push('');
  lines.push('#### 归因判断');
  lines.push('');
  lines.push(`**根本原因：${report.attribution.rootCause === 'target_unrealistic' ? '目标不合理' : '能力需要优化'}**`);
  lines.push(`- 置信度：${(report.attribution.confidence * 100).toFixed(0)}%`);
  lines.push(`- 原因：`);
  for (const reason of report.attribution.reasons) {
    lines.push(`  - ${reason}`);
  }
  lines.push('');

  // 工具效能
  if (report.toolEfficiency.length > 0) {
    lines.push('## 🛠️ 工具效能评估');
    lines.push('');
    lines.push('| 工具名称 | 调用次数 | 决策后胜率 | 平均收益 | ROI | 评级 |');
    lines.push('|---------|---------|-----------|---------|-----|------|');

    for (const tool of report.toolEfficiency) {
      const stars = '⭐'.repeat(tool.rating);
      lines.push(`| ${tool.tool_name} | ${tool.call_count} | ${(tool.win_rate * 100).toFixed(0)}% | ${(tool.avg_return * 100).toFixed(1)}% | ${tool.roi.toFixed(1)} | ${stars} |`);
    }
    lines.push('');
  }

  // 优化建议
  if (report.suggestions.length > 0) {
    lines.push('## 💡 补偿器调整方案');
    lines.push('');

    const addSuggestions = report.suggestions.filter(s => s.type === 'add_tool');
    const removeSuggestions = report.suggestions.filter(s => s.type === 'remove_tool');
    const updateSuggestions = report.suggestions.filter(s => s.type === 'update_experience');

    if (addSuggestions.length > 0) {
      lines.push('### ➕ 新增能力');
      lines.push('');
      for (const s of addSuggestions) {
        lines.push(`#### ${s.description}`);
        lines.push(`- **原因**：${s.reason}`);
        lines.push(`- **预期效果**：${s.expectedImpact}`);
        lines.push('');
      }
    }

    if (removeSuggestions.length > 0) {
      lines.push('### ➖ 移除能力');
      lines.push('');
      for (const s of removeSuggestions) {
        lines.push(`#### ${s.description}`);
        lines.push(`- **原因**：${s.reason}`);
        lines.push(`- **预期效果**：${s.expectedImpact}`);
        lines.push('');
      }
    }

    if (updateSuggestions.length > 0) {
      lines.push('### 📝 经验库更新');
      lines.push('');
      for (const s of updateSuggestions) {
        lines.push(`- ${s.description}：${s.reason}`);
      }
      lines.push('');
    }
  }

  lines.push('---');
  lines.push('');
  lines.push(`**生成时间**：${new Date().toISOString()}`);

  return lines.join('\n');
}
