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
