import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { evolutionLeaderboardPrompt, type EvolutionLeaderboardParams, type EvolutionLeaderboardResult } from './prompt';

export class EvolutionLeaderboardTool extends BaseTool<EvolutionLeaderboardParams, EvolutionLeaderboardResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'evolution_leaderboard',
    category: 'evolution',
    version: '1.0.0',
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
    const result = await this.aos.evolution.getLeaderboard({
      limit: params.limit || 10,
    });

    return result as EvolutionLeaderboardResult;
  }

  protected wrap(data: EvolutionLeaderboardResult, context: ToolContext): ToolResponse<EvolutionLeaderboardResult> {
    const { rankings = [], total_strategies = 0, avg_fitness } = data;

    const avgFitnessStr = avg_fitness !== undefined && avg_fitness !== null
      ? avg_fitness.toFixed(2)
      : 'N/A';

    const message = `共 ${total_strategies} 个策略，平均适应度 ${avgFitnessStr}，展示前 ${rankings.length} 名`;

    return {
      success: true,
      data: {
        ...data,
        rankings,
        total_strategies,
      },
      message,
      metadata: {
        total_strategies,
        avg_fitness,
        displayed: rankings.length,
      },
    };
  }
}
