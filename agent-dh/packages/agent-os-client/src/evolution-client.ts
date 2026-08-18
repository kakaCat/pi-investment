import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type {
  EvolutionLeaderboardParams,
  EvolutionLeaderboardResponse,
  EvolutionRunParams,
  EvolutionRunResponse,
  RegistryClientConfig,
} from './types.js';

/**
 * EvolutionClient — Agent OS evolution APIs.
 *
 * NOTE: the Agent OS server does not implement /api/v1/evolution/*
 * yet (verified live: 404). The client is contract-ready; until the
 * routes land, calls reject with a clear error naming the missing
 * endpoint so plugins can degrade gracefully.
 */
export class EvolutionClient {
  private client: AxiosInstance;

  constructor(config: RegistryClientConfig) {
    this.client = createHttpClient(config);
  }

  /**
   * Run a strategy evolution round.
   */
  async run(params: EvolutionRunParams): Promise<EvolutionRunResponse> {
    const strategyId =
      params.strategy_id !== undefined && params.strategy_id !== null
        ? String(params.strategy_id).trim()
        : '';
    if (strategyId === '') {
      throw new Error('strategy_id is required');
    }
    const response = await this.client.post<EvolutionRunResponse>(
      '/api/v1/evolution/run',
      {
        ...params,
        strategy_id: strategyId,
      }
    );
    return response.data;
  }

  /**
   * Fetch the evolution leaderboard.
   */
  async getLeaderboard(
    params?: EvolutionLeaderboardParams
  ): Promise<EvolutionLeaderboardResponse> {
    const response = await this.client.get<EvolutionLeaderboardResponse>(
      '/api/v1/evolution/leaderboard',
      { params: params?.limit ? { limit: params.limit } : undefined }
    );
    return response.data;
  }
}
