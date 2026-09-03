import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { evolutionRunPrompt, type EvolutionRunParams, type EvolutionRunResult } from './prompt';
import { allFitnessArePlaceholder, textSignalsPlaceholder } from '../../placeholder';

export class EvolutionRunTool extends BaseTool<EvolutionRunParams, EvolutionRunResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_run',
    category: 'evolution',
    version: '1.1.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = evolutionRunPrompt;

  constructor(private aos: AgentOSClient) {
    super();
  }

  protected validate(params: EvolutionRunParams): ValidationResult {
    const { strategy_id, mode, generations } = params;

    // strategy_id 校验 (兼容 string/number)
    if (strategy_id !== undefined && strategy_id !== null) {
      const id = typeof strategy_id === 'string' ? parseInt(strategy_id, 10) : strategy_id;
      if (isNaN(id) || id <= 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'strategy_id',
          issue: 'strategy_id 必须是正整数',
        };
      }
    }

    // mode 校验
    if (mode && !['full', 'propose', 'validate'].includes(mode)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'mode',
        issue: 'mode 必须是 full、propose 或 validate',
        expected: 'full | propose | validate',
      };
    }

    // generations 校验
    if (generations !== undefined && (generations <= 0 || generations > 10)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'generations',
        issue: 'generations 必须在 1-10 之间',
        expected: '1 <= generations <= 10',
      };
    }

    return { success: true };
  }

  protected async execute(params: EvolutionRunParams, context: ToolContext): Promise<EvolutionRunResult> {
    const result: any = await this.aos.evolution.run({
      strategy_id: params.strategy_id,
      mode: params.mode || 'propose',
      generations: params.generations || 3,
    });

    const proposals: any[] = Array.isArray(result?.proposals) ? result.proposals : [];

    // RFC 012 P0：占位结果拦截——Agent OS 在策略从未真实回测时用 0.05×i 阶梯
    // 冒充适应度（rationale 自曝"基线收益 0.00%"，见 placeholder.ts）。命中即降级，
    // 不展示占位 proposals/提升率；proposals 清空并给出原因，避免 agent 误用假参数。
    const numericPlaceholder = proposals.length > 0
      && allFitnessArePlaceholder(proposals.map((p: any) => p.estimated_fitness ?? p.fitness ?? p.expected_fitness));
    const textualPlaceholder = textSignalsPlaceholder(
      ...proposals.flatMap((p: any) => [p?.rationale, p?.action]),
      result?.rationale,
    );

    if (numericPlaceholder || textualPlaceholder) {
      return sanitizeLossless({
        strategy_id: result?.strategy_id != null ? Number(result.strategy_id) : params.strategy_id,
        mode: result?.mode ?? params.mode ?? 'propose',
        proposals: [],
        data_source: 'degraded',
        degraded_reason:
          'Agent OS 返回的进化结果为启发式占位（estimated_fitness 呈 0.05×i 阶梯，' +
          'rationale 自曝"基线收益 0.00%"——策略从未跑过真实回测，baseline=0 触发占位逻辑）。' +
          '占位 proposals/适应度提升已拦截不展示。真实策略进化请使用 qv2 策略进化引擎（RFC 012）。',
      }) as EvolutionRunResult;
    }

    // 2026-08-30 修复：agent-os 返回的 strategy_id 为 string，而输出 schema 要求 number；
    // 且 proposals/best_params 可能含 undefined 触发 lossless 校验失败。统一归一化+清洗。
    return sanitizeLossless({
      ...(result ?? {}),
      strategy_id: result?.strategy_id != null ? Number(result.strategy_id) : undefined,
      proposals: Array.isArray(result?.proposals) ? result.proposals : [],
      data_source: 'agent_os',
    }) as EvolutionRunResult;
  }

  protected wrap(data: EvolutionRunResult, context: ToolContext): ToolResponse<EvolutionRunResult> {
    const { mode, proposals, fitness_improvement, data_source, degraded_reason } = data;

    if (data_source === 'degraded') {
      const message = `进化不可用（data_source=degraded）：${degraded_reason || '占位结果已拦截'}`;
      return {
        success: true,
        data: { ...data, proposals: [], fitness_improvement: undefined as any },
        message,
        metadata: {
          data_source,
          mode,
          proposal_count: 0,
        },
      };
    }

    let message = `进化模式: ${mode} (data_source=${data_source})`;

    if (proposals && proposals.length > 0) {
      message += `, 生成 ${proposals.length} 个改进建议`;
    }

    if (fitness_improvement !== undefined) {
      message += `, 适应度提升 ${fitness_improvement.toFixed(2)}%`;
    }

    return {
      success: true,
      data,
      message,
      metadata: {
        mode,
        proposal_count: proposals?.length || 0,
        fitness_improvement,
      },
    };
  }
}
