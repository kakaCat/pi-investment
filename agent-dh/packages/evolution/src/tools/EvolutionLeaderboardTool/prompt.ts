/**
 * EvolutionLeaderboardTool - 策略进化排行榜工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * EvolutionLeaderboardTool 参数
 */
export interface EvolutionLeaderboardParams {
  limit?: number;
}

/**
 * EvolutionLeaderboardTool 返回结果
 */
export interface EvolutionLeaderboardResult {
  rankings: Array<{
    strategy_id: number;
    strategy_name: string;
    fitness: number;
    rank: number;
  }>;
  total_strategies: number;
  avg_fitness: number;
}

/**
 * EvolutionLeaderboardTool Prompt
 */
export const evolutionLeaderboardPrompt: ToolPrompt<EvolutionLeaderboardParams, EvolutionLeaderboardResult> = {
  description: '查询策略进化排行榜：各策略的适应度评分与排名。适用于：比较策略优劣、决定启用/停用哪些策略、跟踪 evolution_run 的进化效果。',

  useCases: [
    '比较策略优劣，选择最佳策略',
    '决定启用/停用哪些策略',
    '跟踪进化效果，验证参数优化成果',
  ],

  examples: [
    {
      title: '查询排名前 5 的策略',
      input: { limit: 5 },
      output: {
        rankings: [
          { strategy_id: 178, strategy_name: 'MACD突破', fitness: 1.45, rank: 1 },
          { strategy_id: 201, strategy_name: '动量轮动', fitness: 1.32, rank: 2 },
          { strategy_id: 156, strategy_name: '均值回归', fitness: 1.18, rank: 3 },
        ],
        total_strategies: 25,
        avg_fitness: 1.08,
      },
      explanation: '返回适应度最高的 5 个策略',
    },
    {
      title: '查询所有策略排名（默认前10）',
      input: {},
      output: {
        rankings: [],
        total_strategies: 25,
        avg_fitness: 1.08,
      },
      explanation: '不传 limit 参数时默认返回前 10 名',
    },
  ],
};
