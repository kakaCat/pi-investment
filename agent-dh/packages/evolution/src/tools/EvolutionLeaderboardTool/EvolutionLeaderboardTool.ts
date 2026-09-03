import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { evolutionLeaderboardPrompt, type EvolutionLeaderboardParams, type EvolutionLeaderboardResult } from './prompt';
import { allFitnessArePlaceholder } from '../../placeholder';

/**
 * EvolutionLeaderboardTool — 策略进化排行榜
 *
 * RFC 012 P0（2026-09-03）：不再透传 Agent OS 占位结果。
 * Agent OS 实际返回 {entries:[{strategy_id, fitness, run_id, mode, updated_at}]}
 * （字段名与工具 schema 的 rankings 错位，历史透传曾让工具展示"共 0 个策略"）。
 * 本实现显式映射 entries→rankings，并对占位分（0.05×i 阶梯，见 placeholder.ts）
 * 执行降级：返回空榜 + data_source=degraded + 原因，绝不展示占位数字冒充的排名。
 */
export class EvolutionLeaderboardTool extends BaseTool<EvolutionLeaderboardParams, EvolutionLeaderboardResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_leaderboard',
    category: 'evolution',
    version: '1.1.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = evolutionLeaderboardPrompt;

  constructor(private aos: AgentOSClient) {
    super();
  }

  protected validate(params: EvolutionLeaderboardParams): ValidationResult {
    const { limit } = params;

    // limit 校验
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
    const raw: any = await this.aos.evolution.getLeaderboard({
      limit: params.limit || 10,
    });

    // Agent OS 返回 {entries:[...]}（raw 直接透传曾因字段错位显示空榜）
    const entries: any[] = Array.isArray(raw?.entries)
      ? raw.entries
      : Array.isArray(raw?.rankings)
        ? raw.rankings
        : [];

    if (entries.length === 0) {
      return {
        rankings: [],
        total_strategies: 0,
        avg_fitness: undefined as any,
        data_source: 'empty',
        degraded_reason: '进化榜无记录（Agent OS evolution_runs 无 completed run）。',
      } as any;
    }

    const rankings = entries.map((e, i) => ({
      strategy_id: Number(e.strategy_id ?? e.strategyId),
      strategy_name: (e.strategy_name ?? e.strategyName) || `strategy-${e.strategy_id ?? e.strategyId}`,
      fitness: Number(e.fitness),
      rank: i + 1,
    }));

    const fitnessValues = rankings.map((r) => r.fitness);

    // RFC 012 P0：占位分拦截——全部 0.05×i 阶梯 → 不展示，降级并说明原因
    if (allFitnessArePlaceholder(fitnessValues)) {
      return {
        rankings: [],
        total_strategies: entries.length,
        avg_fitness: undefined as any,
        data_source: 'degraded',
        degraded_reason:
          `Agent OS 返回的 ${entries.length} 条 fitness 全为启发式占位分（0.05×i 阶梯，` +
          '源自策略从未真实回测时 evolution_handler.go 的占位逻辑），非真实回测/双侧捕获结果。' +
          '占位排名已拦截不展示。真实策略进化请使用 qv2 策略进化引擎（RFC 012）。',
        raw_count: entries.length,
      } as any;
    }

    const validFitness = fitnessValues.filter((f) => Number.isFinite(f));
    const avgFitness = validFitness.length > 0
      ? validFitness.reduce((a, b) => a + b, 0) / validFitness.length
      : undefined;

    return {
      rankings,
      total_strategies: entries.length,
      avg_fitness: avgFitness as any,
      data_source: 'agent_os',
    } as any;
  }

  protected wrap(data: EvolutionLeaderboardResult, context: ToolContext): ToolResponse<EvolutionLeaderboardResult> {
    const { rankings = [], total_strategies = 0, avg_fitness, data_source, degraded_reason } = data;

    if (data_source === 'degraded' || data_source === 'empty') {
      const reason = degraded_reason || '无可用数据';
      const message = `进化榜不可用（data_source=${data_source}）：${reason}`;
      return {
        success: true,
        data: {
          ...data,
          rankings: [],
          total_strategies,
        },
        message,
        metadata: {
          data_source,
          displayed: 0,
        },
      };
    }

    const avgFitnessStr = avg_fitness !== undefined && avg_fitness !== null
      ? avg_fitness.toFixed(2)
      : 'N/A';

    const message = `共 ${total_strategies} 个策略，平均适应度 ${avgFitnessStr}，展示前 ${rankings.length} 名（data_source=${data_source}）`;

    return {
      success: true,
      data: {
        ...data,
        rankings,
        total_strategies,
      },
      message,
      metadata: {
        data_source,
        total_strategies,
        avg_fitness,
        displayed: rankings.length,
      },
    };
  }
}
