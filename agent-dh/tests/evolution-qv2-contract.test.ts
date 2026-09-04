/**
 * RFC 012 P2 契约测试：evolution 工具消费 qv2 策略进化引擎（真实回测）响应
 *
 * 背景：P2 将 evolution_run / evolution_leaderboard 数据源从 Agent OS（:8080，占位
 * 0.05×i 冒充）切到 quantsys-v2 策略进化引擎（:5001，RFC 012 P1 落位，camelCase 契约）。
 * 验收：qv2 camelCase 响应 → 工具 snake_case 输出正确归一；引擎诚实降级（degraded）
 * /空态（empty）不展示占位数字；缺必填参数被 INPUT_ERROR 拦截。
 * lessons：工具 schema 契约必须与线上数据模型对齐（qv2 engine 端点 2026-09-05 curl 实测形状）。
 */
import { describe, expect, it, vi } from 'vitest';
import { EvolutionRunTool } from '../packages/evolution/src/tools/EvolutionRunTool/EvolutionRunTool';
import { EvolutionLeaderboardTool } from '../packages/evolution/src/tools/EvolutionLeaderboardTool/EvolutionLeaderboardTool';
import { ErrorType } from '@pi-investment/core-tool';

// qv2 POST /api/evolution/engine/run 真实响应（2026-09-05 curl 实测：camelCase、dataSource）
const REAL_RUN = {
  success: true,
  runId: 'b4f5212a3c2d',
  strategyId: 635,
  symbol: '600519',
  mode: 'propose',
  klineWindow: '2025-09-01~2026-09-05',
  dataSource: 'qv2_real',
  totalVariants: 7,
  successVariants: 7,
  degradedVariants: 0,
  bestParams: { lookback: 15, threshold: 0.7 },
  bestMetrics: { sharpe: 1.45, maxDrawdown: -0.08 },
  fitness: 1.45,
  fitnessImprovement: 8.2,
  proposals: [
    {
      variant: 5,
      params: { lookback: 15, threshold: 0.7 },
      estimatedFitness: 1.45,
      metrics: { sharpe: 1.45 },
      rationale: '调低 lookback 至 15，短线反转捕捉更灵敏',
    },
  ],
  runAt: '2026-09-05T10:00:00',
};

// 引擎诚实降级响应（RFC 012 P1：绝不产出占位 fitness）
const DEGRADED_RUN = {
  success: false,
  dataSource: 'degraded',
  degradedReason: '样本不足：回测交易数 < 3（策略在窗口内无交易）',
  totalVariants: 0,
  successVariants: 0,
  degradedVariants: 0,
};

function makeRunTool(raw: any, request: any = {}) {
  const qv2: any = {
    evolutionRunStrategy: vi.fn().mockResolvedValue(raw),
  };
  return { tool: new EvolutionRunTool(qv2), qv2 };
}

const RUN_ARGS = {
  strategy_id: 635,
  symbol: '600519',
  mode: 'propose' as const,
  generations: 1,
};

describe('EvolutionRunTool RFC 012 P2 契约（qv2 引擎）', () => {
  it('qv2 camelCase 响应 → snake_case 输出 + proposals 键归一', async () => {
    const { tool, qv2 } = makeRunTool(REAL_RUN);
    const out: any = await (tool as any).execute(RUN_ARGS, {} as any);
    // 请求参数 camelCase 映射正确
    expect(qv2.evolutionRunStrategy).toHaveBeenCalledWith({
      strategyId: 635,
      symbol: '600519',
      startDate: expect.any(String),
      endDate: expect.any(String),
      mode: 'propose',
      generations: 1,
      initialCash: 1000000,
    });
    // 响应归一：snake_case 键、proposals.estimated_fitness
    expect(out.data_source).toBe('qv2_real');
    expect(out.run_id).toBe('b4f5212a3c2d');
    expect(out.strategy_id).toBe(635);
    expect(out.best_params).toEqual({ lookback: 15, threshold: 0.7 });
    expect(out.fitness_improvement).toBe(8.2);
    expect(out.proposals).toHaveLength(1);
    expect(out.proposals[0].estimated_fitness).toBe(1.45);
    expect(out.proposals[0].params.lookback).toBe(15);
  });

  it('引擎诚实降级 → data_source=degraded + 原因透传（无占位 proposals）', async () => {
    const { tool } = makeRunTool(DEGRADED_RUN);
    const out: any = await (tool as any).execute(RUN_ARGS, {} as any);
    expect(out.data_source).toBe('degraded');
    expect(out.degraded_reason).toContain('样本不足');
    expect(out.proposals).toBeUndefined();
  });

  it('缺 strategy_id/symbol → INPUT_ERROR 拦截（不再允许无标的进化）', async () => {
    const { tool } = makeRunTool(REAL_RUN);
    const v1 = (tool as any).validate({ symbol: '600519' });
    expect(v1.success).toBe(false);
    expect(v1.field).toBe('strategy_id');
    const v2 = (tool as any).validate({ strategy_id: 635 });
    expect(v2.success).toBe(false);
    expect(v2.field).toBe('symbol');
  });

  it('mode=validate 已移除（qv2 引擎仅 full/propose）', async () => {
    const { tool } = makeRunTool(REAL_RUN);
    const v = (tool as any).validate({ ...RUN_ARGS, mode: 'validate' });
    expect(v.success).toBe(false);
    expect(v.errorType).toBe('INPUT_ERROR');
  });
});

// qv2 GET /api/evolution/engine/runs 真实响应形状：每 run 一条 best 行（fitness 降序）
const RUNS_ROWS = {
  runs: [
    {
      runId: '07598ae74cef',
      strategyId: 635,
      variant: 9,
      variantKey: "{'lookback': 15, 'threshold': 0.7}",
      params: { lookback: 15, threshold: 0.7 },
      fitness: 1.45,
      metrics: { sharpe: 1.45, maxDrawdown: -0.08 },
      computedAt: '2026-09-05T10:00:00',
    },
    {
      runId: 'b4f5212a3c2d',
      strategyId: 635,
      variant: 5,
      variantKey: "{'lookback': 20, 'threshold': 0.65}",
      params: { lookback: 20, threshold: 0.65 },
      fitness: 1.34,
      metrics: { sharpe: 1.34 },
      computedAt: '2026-09-03T09:00:00',
    },
    {
      // 整批降级 run 的最近一行（fitness NULL，诚实失败记录）
      runId: 'a1b2c3d4',
      strategyId: 635,
      variant: 0,
      variantKey: 'baseline',
      params: null,
      fitness: null,
      metrics: null,
      degradedReason: '数据源不可用：外部行情源超时',
      computedAt: '2026-09-01T09:00:00',
    },
  ],
};

function makeLeaderboardTool(raw: any) {
  const qv2: any = {
    getStrategyEvolutionRuns: vi.fn().mockResolvedValue(raw),
  };
  return { tool: new EvolutionLeaderboardTool(qv2), qv2 };
}

const LB_ARGS = { strategy_id: 635, limit: 10 };

describe('EvolutionLeaderboardTool RFC 012 P2 契约（qv2 引擎）', () => {
  it('runs 行 → rankings 排行（fitness 降序、rank 正确、降级行标注不参与均值）', async () => {
    const { tool, qv2 } = makeLeaderboardTool(RUNS_ROWS);
    const out: any = await (tool as any).execute(LB_ARGS, {} as any);
    expect(qv2.getStrategyEvolutionRuns).toHaveBeenCalledWith(635, 10);
    expect(out.data_source).toBe('qv2_real');
    expect(out.total_runs).toBe(3);
    expect(out.rankings).toHaveLength(3);
    expect(out.rankings[0].rank).toBe(1);
    expect(out.rankings[0].run_id).toBe('07598ae74cef');
    expect(out.rankings[0].fitness).toBe(1.45);
    expect(out.rankings[1].fitness).toBe(1.34);
    // 降级行保留并标注（不静默丢弃），fitness=null
    expect(out.rankings[2].fitness).toBeNull();
    expect(out.rankings[2].degraded_reason).toContain('数据源不可用');
    // avg_fitness 只算真实 fitness（1.45+1.34)/2
    expect(out.avg_fitness).toBe(1.395);
  });

  it('无进化记录 → data_source=empty + 诚实空态（不展示排名）', async () => {
    const { tool } = makeLeaderboardTool({ runs: [] });
    const out: any = await (tool as any).execute(LB_ARGS, {} as any);
    expect(out.data_source).toBe('empty');
    expect(out.rankings).toEqual([]);
    expect(out.total_runs).toBe(0);
    expect(out.degraded_reason).toContain('无真实进化记录');
  });

  it('引擎按轮次倒序返回时，工具端按 fitness DESC 重排（rank 即真实排行）', async () => {
    // Live 实测（2026-09-05）：GET runs 按 created_at DESC 返回（轮次倒序非排行序），
    // 工具端须重排——输入顺序刻意乱序：0.95 → 1.0(旧) → 0.90 → 1.0(新)
    const { tool } = makeLeaderboardTool({
      runs: [
        { runId: 'r-low', strategyId: 635, fitness: 0.95, computedAt: '2026-09-05T03:18:49' },
        { runId: 'r-top-old', strategyId: 635, fitness: 1.0, computedAt: '2026-09-05T03:17:51' },
        { runId: 'r-bot', strategyId: 635, fitness: 0.9, computedAt: '2026-09-05T03:18:11' },
        { runId: 'r-top-new', strategyId: 635, fitness: 1.0, computedAt: '2026-09-05T03:18:30' },
      ],
    });
    const out: any = await (tool as any).execute(LB_ARGS, {} as any);
    expect(out.data_source).toBe('qv2_real');
    expect(out.rankings.map((r: any) => r.run_id)).toEqual([
      'r-top-new', // 1.0 且更新
      'r-top-old', // 1.0 且更旧（同分确定性：新→旧）
      'r-low', // 0.95
      'r-bot', // 0.90
    ]);
    expect(out.rankings[0].rank).toBe(1);
    expect(out.rankings[3].rank).toBe(4);
    expect(out.avg_fitness).toBe(0.9625);
  });

  it('全部降级（fitness 全 NULL）→ data_source=degraded，暴露"进化过但失败"', async () => {
    const { tool } = makeLeaderboardTool({
      runs: [{ runId: 'x1', strategyId: 635, fitness: null, degradedReason: '样本不足：≥10 只' }],
    });
    const out: any = await (tool as any).execute(LB_ARGS, {} as any);
    expect(out.data_source).toBe('degraded');
    expect(out.rankings).toEqual([]);
    expect(out.total_runs).toBe(1);
    expect(out.degraded_reason).toContain('样本不足');
  });

  it('缺 strategy_id → INPUT_ERROR（qv2 排行按策略维度查询，必填）', async () => {
    const { tool } = makeLeaderboardTool(RUNS_ROWS);
    const v = (tool as any).validate({ limit: 10 });
    expect(v.success).toBe(false);
    expect(v.field).toBe('strategy_id');
  });
});
