import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { evolutionLeaderboardPrompt, type EvolutionLeaderboardParams, type EvolutionLeaderboardResult } from './prompt';

/**
 * EvolutionLeaderboardTool — 策略进化历史排行（RFC 012 P2 版）
 *
 * 数据源切到 quantsys-v2 策略进化引擎（:5001，真实回测进化）。语义：按 strategy_id
 * 读该策略最近 N 轮进化 run，每 run 取其 fitness 最优变体行（服务端已 fitness DESC
 * NULLS LAST 排序），组装成"进化历史排行"。诚实语义：
 * - 无记录 → data_source=empty（不展示任何排名）
 * - 全为降级行（整批诚实失败，fitness 全 NULL）→ data_source=degraded（暴露"进化过但失败"）
 * - 有真实 fitness → qv2_real（其中降级行保留并标注 degraded_reason，不静默丢弃）
 * 绝不展示占位/虚构数字（Agent OS 0.05×i 阶梯已随 A 链退役）。
 */
export class EvolutionLeaderboardTool extends BaseTool<EvolutionLeaderboardParams, EvolutionLeaderboardResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_leaderboard',
    category: 'evolution',
    version: '2.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = evolutionLeaderboardPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: EvolutionLeaderboardParams): ValidationResult {
    const { strategy_id, limit } = params;

    if (strategy_id == null || Number.isNaN(Number(strategy_id)) || Number(strategy_id) <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'strategy_id',
        issue: 'strategy_id 必填且必须是正整数（经 strategy_list 获取）',
      };
    }

    if (limit !== undefined && (limit <= 0 || limit > 100)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'limit',
        issue: 'limit 必须在 1-100 之间',
        expected: '1 <= limit <= 100',
      };
    }

    return { success: true };
  }

  protected async execute(params: EvolutionLeaderboardParams, context: ToolContext): Promise<EvolutionLeaderboardResult> {
    const strategyId = Number(params.strategy_id);
    const qv2Result: any = await this.qv2.getStrategyEvolutionRuns(strategyId, params.limit ?? 10);
    const runs: any[] = Array.isArray(qv2Result?.runs) ? qv2Result.runs : [];

    if (runs.length === 0) {
      return sanitizeLossless({
        strategy_id: strategyId,
        rankings: [],
        total_runs: 0,
        data_source: 'empty',
        degraded_reason: `策略 ${strategyId} 在 qv2 策略进化引擎中无真实进化记录（先跑 evolution_run 产生数据）。`,
      }) as any;
    }

    // 每 run 一条 best 行；服务端已按 fitness DESC NULLS LAST 排序，rank 即降序位置
    const rankings = runs.map((r, i) => ({
      rank: i + 1,
      run_id: r.runId ?? r.run_id,
      strategy_id: Number(r.strategyId ?? r.strategy_id ?? strategyId),
      fitness: r.fitness != null ? Number(r.fitness) : null,
      best_params: r.params ?? undefined,
      variant_key: r.variantKey ?? r.variant_key,
      metrics: r.metrics ?? null,
      degraded_reason: r.degradedReason ?? r.degraded_reason ?? null,
      computed_at: r.computedAt ?? r.computed_at,
    }));

    const realRuns = rankings.filter((x) => x.fitness != null && Number.isFinite(x.fitness));

    if (realRuns.length === 0) {
      // 整批降级：进化过但诚实失败——暴露记录与原因，不展示排名
      return sanitizeLossless({
        strategy_id: strategyId,
        rankings: [],
        total_runs: runs.length,
        data_source: 'degraded',
        degraded_reason: `策略 ${strategyId} 的 ${runs.length} 轮进化均诚实降级（无真实 fitness），最近原因：${rankings[0]?.degraded_reason || '数据源不可用/样本不足'}。`,
        raw_count: runs.length,
      }) as any;
    }

    const avgFitness = realRuns.reduce((a, b) => a + b.fitness!, 0) / realRuns.length;

    return sanitizeLossless({
      strategy_id: strategyId,
      rankings,
      total_runs: runs.length,
      avg_fitness: Number(avgFitness.toFixed(4)),
      data_source: 'qv2_real',
      ...(realRuns.length < runs.length
        ? { degraded_note: `${runs.length - realRuns.length} 轮降级 run 已标注不参与均值` }
        : {}),
    }) as any;
  }

  protected wrap(data: EvolutionLeaderboardResult, context: ToolContext): ToolResponse<EvolutionLeaderboardResult> {
    const { strategy_id, rankings = [], total_runs = 0, avg_fitness, data_source, degraded_reason } = data;

    if (data_source === 'degraded' || data_source === 'empty') {
      const reason = degraded_reason || '无可用数据';
      const message = `进化排行不可用（data_source=${data_source}）：${reason}`;
      return {
        success: true,
        data: { ...data, rankings: [], total_runs },
        message,
        metadata: { data_source, strategy_id, displayed: 0 },
      };
    }

    const top = rankings[0];
    const topStr = top && top.fitness != null
      ? `最优 ${Number(top.fitness).toFixed(2)}（run ${top.run_id}）`
      : '无真实 fitness';
    const message = `策略 ${strategy_id} 共 ${total_runs} 轮进化，平均 fitness ${avg_fitness != null ? Number(avg_fitness).toFixed(2) : 'N/A'}，${topStr}（data_source=qv2_real）`;

    return {
      success: true,
      data,
      message,
      metadata: {
        data_source,
        strategy_id,
        total_runs,
        avg_fitness,
        displayed: rankings.length,
      },
    };
  }
}
