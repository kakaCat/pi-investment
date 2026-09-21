/**
 * EvolutionRunTool - 策略进化执行工具类型和提示词定义（RFC 012 P2 版）
 *
 * 数据源：quantsys-v2 策略进化引擎（:5001，真实回测进化，RFC 012 P1）。
 * 不再是 Agent OS 占位源——引擎内建诚实降级（data_source=degraded 时绝不产出占位 fitness）。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * EvolutionRunTool 参数
 */
export interface EvolutionRunParams {
  strategy_id: number;
  symbol: string;
  /** 回测窗口开始（YYYY-MM-DD）；缺省自动取最近 365 天 */
  start_date?: string;
  /** 回测窗口结束（YYYY-MM-DD）；缺省今天 */
  end_date?: string;
  /** full=完整进化（生成+逐变体回测）/ propose=生成改进建议（含回测验证） */
  mode?: 'full' | 'propose';
  /** 进化代数（默认 3；full 模式变体数随代数增长，耗时随之增加） */
  generations?: number;
  /** 初始资金（默认 1000000） */
  initial_cash?: number;
}

/**
 * EvolutionRunTool 返回结果（qv2 camelCase → 工具 snake_case 归一后形状）
 */
export interface EvolutionRunResult {
  success?: boolean;
  run_id?: string;
  strategy_id?: number;
  symbol?: string;
  mode?: string;
  /** 回测窗口（YYYY-MM-DD~YYYY-MM-DD） */
  kline_window?: string;
  /** qv2_real=qv2 真实回测进化 / degraded=引擎诚实降级（无占位数字） */
  data_source?: 'qv2_real' | 'degraded';
  /** degraded 时的具体原因 */
  degraded_reason?: string;
  total_variants?: number;
  success_variants?: number;
  degraded_variants?: number;
  best_params?: Record<string, any>;
  best_metrics?: Record<string, any> | null;
  fitness?: number | null;
  fitness_improvement?: number | null;
  proposals?: Array<{
    variant?: number;
    params?: Record<string, any>;
    estimated_fitness?: number | null;
    metrics?: Record<string, any> | null;
    rationale?: string | null;
    [key: string]: any;
  }>;
  run_at?: string;
  [key: string]: any;
}

/**
 * EvolutionRunTool Prompt
 */
export const evolutionRunPrompt: ToolPrompt<EvolutionRunParams, EvolutionRunResult> = {
  description: '执行策略进化：对指定策略在指定标的/回测窗口上跑一轮真实回测进化（参数网格 → 逐变体回测 → 同批 fitness 归一 → 生成改进建议并落库）。适用于：定期（如每周）优化策略参数、策略表现下滑后寻找改进方向。查看该策略的进化历史排行用 evolution_leaderboard；验证改进后的策略用 strategy_execute(mode=backtest)。真实数据来源 quantsys-v2 策略进化引擎（RFC 012）；返回 data_source=degraded 表示引擎诚实降级（数据源不可用/样本不足），此时无任何 proposals，禁止基于降级结果做决策。',

  parameters: {
    strategy_id: {
      type: 'number',
      description: '要进化的策略 ID（必填，经 strategy_list 获取）',
      required: true,
    },
    symbol: {
      type: 'string',
      description: '回测标的（6 位 A 股代码，必填，如 600519）',
      required: true,
    },
    start_date: {
      type: 'string',
      description: '回测窗口开始（YYYY-MM-DD）；缺省自动取最近 365 天',
    },
    end_date: {
      type: 'string',
      description: '回测窗口结束（YYYY-MM-DD）；缺省今天',
    },
    mode: {
      type: 'string',
      description: '进化模式：full（完整进化，变体随代数增长，耗时更长）/ propose（生成改进建议，含回测验证）',
      enum: ['full', 'propose'],
      default: 'propose',
    },
    generations: {
      type: 'number',
      description: '进化代数（默认 3）',
      default: 3,
    },
    initial_cash: {
      type: 'number',
      description: '回测初始资金（默认 1000000）',
      default: 1000000,
    },
  },

  useCases: [
    '定期（如每周）优化策略参数',
    '策略表现下滑后寻找改进方向',
    '探索参数空间寻找更优配置',
  ],

  examples: [
    {
      title: '对单个策略生成改进建议（真实回测进化）',
      input: { strategy_id: 178, symbol: '600519', start_date: '2025-09-01', end_date: '2026-09-05', mode: 'propose', generations: 1 },
      output: {
        success: true,
        run_id: 'b4f5212a',
        strategy_id: 178,
        symbol: '600519',
        mode: 'propose',
        data_source: 'qv2_real',
        total_variants: 7,
        success_variants: 7,
        degraded_variants: 0,
        proposals: [
          { variant: 5, params: { lookback: 15 }, estimated_fitness: 1.25, rationale: '调低 lookback 至 15，短线反转捕捉更灵敏' },
        ],
        best_params: { lookback: 15 },
        fitness_improvement: 8.2,
      },
      explanation: '跑一轮真实回测进化（7 个变体），返回最优参数与改进建议',
    },
    {
      title: '完整进化周期（full 模式）',
      input: { strategy_id: 178, symbol: '000858', mode: 'full', generations: 3 },
      output: {
        success: true,
        run_id: '07598ae7',
        strategy_id: 178,
        symbol: '000858',
        mode: 'full',
        data_source: 'qv2_real',
        total_variants: 15,
        best_params: { lookback: 20, threshold: 0.65 },
        fitness_improvement: 22.3,
      },
      explanation: '完整进化周期（15 个变体），包含回测验证与落库',
    },
  ],

  output: {
    schema: {
      type: 'object',
      properties: {
        success: { type: 'boolean', description: '引擎执行是否成功' },
        run_id: { type: 'string', description: '进化批次 ID（落库主键）' },
        strategy_id: { type: 'number', description: '策略 ID' },
        symbol: { type: 'string', description: '回测标的代码' },
        mode: { type: 'string', description: '实际执行的进化模式' },
        kline_window: { type: 'string', description: '回测窗口' },
        data_source: { type: 'string', enum: ['qv2_real', 'degraded'], description: '数据来源：qv2_real=真实回测进化 / degraded=引擎诚实降级' },
        degraded_reason: { type: 'string', description: 'degraded 时的原因' },
        total_variants: { type: 'number', description: '总变体数' },
        success_variants: { type: 'number', description: '回测成功变体数' },
        degraded_variants: { type: 'number', description: '降级变体数' },
        best_params: { type: 'object', additionalProperties: true, description: '最优参数' },
        best_metrics: { type: 'object', additionalProperties: true, description: '最优变体回测指标' },
        fitness: { type: 'number', description: '最优 fitness' },
        fitness_improvement: { type: 'number', description: '相对 base 变体的 fitness 提升（%）' },
        proposals: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: true,
            description: '改进建议（参数+估计 fitness+理由）',
          },
          description: '生成的参数改进建议',
        },
        run_at: { type: 'string', description: '执行时间' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },
};
