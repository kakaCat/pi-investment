import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { evolutionRunPrompt, type EvolutionRunParams, type EvolutionRunResult } from './prompt';

export class EvolutionRunTool extends BaseTool<EvolutionRunParams, EvolutionRunResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_run',
    category: 'evolution',
    version: '1.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = evolutionRunPrompt;

  constructor(private aos: AgentOSClient) {
    super();
  }

  protected validate(params: EvolutionRunParams): ValidationResult {
    const { strategy_id, mode, generations } = params;

    // strategy_id 校验
    if (strategy_id !== undefined && strategy_id <= 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'strategy_id',
        issue: 'strategy_id 必须是正整数',
      };
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
    const result = await this.aos.evolution.run({
      strategy_id: params.strategy_id,
      mode: params.mode || 'propose',
      generations: params.generations || 3,
    });

    return result as EvolutionRunResult;
  }

  protected wrap(data: EvolutionRunResult, context: ToolContext): ToolResponse<EvolutionRunResult> {
    const { mode, proposals, fitness_improvement } = data;

    let message = `进化模式: ${mode}`;

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
