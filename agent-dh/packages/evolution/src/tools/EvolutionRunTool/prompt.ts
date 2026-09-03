/**
 * EvolutionRunTool - 策略进化执行工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * EvolutionRunTool 参数
 */
export interface EvolutionRunParams {
  strategy_id?: number;
  mode?: 'full' | 'propose' | 'validate';
  generations?: number;
}

/**
 * EvolutionRunTool 返回结果
 */
export interface EvolutionRunResult {
  strategy_id?: number;
  mode: string;
  proposals: any[];
  best_params?: Record<string, any>;
  fitness_improvement?: number;
  backtest_result?: Record<string, any>;
  /** agent_os=Agent OS 原始数据 / degraded=占位已拦截 */
  data_source?: 'agent_os' | 'degraded';
  /** degraded 时的具体原因（RFC 012 P0 诚实降级） */
  degraded_reason?: string;
}

/**
 * EvolutionRunTool Prompt
 */
export const evolutionRunPrompt: ToolPrompt<EvolutionRunParams, EvolutionRunResult> = {
  description: '执行策略进化：回测参数变体、评估适应度、生成改进建议（耗时操作，最长等待 60 秒）。适用于：定期（如每周）优化策略参数、策略表现下滑后寻找改进方向。查看各策略进化历史与排名用 evolution_leaderboard；验证改进后的策略用 strategy_execute(mode=backtest)。⚠️ RFC 012 P0 起：若返回 data_source=degraded 说明 Agent OS 只给了占位结果（策略从未真实回测），不执行任何基于占位 fitness 的决策；真实策略进化须 qv2 策略进化引擎就绪后使用。',

  parameters: {
    strategy_id: {
      type: 'number',
      description: '要进化的策略 ID（可选，默认对所有活跃策略）',
    },
    mode: {
      type: 'string',
      description: "进化模式：full（生成+验证+回测）/ propose（仅生成建议）/ validate（仅验证）",
      enum: ['full', 'propose', 'validate'],
    },
    generations: {
      type: 'number',
      description: '进化代数（可选，默认 3）',
    },
  },

  useCases: [
    '定期（如每周）优化策略参数',
    '策略表现下滑后寻找改进方向',
    '探索参数空间寻找更优配置',
  ],

  examples: [
    {
      title: '对单个策略生成改进建议',
      input: { strategy_id: 178, mode: 'propose', generations: 3 },
      output: {
        strategy_id: 178,
        mode: 'propose',
        proposals: [
          { params: { threshold: 0.8 }, expected_fitness: 1.25 },
          { params: { threshold: 0.75 }, expected_fitness: 1.18 },
        ],
        best_params: { threshold: 0.8 },
        fitness_improvement: 15.5,
      },
      explanation: '运行 3 代进化，生成参数改进建议',
    },
    {
      title: '完整进化周期（生成+验证+回测）',
      input: { strategy_id: 201, mode: 'full', generations: 5 },
      output: {
        strategy_id: 201,
        mode: 'full',
        proposals: [],
        best_params: { lookback: 20, threshold: 0.65 },
        fitness_improvement: 22.3,
        backtest_result: { sharpe: 1.45, max_drawdown: -0.12 },
      },
      explanation: '运行完整进化周期，包含回测验证',
    },
  ],

  output: {
    schema: {
      type: 'object',
      properties: {
        strategy_id: { type: 'number', description: '策略 ID（可选）' },
        mode: { type: 'string', description: '实际执行的进化模式' },
        proposals: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '生成的参数改进建议' },
        best_params: { type: 'object', additionalProperties: true, description: '最优参数（可选）' },
        fitness_improvement: { type: 'number', description: '适应度提升百分比（可选）' },
        backtest_result: { type: 'object', additionalProperties: true, description: '回测结果（可选）' },
        data_source: { type: 'string', enum: ['agent_os', 'degraded'], description: '数据来源：agent_os=原始 / degraded=占位已拦截' },
        degraded_reason: { type: 'string', description: 'degraded 时的原因' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
};
