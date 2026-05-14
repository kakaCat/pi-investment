/**
 * Evolution Reporter - 进化报告生成器
 *
 * 生成结构化的进化报告
 */

import type {
  EvolutionReport,
  AttributionResult,
  ToolEfficiency,
  OptimizationSuggestion
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
export function formatReportAsMarkdown(report: EvolutionReport): string {
  const lines: string[] = [];

  // 标题
  lines.push(`# 进化报告 ${report.period}`);
  lines.push('');

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
