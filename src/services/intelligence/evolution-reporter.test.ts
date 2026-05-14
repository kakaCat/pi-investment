import { describe, it, expect } from '@jest/globals';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter.js';
import type { AttributionResult, ToolEfficiency, EvolutionReport } from '../../types/evolution.js';

describe('EvolutionReporter - generateEvolutionReport', () => {
  it('应该生成完整的进化报告', () => {
    const attribution: AttributionResult = {
      rootCause: 'capability_insufficient',
      confidence: 0.85,
      reasons: ['跑输大盘2%', '决策错误率30%'],
      recommendation: 'trigger_optimizer'
    };

    const toolStats: ToolEfficiency[] = [
      {
        tool_name: 'calculate_technical_indicators',
        call_count: 50,
        decisions_after_call: 45,
        win_rate: 0.72,
        avg_return: 0.032,
        avg_tokens: 1200,
        cost_per_call: 0.012,
        roi: 2.67,
        rating: 3
      }
    ];

    const report = generateEvolutionReport({
      period: '2026-05',
      performance: {
        target: 12,
        actual: 10,
        gap: 2,
        market: 8,
        winRate: 0.68,
        maxDrawdown: -6,
        sharpeRatio: 1.3
      },
      attribution,
      toolStats,
      suggestions: []
    });

    expect(report.period).toBe('2026-05');
    expect(report.performance.gap).toBe(2);
    expect(report.attribution.rootCause).toBe('capability_insufficient');
    expect(report.toolEfficiency).toHaveLength(1);
  });
});

describe('EvolutionReporter - formatReportAsMarkdown', () => {
  it('应该生成 Markdown 格式报告', () => {
    const report: EvolutionReport = {
      period: '2026-05',
      performance: {
        target: 12,
        actual: 10,
        gap: 2,
        market: 8,
        winRate: 0.68,
        maxDrawdown: -6,
        sharpeRatio: 1.3
      },
      attribution: {
        rootCause: 'capability_insufficient',
        confidence: 0.85,
        reasons: ['跑输大盘2%'],
        recommendation: 'trigger_optimizer'
      },
      sessionAnalysis: {
        totalSessions: 50,
        successPatterns: [],
        failurePatterns: []
      },
      toolEfficiency: [],
      suggestions: []
    };

    const markdown = formatReportAsMarkdown(report);

    expect(markdown).toContain('# 进化报告 2026-05');
    expect(markdown).toContain('## 📊 本月表现');
    expect(markdown).toContain('| 月收益率 | +12% | +10% | +2% | +8% |');
    expect(markdown).toContain('## 🔍 减法器归因分析');
  });
});
