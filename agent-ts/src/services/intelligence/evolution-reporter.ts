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
  ExperienceSummary,
  ComparisonResult,
  PeriodPerformance,
  DataQualityReport,
  TotalReturn,
} from '../../types/evolution.js';
import type { MarketContext } from '../../types/market-context.js';
import type { SessionAnalysis } from '../../types/session-log.js';
import type { ToolEfficiencyAssessment } from './tool-efficiency-analyzer.js';
import type { HoldingDimensionAnalysis } from '../../types/holding-analysis.js';

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
  marketContext?: MarketContext; // 新增：市场环境数据
  sessionAnalysis?: SessionAnalysis; // 新增：Session 日志分析
  toolEfficiencyAssessment?: ToolEfficiencyAssessment; // 新增：工具效能评估
  holdingAnalysis?: HoldingDimensionAnalysis; // 新增：持仓维度分析
  // 可选：减法器全量数据（用于详细报告）
  comparisonResult?: ComparisonResult;
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
    suggestions: input.suggestions,
    marketContext: input.marketContext, // 新增：传递市场环境数据
    sessionLog: input.sessionAnalysis, // 新增：传递 Session 日志分析
    toolEfficiencyAssessment: input.toolEfficiencyAssessment, // 新增：传递工具效能评估
    holdingAnalysis: input.holdingAnalysis, // 新增：传递持仓维度分析
  };
}

/**
 * 格式化为 Markdown
 */
export function formatReportAsMarkdown(report: EvolutionReport, recentHistories?: EvolutionHistory[], experience?: ExperienceSummary, comparisonResult?: ComparisonResult): string {
  const lines: string[] = [];

  // 标题
  lines.push(`# 进化报告 ${report.period}`);
  lines.push('');

  // Session 日志分析（提前到最前面，紧跟标题）
  if (report.sessionLog) {
    const sa = report.sessionLog;
    lines.push('## 📊 Session 日志分析');
    lines.push('');
    lines.push('### 工具调用统计');
    lines.push('');
    lines.push(`- **总调用次数**：${sa.totalToolCalls} 次`);
    lines.push(`- **总失败次数**：${sa.totalToolFailures} 次`);
    lines.push(`- **整体错误率**：${(sa.overallErrorRate * 100).toFixed(2)}%`);
    lines.push(`- **平均耗时**：${sa.avgToolDuration.toFixed(0)}ms`);
    lines.push('');

    if (sa.topTools.length > 0) {
      lines.push('### 高频工具 Top 5');
      lines.push('');
      lines.push('| 工具名 | 调用次数 | 成功率 | 平均耗时 |');
      lines.push('|--------|----------|--------|----------|');
      sa.topTools.forEach(tool => {
        const successRate = ((1 - tool.errorRate) * 100).toFixed(1);
        lines.push(`| ${tool.name} | ${tool.callCount} | ${successRate}% | ${tool.avgDuration.toFixed(0)}ms |`);
      });
      lines.push('');
    }

    if (sa.slowestTools.length > 0) {
      lines.push('### 最慢工具 Top 5');
      lines.push('');
      lines.push('| 工具名 | 平均耗时 | 调用次数 |');
      lines.push('|--------|----------|----------|');
      sa.slowestTools.forEach(tool => {
        lines.push(`| ${tool.name} | ${tool.avgDuration.toFixed(0)}ms | ${tool.callCount} |`);
      });
      lines.push('');
    }

    if (sa.mostFailedTools.length > 0) {
      lines.push('### 高失败率工具');
      lines.push('');
      lines.push('| 工具名 | 失败次数 | 错误率 | 调用次数 |');
      lines.push('|--------|----------|--------|----------|');
      sa.mostFailedTools.forEach(tool => {
        lines.push(`| ${tool.name} | ${tool.failureCount} | ${(tool.errorRate * 100).toFixed(1)}% | ${tool.callCount} |`);
      });
      lines.push('');
    }

    lines.push('### Session 元数据');
    lines.push('');
    lines.push(`- **Session ID**：${sa.metadata.session_key}`);
    lines.push(`- **模型**：${sa.metadata.model}`);
    lines.push(`- **总轮次**：${sa.metadata.total_turns}`);
    lines.push(`- **总消息数**：${sa.metadata.total_messages}`);
    lines.push(`- **总 Token 数**：${sa.metadata.total_tokens.toLocaleString()}`);
    lines.push(`- **LLM 调用次数**：${sa.metadata.llm_calls}`);
    lines.push('');
  }

  // 工具效能评估（紧跟 Session 日志分析）
  if (report.toolEfficiencyAssessment) {
    const tea = report.toolEfficiencyAssessment;
    lines.push('## 🔧 工具效能评估');
    lines.push('');
    lines.push(`- **整体效能评分**：${tea.overallScore}/100`);
    lines.push('');

    if (tea.problematicTools.length > 0) {
      lines.push('### ⚠️ 高失败率工具');
      lines.push('');
      lines.push('| 工具名 | 失败次数 | 错误率 | 调用次数 | 建议 |');
      lines.push('|--------|----------|--------|----------|------|');
      tea.problematicTools.forEach((tool: { name: string; failureCount: number; errorRate: number; callCount: number }) => {
        const action = tool.errorRate > 0.5 ? '重写或移除' : '优化错误处理';
        lines.push(`| ${tool.name} | ${tool.failureCount} | ${(tool.errorRate * 100).toFixed(1)}% | ${tool.callCount} | ${action} |`);
      });
      lines.push('');
    }

    if (tea.slowTools.length > 0) {
      lines.push('### 🐌 性能瓶颈工具');
      lines.push('');
      lines.push('| 工具名 | 平均耗时 | 调用次数 | 建议 |');
      lines.push('|--------|----------|----------|------|');
      tea.slowTools.forEach((tool: { name: string; avgDuration: number; callCount: number }) => {
        lines.push(`| ${tool.name} | ${(tool.avgDuration / 1000).toFixed(1)}s | ${tool.callCount} | 添加缓存/优化查询 |`);
      });
      lines.push('');
    }

    if (tea.suggestions.length > 0) {
      lines.push('### 💡 工具优化建议');
      lines.push('');
      tea.suggestions.slice(0, 5).forEach((suggestion: OptimizationSuggestion, index: number) => {
        const priorityEmoji = suggestion.priority === 'high' ? '🔴' : suggestion.priority === 'medium' ? '🟡' : '🟢';
        lines.push(`${index + 1}. ${priorityEmoji} **${suggestion.description}**`);
        lines.push(`   - 原因：${suggestion.reason}`);
        lines.push(`   - 预期影响：${suggestion.expectedImpact}`);
        lines.push('');
      });
    }
  }

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

  // 市场环境
  if (report.marketContext) {
    const mc = report.marketContext;
    lines.push('## 🌍 市场环境');
    lines.push('');

    lines.push('### 大盘指数');
    lines.push('');
    lines.push('| 指数 | 收益率 | 趋势 | 波动率 |');
    lines.push('|------|--------|------|--------|');

    for (const [key, index] of Object.entries(mc.indices)) {
      if (!index) continue;
      const trendEmoji = index.trend === 'up' ? '📈' : index.trend === 'down' ? '📉' : '➡️';
      lines.push(`| ${index.name} | ${index.return.toFixed(2)}% | ${trendEmoji} ${index.trend} | ${index.volatility.toFixed(2)}% |`);
    }
    lines.push('');

    if (mc.sectorPerformance.length > 0) {
      lines.push('### 板块表现 Top 10');
      lines.push('');
      lines.push('| 排名 | 板块 | 收益率 | 资金流向 |');
      lines.push('|------|------|--------|----------|');

      mc.sectorPerformance.slice(0, 10).forEach(sector => {
        lines.push(`| ${sector.rank} | ${sector.sector} | ${sector.return.toFixed(2)}% | ${sector.fundFlow.toFixed(2)}亿 |`);
      });
      lines.push('');
    }

    lines.push('### 市场情绪');
    lines.push('');
    const sentimentEmoji = mc.sentiment.sentiment === 'bullish' ? '🐂' :
                          mc.sentiment.sentiment === 'bearish' ? '🐻' : '😐';
    lines.push(`- **情绪**：${sentimentEmoji} ${mc.sentiment.sentiment}`);
    lines.push(`- **涨跌家数比**：${mc.sentiment.advanceDeclineRatio.toFixed(2)}`);
    lines.push(`- **市场广度**：${(mc.sentiment.marketBreadth * 100).toFixed(1)}%`);
    lines.push(`- **成交量比**：${mc.sentiment.volumeRatio.toFixed(2)}x`);
    lines.push('');
  }

  // 数据完整性
  if (comparisonResult?.dataQuality) {
    const dq = comparisonResult.dataQuality;
    lines.push('## 🔍 数据完整性评估');
    lines.push('');
    lines.push(`| 维度 | 状态 |`);
    lines.push('|------|------|');
    lines.push(`| 交易记录 | ${dq.tradeCount} 笔`);
    lines.push(`| 持仓数量 | ${dq.positionCount} 只`);
    lines.push(`| 时间跨度 | ${dq.earliestTradeDate ?? '无'} ~ ${dq.latestTradeDate ?? '无'}`);
    const reliabilityEmoji = dq.reliability === 'high' ? '✅' : dq.reliability === 'medium' ? '⚠️' : '❌';
    lines.push(`| 可靠性评级 | ${reliabilityEmoji} ${dq.reliability}`);
    if (dq.warnings.length > 0) {
      lines.push('');
      lines.push('**警告**：');
      for (const w of dq.warnings) {
        lines.push(`- ⚠️ ${w}`);
      }
    }
    lines.push('');
  }

  // 阶段对比：周
  if (comparisonResult?.weeklyComparison && comparisonResult.weeklyComparison.length > 0) {
    lines.push('## 📅 周度表现');
    lines.push('');
    lines.push('| 周 | 已实现盈亏 | 收益率 | 交易 | 可靠性 |');
    lines.push('|----|----------|--------|------|--------|');
    for (const w of comparisonResult.weeklyComparison) {
      const pnlStr = w.realizedPnL >= 0 ? `+¥${w.realizedPnL.toFixed(0)}` : `-¥${Math.abs(w.realizedPnL).toFixed(0)}`;
      const retStr = w.returnPct >= 0 ? `+${w.returnPct}%` : `${w.returnPct}%`;
      lines.push(`| ${w.label} | ${pnlStr} | ${retStr} | ${w.tradeCount}笔 | ${w.reliability} |`);
    }
    lines.push('');
  }

  // 阶段对比：月
  if (comparisonResult?.monthlyComparison && comparisonResult.monthlyComparison.length > 0) {
    lines.push('## 📆 月度表现');
    lines.push('');
    lines.push('| 月 | 已实现盈亏 | 收益率 | 交易 | 可靠性 |');
    lines.push('|----|----------|--------|------|--------|');
    for (const m of comparisonResult.monthlyComparison) {
      const pnlStr = m.realizedPnL >= 0 ? `+¥${m.realizedPnL.toFixed(0)}` : `-¥${Math.abs(m.realizedPnL).toFixed(0)}`;
      const retStr = m.returnPct >= 0 ? `+${m.returnPct}%` : `${m.returnPct}%`;
      lines.push(`| ${m.label} | ${pnlStr} | ${retStr} | ${m.tradeCount}笔 | ${m.reliability} |`);
    }
    lines.push('');
  }

  // 全周期总账
  if (comparisonResult?.totalReturn) {
    const tr = comparisonResult.totalReturn;
    lines.push('## 🏦 全周期总账');
    lines.push('');
    lines.push('| 项目 | 金额 |');
    lines.push('|------|------|');
    lines.push(`| 累积总投入（含清仓） | ¥${tr.totalInvestment.toLocaleString()}`);
    lines.push(`| 活跃资金（当前持仓） | ¥${tr.activeInvestment.toLocaleString()}`);
    lines.push(`| 峰值占用资金 | ¥${tr.peakInvestment.toLocaleString()}`);
    lines.push(`| 已实现盈亏 | ¥${tr.realizedPnL.toLocaleString()}`);
    lines.push(`| 持仓浮盈（估） | ¥${tr.unrealizedPnL.toLocaleString()}`);
    const totalStr = tr.totalPnL >= 0 ? `+¥${tr.totalPnL.toLocaleString()}` : `-¥${Math.abs(tr.totalPnL).toLocaleString()}`;
    lines.push(`| **总盈亏** | **${totalStr}**`);
    lines.push(`| 累积投入回报率 | ${tr.totalReturnPct >= 0 ? '+' : ''}${tr.totalReturnPct}%`);
    if (tr.activeInvestment !== tr.totalInvestment) {
      lines.push(`| 活跃资金回报率 | ${tr.activeReturnPct >= 0 ? '+' : ''}${tr.activeReturnPct}%`);
    }
    lines.push('');
  }

  // 本月表现
  lines.push('## 📊 本期表现');
  lines.push('');
  lines.push('| 指标 | 目标 | 实际 | 差距 | 大盘 |');
  lines.push('|------|------|------|------|------|');
  lines.push(`| 收益率 | +${report.performance.target}% | ${report.performance.actual >= 0 ? '+' : ''}${report.performance.actual}% | ${report.performance.gap >= 0 ? '+' : ''}${report.performance.gap}% | +${report.performance.market}% |`);
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

  // 工具效能评估（新增）
  if (report.toolEfficiencyAssessment) {
    const tea = report.toolEfficiencyAssessment;
    lines.push('## 🔧 工具效能深度评估');
    lines.push('');
    lines.push(`- **整体效能评分**：${tea.overallScore}/100`);
    lines.push('');

    if (tea.problematicTools.length > 0) {
      lines.push('### ⚠️ 高错误率工具');
      lines.push('');
      lines.push('| 工具名称 | 调用次数 | 错误率 | 平均耗时 |');
      lines.push('|---------|---------|--------|----------|');
      tea.problematicTools.forEach((tool: { name: string; callCount: number; errorRate: number; avgDuration: number }) => {
        lines.push(`| ${tool.name} | ${tool.callCount} | ${(tool.errorRate * 100).toFixed(1)}% | ${tool.avgDuration.toFixed(0)}ms |`);
      });
      lines.push('');
    }

    if (tea.slowTools.length > 0) {
      lines.push('### 🐌 性能瓶颈工具');
      lines.push('');
      lines.push('| 工具名称 | 调用次数 | 平均耗时 | 错误率 |');
      lines.push('|---------|---------|----------|--------|');
      tea.slowTools.forEach((tool: { name: string; callCount: number; avgDuration: number; errorRate: number }) => {
        lines.push(`| ${tool.name} | ${tool.callCount} | ${tool.avgDuration.toFixed(0)}ms | ${(tool.errorRate * 100).toFixed(1)}% |`);
      });
      lines.push('');
    }

    if (tea.suggestions.length > 0) {
      lines.push('### 💡 工具优化建议');
      lines.push('');
      tea.suggestions.forEach((s: { type: string; description: string; reason: string; expectedImpact: string }) => {
        const typeEmoji = s.type === 'add_tool' ? '➕' : s.type === 'remove_tool' ? '➖' : '🔧';
        lines.push(`#### ${typeEmoji} ${s.description}`);
        lines.push(`- **原因**：${s.reason}`);
        lines.push(`- **预期效果**：${s.expectedImpact}`);
        lines.push('');
      });
    }
  }

  // 持仓维度分析（新增）
  if (report.holdingAnalysis) {
    const ha = report.holdingAnalysis;
    lines.push('## 📊 持仓维度分析');
    lines.push('');

    // 统计摘要
    lines.push('### 📈 组合概览');
    lines.push('');
    lines.push('| 指标 | 数值 |');
    lines.push('|------|------|');
    lines.push(`| 总市值 | ¥${ha.summary!.totalValue.toFixed(2)} |`);
    lines.push(`| 未实现盈亏 | ¥${ha.summary!.totalPnL.toFixed(2)} |`);
    lines.push(`| 平均收益率 | ${ha.summary!.avgReturn.toFixed(2)}% |`);
    lines.push(`| 盈利个股 | ${ha.summary!.winningStocks}/${ha.stocks.length} |`);
    lines.push(`| 胜率 | ${ha.summary!.winRate.toFixed(1)}% |`);
    lines.push(`| 最大单股占比 | ${ha.summary!.maxSingleStockWeight.toFixed(2)}% |`);
    lines.push(`| 最大行业占比 | ${ha.summary!.maxSectorWeight.toFixed(2)}% |`);
    lines.push('');

    // 表现最好的个股
    if (ha.topPerformers.length > 0) {
      lines.push('### 🌟 表现最佳个股 Top 5');
      lines.push('');
      lines.push('| 股票 | 收益率 | 贡献度 | 占比 | 市值 |');
      lines.push('|------|--------|--------|------|------|');
      ha.topPerformers.forEach((stock: { symbol: string; name: string; returnRate: number; contribution: number; weight: number; marketValue: number }) => {
        lines.push(`| ${stock.symbol} ${stock.name} | ${stock.returnRate.toFixed(2)}% | ${stock.contribution.toFixed(2)}% | ${stock.weight.toFixed(2)}% | ¥${stock.marketValue.toFixed(2)} |`);
      });
      lines.push('');
    }

    // 表现最差的个股
    if (ha.bottomPerformers.length > 0) {
      lines.push('### ⚠️ 表现最差个股 Top 5');
      lines.push('');
      lines.push('| 股票 | 收益率 | 贡献度 | 占比 | 市值 |');
      lines.push('|------|--------|--------|------|------|');
      ha.bottomPerformers.forEach((stock: { symbol: string; name: string; returnRate: number; contribution: number; weight: number; marketValue: number }) => {
        lines.push(`| ${stock.symbol} ${stock.name} | ${stock.returnRate.toFixed(2)}% | ${stock.contribution.toFixed(2)}% | ${stock.weight.toFixed(2)}% | ¥${stock.marketValue.toFixed(2)} |`);
      });
      lines.push('');
    }

    // 行业维度分析
    if (ha.topSectors.length > 0 || ha.bottomSectors.length > 0) {
      lines.push('### 🏭 行业维度分析');
      lines.push('');
      lines.push('| 行业 | 个股数 | 占比 | 平均收益率 | 贡献度 |');
      lines.push('|------|--------|------|------------|--------|');

      // 表现最好的行业
      ha.topSectors.forEach((sector: { sector: string; stockCount: number; weight: number; avgReturn: number; contribution: number }) => {
        lines.push(`| 🌟 ${sector.sector} | ${sector.stockCount} | ${sector.weight.toFixed(2)}% | ${sector.avgReturn.toFixed(2)}% | ${sector.contribution.toFixed(2)}% |`);
      });

      // 表现最差的行业
      ha.bottomSectors.forEach((sector: { sector: string; stockCount: number; weight: number; avgReturn: number; contribution: number }) => {
        lines.push(`| ⚠️ ${sector.sector} | ${sector.stockCount} | ${sector.weight.toFixed(2)}% | ${sector.avgReturn.toFixed(2)}% | ${sector.contribution.toFixed(2)}% |`);
      });
      lines.push('');
    }

    // 市值维度分析
    if (ha.marketCaps.length > 0) {
      lines.push('### 💰 市值维度分析');
      lines.push('');
      lines.push('| 类别 | 个股数 | 占比 | 平均收益率 | 贡献度 |');
      lines.push('|------|--------|------|------------|--------|');
      ha.marketCaps.forEach((mc: { label: string; stockCount: number; weight: number; avgReturn: number; contribution: number }) => {
        lines.push(`| ${mc.label} | ${mc.stockCount} | ${mc.weight.toFixed(2)}% | ${mc.avgReturn.toFixed(2)}% | ${mc.contribution.toFixed(2)}% |`);
      });
      lines.push('');
    }

    // 问题诊断
    if (ha.issues.length > 0) {
      lines.push('### 🚨 持仓问题诊断');
      lines.push('');

      const highIssues = ha.issues.filter((i: { severity: string }) => i.severity === 'high');
      const mediumIssues = ha.issues.filter((i: { severity: string }) => i.severity === 'medium');

      if (highIssues.length > 0) {
        lines.push('#### 🔴 高风险问题');
        lines.push('');
        highIssues.forEach((issue: { description: string; impact: string; suggestion: string }) => {
          lines.push(`**${issue.description}**`);
          lines.push(`- 影响：${issue.impact}`);
          lines.push(`- 建议：${issue.suggestion}`);
          lines.push('');
        });
      }

      if (mediumIssues.length > 0) {
        lines.push('#### 🟡 中等风险问题');
        lines.push('');
        mediumIssues.forEach((issue: { description: string; impact: string; suggestion: string }) => {
          lines.push(`**${issue.description}**`);
          lines.push(`- 影响：${issue.impact}`);
          lines.push(`- 建议：${issue.suggestion}`);
          lines.push('');
        });
      }
    }
  }

  // 优化建议
  lines.push('## 💡 补偿器调整方案');
  lines.push('');

  if (report.suggestions.length === 0) {
    lines.push('**本次无新建议**');
    lines.push('');
    lines.push('原因：');
    lines.push('- 最近的优化建议已在历史中尝试过，避免重复');
    lines.push('- 当前表现稳定，无需立即调整');
    lines.push('- 或数据样本不足，需要更多交易数据');
    lines.push('');
  } else {
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
