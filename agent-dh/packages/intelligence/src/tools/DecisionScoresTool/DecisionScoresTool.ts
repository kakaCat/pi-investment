/**
 * DecisionScoresTool - 决策评分与教训查询工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { decisionScoresPrompt, DecisionScoresParams } from './prompt';

const ACTION_MAP: Record<string, string[]> = {
  buy: ['trade_buy'],
  sell: ['trade_sell'],
  skip: ['skip_trade', 'missed_opportunity'],
};

interface ScoreRow {
  decisionId?: string;
  decisionType?: string;
  relatedEntityId?: string;
  evaluationResult?: {
    band?: string;
    score?: number;
    excessReturn?: number;
    benchmark?: string;
    tradeDate?: string;
    windowTradingDays?: number;
    benchmarkMissing?: boolean;
  };
  learnedLesson?: string | null;
  context?: Record<string, any>;
}

export class DecisionScoresTool extends BaseTool<DecisionScoresParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'decision_scores',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = decisionScoresPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DecisionScoresParams): ValidationResult {
    if (args.limit !== undefined && (args.limit < 1 || args.limit > 500)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, issue: 'limit 取值范围 1-500' };
    }
    if (args.since && !/^\d{4}-\d{2}-\d{2}$/.test(args.since)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, issue: 'since 格式须为 YYYY-MM-DD' };
    }
    return { success: true };
  }

  protected async execute(args: DecisionScoresParams, _context: ToolContext): Promise<any> {
    const raw = await this.qv2.getEvolutionDecisionScores();
    const all: ScoreRow[] = Array.isArray((raw as any)?.items) ? (raw as any).items : [];

    // 过滤
    const wantedTypes = args.action ? ACTION_MAP[args.action] ?? [] : null;
    const filtered = all.filter((r) => {
      if (wantedTypes && !wantedTypes.includes(String(r.decisionType))) return false;
      if (args.band && r.evaluationResult?.band !== args.band) return false;
      if (args.symbol && String(r.relatedEntityId) !== String(args.symbol)) return false;
      if (args.since && String(r.evaluationResult?.tradeDate ?? '') < args.since) return false;
      if (args.lessons_only && !r.learnedLesson) return false;
      return true;
    });

    // 汇总（基于过滤后全量，非 limit 截断后）
    const withExcess = filtered.filter((r) => typeof r.evaluationResult?.excessReturn === 'number');
    const excessArr = withExcess.map((r) => Number(r.evaluationResult!.excessReturn));
    const bandCount: Record<string, number> = {};
    for (const r of filtered) {
      const b = r.evaluationResult?.band ?? 'unscored';
      bandCount[b] = (bandCount[b] ?? 0) + 1;
    }
    const typeCount: Record<string, number> = {};
    for (const r of filtered) {
      const t = String(r.decisionType ?? 'unknown');
      typeCount[t] = (typeCount[t] ?? 0) + 1;
    }
    const lessonNonEmpty = filtered.filter((r) => !!r.learnedLesson).length;
    const sortByExcess = [...withExcess].sort(
      (a, b) => Number(a.evaluationResult!.excessReturn) - Number(b.evaluationResult!.excessReturn),
    );
    const mean = excessArr.length ? excessArr.reduce((x, y) => x + y, 0) / excessArr.length : null;

    const limit = args.limit ?? 20;
    const items = filtered.slice(0, limit).map((r) => ({
      decisionId: r.decisionId,
      decisionType: r.decisionType,
      symbol: r.relatedEntityId,
      tradeDate: r.evaluationResult?.tradeDate,
      windowTradingDays: r.evaluationResult?.windowTradingDays,
      band: r.evaluationResult?.band,
      score: r.evaluationResult?.score,
      excessReturnPct:
        typeof r.evaluationResult?.excessReturn === 'number'
          ? Number((Number(r.evaluationResult.excessReturn) * 100).toFixed(2))
          : null,
      benchmark: r.evaluationResult?.benchmark,
      benchmarkMissing: r.evaluationResult?.benchmarkMissing,
      learnedLesson: r.learnedLesson ?? null,
      context: r.context ?? null,
    }));

    return sanitizeLossless({
      total: all.length,
      matched: filtered.length,
      summary: {
        byBand: bandCount,
        byType: typeCount,
        meanExcessPct: mean === null ? null : Number((mean * 100).toFixed(2)),
        evaluatedWithExcess: excessArr.length,
        worst:
          sortByExcess[0]
            ? {
                decisionId: sortByExcess[0].decisionId,
                symbol: sortByExcess[0].relatedEntityId,
                excessReturnPct: Number((Number(sortByExcess[0].evaluationResult!.excessReturn) * 100).toFixed(2)),
              }
            : null,
        best: sortByExcess.length
          ? (() => {
              const b = sortByExcess[sortByExcess.length - 1];
              return {
                decisionId: b.decisionId,
                symbol: b.relatedEntityId,
                excessReturnPct: Number((Number(b.evaluationResult!.excessReturn) * 100).toFixed(2)),
              };
            })()
          : null,
        lessonCoverage: {
          total: filtered.length,
          nonEmpty: lessonNonEmpty,
          rate: filtered.length ? Number((lessonNonEmpty / filtered.length).toFixed(3)) : null,
        },
      },
      filters: { ...args },
      returned: items.length,
      items,
      source: 'quantsys-v2 GET /api/evolution/decision-scores',
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
