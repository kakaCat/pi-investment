/**
 * RFC 012 P0 契约测试：evolution 工具占位拦截（Agent OS 0.05×i 阶梯冒充）
 *
 * 背景（实测坐实 2026-09-03）：Agent OS legacy 进化在策略从未真实回测
 * （/api/performance/strategy/{id} 空 stats → baseline=0）时，用 estimated=0.05×i
 * 占位（evolution_handler.go:182-186）。工具不得把占位当真实 fitness/排名展示。
 *
 * 验收：占位命中 → data_source=degraded + 空榜/空 proposals + 原因；
 * 真实/空数据不被误伤。lessons：工具 schema 契约必须与线上数据模型对齐——
 * Agent OS 实际返回 {entries:[...]} 而工具 schema 用 rankings，透传曾显示空榜。
 */
import { describe, expect, it, vi } from 'vitest';
import {
  isAgentOsPlaceholderFitness,
  allFitnessArePlaceholder,
  textSignalsPlaceholder,
} from '../packages/evolution/src/placeholder';
import { EvolutionLeaderboardTool } from '../packages/evolution/src/tools/EvolutionLeaderboardTool/EvolutionLeaderboardTool';
import { EvolutionRunTool } from '../packages/evolution/src/tools/EvolutionRunTool/EvolutionRunTool';

describe('placeholder util', () => {
  it('识别 0.05×i 阶梯占位分（含浮点噪声 0.15000000000000002）', () => {
    expect(isAgentOsPlaceholderFitness(0.05)).toBe(true);
    expect(isAgentOsPlaceholderFitness(0.15000000000000002)).toBe(true);
    expect(isAgentOsPlaceholderFitness(0.2)).toBe(true);
    expect(isAgentOsPlaceholderFitness(0.5)).toBe(true);
  });

  it('不误伤真实 fitness 值', () => {
    expect(isAgentOsPlaceholderFitness(1.45)).toBe(false);
    expect(isAgentOsPlaceholderFitness(-0.1485)).toBe(false);
    expect(isAgentOsPlaceholderFitness(0)).toBe(false);
    expect(isAgentOsPlaceholderFitness(0.6)).toBe(false); // 超阶梯上限(0.5×10 代)
    expect(isAgentOsPlaceholderFitness('0.15')).toBe(false);
    expect(isAgentOsPlaceholderFitness(0.13)).toBe(false); // 非阶梯值
  });

  it('allFitnessArePlaceholder：全占位才 true，空数组不算', () => {
    expect(allFitnessArePlaceholder([0.05, 0.1, 0.15])).toBe(true);
    expect(allFitnessArePlaceholder([0.05, 1.45])).toBe(false);
    expect(allFitnessArePlaceholder([])).toBe(false);
  });

  it('文本信号：自曝"风险乘数/基线收益 0.00/to confirm"即占位', () => {
    expect(textSignalsPlaceholder('调整风险乘数至 0.85，在基线收益 0.00% 基础上评估')).toBe(true);
    expect(textSignalsPlaceholder('backtest this variant via /api/backtest/strategy to confirm')).toBe(true);
    expect(textSignalsPlaceholder('基于真实回测的改进建议')).toBe(false);
  });
});

describe('EvolutionLeaderboardTool P0 占位拦截', () => {
  // Agent OS 真实返回形状（curl 实测 2026-09-03）：{entries:[{strategy_id, fitness, ...}]}
  const PLACEHOLDER_RAW = {
    entries: [
      { strategy_id: '178', fitness: 0.15000000000000002, mode: 'propose', status: 'completed' },
      { strategy_id: '203', fitness: 0.1, mode: 'propose', status: 'completed' },
      { strategy_id: '636', fitness: 0.2, mode: 'propose', status: 'completed' },
    ],
  };

  function makeLeaderboard(raw: any) {
    const aos: any = { evolution: { getLeaderboard: vi.fn().mockResolvedValue(raw) } };
    return new EvolutionLeaderboardTool(aos);
  }

  it('全占位 → data_source=degraded、空榜、带原因', async () => {
    const tool = makeLeaderboard(PLACEHOLDER_RAW);
    const out = await (tool as any).execute({ limit: 10 }, {});
    expect(out.data_source).toBe('degraded');
    expect(out.rankings).toEqual([]);
    expect(out.total_strategies).toBe(3);
    expect(out.raw_count).toBe(3);
    expect(out.degraded_reason).toContain('占位');
  });

  it('真实 fitness → rankings 显式映射（entries 契约对齐）+ agent_os 标记', async () => {
    const tool = makeLeaderboard({
      entries: [
        { strategy_id: '178', fitness: 1.45 },
        { strategy_id: '201', fitness: -0.15 },
      ],
    });
    const out = await (tool as any).execute({ limit: 10 }, {});
    expect(out.data_source).toBe('agent_os');
    expect(out.rankings).toHaveLength(2);
    expect(out.rankings[0]).toEqual({ strategy_id: 178, strategy_name: 'strategy-178', fitness: 1.45, rank: 1 });
    expect(out.rankings[1]).toEqual({ strategy_id: 201, strategy_name: 'strategy-201', fitness: -0.15, rank: 2 });
  });

  it('空 entries → data_source=empty 诚实空态', async () => {
    const tool = makeLeaderboard({ entries: [] });
    const out = await (tool as any).execute({ limit: 10 }, {});
    expect(out.data_source).toBe('empty');
    expect(out.rankings).toEqual([]);
    expect(out.total_strategies).toBe(0);
  });
});

describe('EvolutionRunTool P0 占位拦截', () => {
  // aos evolution.run 实测返回（2026-09-03 POST /api/v1/evolution/run strategy_id=635）
  const PLACEHOLDER_RUN = {
    id: 'a9945dfd',
    strategy_id: '635',
    mode: 'propose',
    generations: 3,
    status: 'completed',
    fitness: 0.15000000000000002,
    fitness_improvement: 0.15000000000000002,
    proposals: [
      { variant: 1, risk_multiplier: 0.85, estimated_fitness: 0.05, rationale: '调整风险乘数至 0.85，在基线收益 0.00% 基础上评估', action: 'backtest this variant via /api/backtest/strategy to confirm' },
      { variant: 2, risk_multiplier: 0.9, estimated_fitness: 0.1, rationale: '调整风险乘数至 0.90，在基线收益 0.00% 基础上评估', action: 'backtest this variant via /api/backtest/strategy to confirm' },
      { variant: 3, risk_multiplier: 0.95, estimated_fitness: 0.15000000000000002, rationale: '调整风险乘数至 0.95，在基线收益 0.00% 基础上评估', action: 'backtest this variant via /api/backtest/strategy to confirm' },
    ],
    best_params: { risk_multiplier: 0.95, strategy_id: '635', variant: 3 },
  };

  function makeRun(raw: any) {
    const aos: any = { evolution: { run: vi.fn().mockResolvedValue(raw) } };
    return new EvolutionRunTool(aos);
  }

  it('占位 proposals（文本+数值双信号）→ degraded、proposals 清空、带原因', async () => {
    const tool = makeRun(PLACEHOLDER_RUN);
    const out = await (tool as any).execute({ strategy_id: 635, mode: 'propose', generations: 3 }, {});
    expect(out.data_source).toBe('degraded');
    expect(out.proposals).toEqual([]);
    expect(out.fitness_improvement).toBeUndefined();
    expect(out.degraded_reason).toContain('占位');
  });

  it('真实 run 返回 → 透传 + data_source=agent_os', async () => {
    const REAL_RUN = {
      strategy_id: '635',
      mode: 'full',
      fitness: 1.45,
      fitness_improvement: 15.5,
      proposals: [
        { params: { lookback: 20 }, expected_fitness: 1.45, rationale: '基于真实回测的改进建议' },
      ],
      best_params: { lookback: 20 },
    };
    const tool = makeRun(REAL_RUN);
    const out = await (tool as any).execute({ strategy_id: 635, mode: 'full' }, {});
    expect(out.data_source).toBe('agent_os');
    expect(out.strategy_id).toBe(635);
    expect(out.proposals).toHaveLength(1);
    expect(out.fitness_improvement).toBe(15.5);
  });
});
