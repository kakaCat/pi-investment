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
  avg_fitness?: number;
  /** agent_os=Agent OS 原始数据 / degraded=占位已拦截 / empty=无记录 */
  data_source?: 'agent_os' | 'degraded' | 'empty';
  /** degraded/empty 时的具体原因（RFC 012 P0 诚实降级） */
  degraded_reason?: string;
  /** 降级前源数据条数（degraded 时提供，便于追溯） */
  raw_count?: number;
}

/**
 * EvolutionLeaderboardTool Prompt
 */
export const evolutionLeaderboardPrompt: ToolPrompt<EvolutionLeaderboardParams, EvolutionLeaderboardResult> = {
  description: '查询策略进化排行榜：各策略的适应度评分与排名。适用于：比较策略优劣、决定启用/停用哪些策略、跟踪 evolution_run 的进化效果。⚠️ RFC 012 P0 起：若数据源为 Agent OS 占位分（0.05×i 阶梯，策略未真实回测时的启发式冒充），工具返回 data_source=degraded 空榜+原因，不会展示占位排名。',

  parameters: {
    limit: {
      type: 'number',
      description: '返回排名数量（1-50），默认 10',
      default: 10,
      minimum: 1,
      maximum: 50,
      example: 10,
    },
  },

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

  output: {
    schema: {
      type: 'object',
      properties: {
        rankings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              strategy_id: { type: 'number', description: '策略 ID' },
              strategy_name: { type: 'string', description: '策略名称' },
              fitness: { type: 'number', description: '适应度评分' },
              rank: { type: 'number', description: '排名' },
            },
            additionalProperties: true,
          },
        },
        total_strategies: { type: 'number', description: '策略总数' },
        avg_fitness: { type: 'number', description: '平均适应度（占位拦截后为空）' },
        data_source: { type: 'string', enum: ['agent_os', 'degraded', 'empty'], description: '数据来源：agent_os=原始 / degraded=占位已拦截 / empty=无记录' },
        degraded_reason: { type: 'string', description: 'degraded/empty 时的原因' },
        raw_count: { type: 'number', description: '降级前源数据条数' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
};
