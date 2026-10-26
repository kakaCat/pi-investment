import { describe, expect, it } from 'vitest';
import { DailyDistillTool } from '../src/tools/DailyDistillTool/DailyDistillTool';

function makeTool(learningResult: any) {
  const calls: Array<{ name: string; args: any }> = [];
  const ctx = {
    tools: {
      execute: async (req: any) => {
        calls.push({ name: req.name, args: req.arguments });
        if (req.name === 'learning_analyze') return { value: learningResult };
        if (req.name === 'prompt_evolver') {
          return { value: { proposals: [], summary: 'ok', applied_count: 0, results: [] } };
        }
        throw new Error(`unexpected tool: ${req.name}`);
      },
    },
  } as any;
  return { tool: new DailyDistillTool(ctx, {} as any) as any, calls };
}

describe('daily_distill 建议供给', () => {
  it('样本不足零建议时不调用 prompt_evolver', async () => {
    const { tool, calls } = makeTool({ patterns: [], suggestions: [], sample_count: 2 });
    const result = await tool.execute({ days: 7, auto_apply: false }, {});
    expect(calls.map(c => c.name)).toEqual(['learning_analyze']);
    expect(result.evolver_result.applied_count).toBe(0);
    expect(result.summary).toContain('蒸馏建议: 0 条');
  });

  it('自动应用只向 prompt_evolver 提供一个主题', async () => {
    const { tool, calls } = makeTool({
      patterns: [],
      suggestions: ['主题一', '主题二', '主题三'],
      sample_count: 20,
    });
    await tool.execute({ days: 7, auto_apply: true }, {});
    const evolver = calls.find(c => c.name === 'prompt_evolver');
    expect(evolver.args.suggestions).toHaveLength(1);
    expect(evolver.args.suggestions[0].content).toBe('主题一');
    expect(evolver.args.dry_run).toBe(false);
  });
});
