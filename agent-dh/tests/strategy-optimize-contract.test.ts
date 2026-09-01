/**
 * G-1 契约测试：StrategyOptimizeTool execute 输出必须符合 output schema
 * （模拟绑定层校验——lessons：工具 schema 契约必须与线上数据模型对齐）
 */
import { describe, expect, it, vi } from 'vitest';
import { StrategyOptimizeTool } from '../packages/strategy/src/tools/StrategyOptimizeTool/StrategyOptimizeTool';

// 后端真实返回形状（2026-09-01 实测）：{success, results[], totalCombinations, successfulCombinations}
const BACKEND_SHAPE = {
  success: true,
  results: [
    { params: { fast_period: 8 }, sharpeRatio: 0.5, totalReturn: 0.1, maxDrawdown: -0.05, winRate: 0.55 },
    { params: { fast_period: 12 }, sharpeRatio: 1.2, totalReturn: 0.2, maxDrawdown: -0.08, winRate: 0.6 },
  ],
  totalCombinations: 2,
  successfulCombinations: 2,
};

function makeTool(raw: any) {
  const qv2: any = { optimizeStrategy: vi.fn().mockResolvedValue(raw) };
  return new StrategyOptimizeTool(qv2);
}

const ARGS = { strategy_id: 635, param_ranges: { fast_period: [8, 12] } };

describe('StrategyOptimizeTool G-1 契约', () => {
  it('后端 results[] 适配为 best_params/best_score/all_results', async () => {
    const tool = makeTool(BACKEND_SHAPE);
    const out: any = await (tool as any).execute(ARGS, {} as any);
    expect(out.best_params).toEqual({ fast_period: 12 });
    expect(out.best_score).toBe(1.2);
    expect(out.all_results).toHaveLength(2);
    expect(out.total_combinations).toBe(2);
    expect(typeof out.best_score.toFixed).toBe('function'); // render 不再崩
  });

  it('空结果兜底不崩（best_score=0）', async () => {
    const tool = makeTool({ success: true, results: [], totalCombinations: 0, successfulCombinations: 0 });
    const out: any = await (tool as any).execute(ARGS, {} as any);
    expect(out.best_score).toBe(0);
    expect(out.best_params).toEqual({});
    expect(out.all_results).toEqual([]);
    expect(out.best_score.toFixed(4)).toBe('0.0000');
  });

  it('optimization_target=return 时按 totalReturn 选最优', async () => {
    const tool = makeTool(BACKEND_SHAPE);
    const out: any = await (tool as any).execute({ ...ARGS, optimization_target: 'return' }, {} as any);
    expect(out.best_score).toBe(0.2);
    expect(out.best_params).toEqual({ fast_period: 12 });
  });

  it('后端异常形状（无 results 键）不崩', async () => {
    const tool = makeTool({ success: false });
    const out: any = await (tool as any).execute(ARGS, {} as any);
    expect(out.all_results).toEqual([]);
    expect(out.best_score).toBe(0);
  });
});
