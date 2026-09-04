/**
 * EvolutionLeaderboardTool - 策略进化排行榜工具类型和提示词定义（RFC 012 P2 版）
 *
 * 数据源：quantsys-v2 策略进化引擎（:5001）。语义 = 指定策略的真实进化历史排行：
 * 每轮进化 run 取其 fitness 最优变体行，按 fitness 降序排（fitness 为真实回测 fitness，
 * 同批变体归一后的绝对值；非占位、非虚构）。A 链（Agent OS evolution）已退役。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * EvolutionLeaderboardTool 参数
 */
export interface EvolutionLeaderboardParams {
  /** 要查询进化历史的策略 ID（必填，经 strategy_list 获取） */
  strategy_id?: number;
  /** 返回最近几轮进化 run 的排行（1-100），默认 10 */
  limit?: number;
}

/**
 * EvolutionLeaderboardTool 返回结果
 */
export interface EvolutionLeaderboardResult {
  strategy_id?: number;
  rankings: Array<{
    rank: number;
    run_id: string;
    strategy_id: number;
    fitness: number | null;
    best_params?: Record<string, any>;
    variant_key?: string;
    metrics?: Record<string, any> | null;
    degraded_reason?: string | null;
    computed_at?: string;
  }>;
  /** 参与排行的进化 run 数 */
  total_runs: number;
  /** 非降级 run 的真实 fitness 均值 */
  avg_fitness?: number;
  /** qv2_real=真实回测进化 / degraded=引擎诚实降级无真实分 / empty=无进化记录 */
  data_source?: 'qv2_real' | 'degraded' | 'empty';
  /** degraded/empty 时的具体原因 */
  degraded_reason?: string;
}

/**
 * EvolutionLeaderboardTool Prompt
 */
export const evolutionLeaderboardPrompt: ToolPrompt<EvolutionLeaderboardParams, EvolutionLeaderboardResult> = {
  description: '查询指定策略的进化历史排行（真实数据源 quantsys-v2 策略进化引擎）：每轮进化 run 取其最优变体行的 fitness，按 fitness 降序返回最近 N 轮。适用于：跟踪 evolution_run 的进化效果（各轮最优配置与 fitness 趋势）、决定是否采用更优参数。⚠️ data_source=degraded（引擎诚实降级）或 empty（该策略从未真实进化）时不展示任何排名；真实策略进化请先跑 evolution_run。',

  parameters: {
    strategy_id: {
      type: 'number',
      description: '要查询进化历史的策略 ID（必填，经 strategy_list 获取）',
      required: true,
    },
    limit: {
      type: 'number',
      description: '返回最近几轮进化 run 的排行（1-100），默认 10',
      default: 10,
      minimum: 1,
      maximum: 100,
      example: 10,
    },
  },

  useCases: [
    '跟踪某策略多轮进化后的最优 fitness 与参数收敛',
    '验证 evolution_run 是否产生更优配置',
    '对比策略不同进化批次的参数效果',
  ],

  examples: [
    {
      title: '查看策略 178 的进化历史排行',
      input: { strategy_id: 178, limit: 5 },
      output: {
        strategy_id: 178,
        rankings: [
          { rank: 1, run_id: '07598ae7', strategy_id: 178, fitness: 1.45, best_params: { lookback: 15, threshold: 0.7 }, computed_at: '2026-09-05' },
          { rank: 2, run_id: 'b4f5212a', strategy_id: 178, fitness: 1.34, best_params: { lookback: 20, threshold: 0.65 }, computed_at: '2026-09-03' },
        ],
        total_runs: 2,
        avg_fitness: 1.395,
        data_source: 'qv2_real',
      },
      explanation: '返回策略 178 最近 2 轮真实进化，best_params 为每轮最优变体参数',
    },
    {
      title: '策略从未进化（empty 诚实空态）',
      input: { strategy_id: 201, limit: 10 },
      output: {
        strategy_id: 201,
        rankings: [],
        total_runs: 0,
        data_source: 'empty',
        degraded_reason: '该策略在 qv2 策略进化引擎中无真实进化记录（先跑 evolution_run）。',
      },
      explanation: '无真实进化记录时不展示任何排名',
    },
  ],

  output: {
    schema: {
      type: 'object',
      properties: {
        strategy_id: { type: 'number', description: '策略 ID' },
        rankings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: true,
            description: '每轮进化 run 的最优变体行（fitness 降序）',
          },
          description: '进化历史排行',
        },
        total_runs: { type: 'number', description: '参与排行的进化 run 数' },
        avg_fitness: { type: 'number', description: '非降级 run 的真实 fitness 均值' },
        data_source: { type: 'string', enum: ['qv2_real', 'degraded', 'empty'], description: '数据来源：qv2_real=真实回测进化 / degraded=引擎诚实降级 / empty=无进化记录' },
        degraded_reason: { type: 'string', description: 'degraded/empty 时的原因' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
};
