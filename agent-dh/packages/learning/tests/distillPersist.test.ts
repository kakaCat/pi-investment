import { describe, it, expect, vi } from 'vitest';
import { LearningDistillTool } from '../src/tools/LearningDistillTool/LearningDistillTool';

/**
 * 2026-09-03 Fix③：learning_distill → learning_apply 闭环单测。
 *
 * 背景（审计 profit-engine-autonomy-full-flow-audit ③）：learning_apply 原是"假 applied:true"占位，
 * 且规则从不落库 → apply 永远"规则不存在"。Fix③ 让 distill 产出规则即落库（persistRules 回调），
 * apply 把 testing 候选转正 active。这里测工具层契约：
 *  - persistRules 成功：rules 富化 memory_id、persistence.persisted=total
 *  - persistRules 抛错：不吞错——persistence.error 带回、persisted=0
 *  - 蒸馏无经验/无规则：persistence 为 undefined（不写空壳记录）
 */

function makeTool(persistRules?: (rules: any[], meta: { source: string; target_format: string }) => Promise<any[]>) {
  return new LearningDistillTool(
    async () => [
      { id: 'exp_1', reward: 0.9, outcome: { success: true }, context: { symbol: '600519' }, action: { tool: 'portfolio_trade' }, tags: [], timestamp: new Date().toISOString(), agent_version: 't' },
      { id: 'exp_2', reward: 0.7, outcome: { success: true }, context: { symbol: '000858' }, action: { tool: 'portfolio_trade' }, tags: [], timestamp: new Date().toISOString(), agent_version: 't' },
    ],
    (options: any) => {
      // 模拟 distillRules：每个成功经验产出一条规则
      return options.experiences.map((exp: any, i: number) => ({
        id: `rule_${Date.now()}_${i}`,
        condition: `context matches ${JSON.stringify(exp.context)}`,
        action: `execute ${exp.action.tool}`,
        confidence: Math.min(0.99, exp.reward + 0.3),
        source_experiences: [exp.id],
        format: options.targetFormat,
      })).filter((r: any) => r.confidence >= options.minConfidence);
    },
    () => 'decision_tree_learning',
    (rules: any[], _exp: any[]) => ({ total_rules: rules.length, avg_confidence: rules.length ? 0.9 : 0, coverage: rules.length ? 1 : 0 }),
    persistRules
  );
}

describe('learning_distill Fix③ 规则落库（distill→apply 闭环）', () => {
  it('persistRules 成功时 rules 富化 memory_id 且 persistence 统计正确', async () => {
    const persistRules = vi.fn(async (rules: any[], meta: { source: string; target_format: string }) => {
      expect(meta.source).toBe('successful_trades');
      expect(meta.target_format).toBe('rule');
      return rules.map((r: any, i: number) => ({ ...r, rule_id: r.id, memory_id: `mem_${i}` }));
    });
    const tool = makeTool(persistRules);
    const res = await tool.call({ source: 'successful_trades', target_format: 'rule' } as any, {});
    expect(res.success).toBe(true);
    const data: any = res.data;
    expect(persistRules).toHaveBeenCalledTimes(1);
    // rules 已富化 memory_id
    expect(data.rules.length).toBeGreaterThan(0);
    for (const r of data.rules) expect(r.memory_id).toBeTruthy();
    // persistence 统计
    expect(data.persistence.persisted).toBe(data.rules.length);
    expect(data.persistence.total).toBe(data.rules.length);
    expect(data.persistence.failed).toBe(0);
    expect(data.persistence.error).toBeNull();
  });

  it('persistRules 抛错时不吞——persistence.error 带回、persisted=0，规则仍返回', async () => {
    const persistRules = vi.fn(async () => { throw new Error('OS memory down'); });
    const tool = makeTool(persistRules);
    const res = await tool.call({ source: 'successful_trades', target_format: 'rule' } as any, {});
    expect(res.success).toBe(true);
    const data: any = res.data;
    expect(data.persistence.persisted).toBe(0);
    expect(data.persistence.total).toBeGreaterThan(0);
    expect(data.persistence.error).toContain('OS memory down');
    // 规则仍是纯计算产物（可读），只是无 memory_id
    expect(data.rules.length).toBeGreaterThan(0);
    expect(data.rules[0].memory_id).toBeUndefined();
  });

  it('无蒸馏规则（无成功经验）时 persistence 为 undefined——不写空壳', async () => {
    const persistRules = vi.fn();
    const tool = new LearningDistillTool(
      async () => [],  // 空经验
      () => [],        // 无规则
      () => 'template',
      (rules: any[], _exp: any[]) => ({ total_rules: 0, avg_confidence: 0, coverage: 0 }),
      persistRules
    );
    const res = await tool.call({ source: 'failed_trades', target_format: 'rule' } as any, {});
    const data: any = res.data;
    expect(data.rules).toEqual([]);
    expect(data.persistence).toBeUndefined();
    expect(persistRules).not.toHaveBeenCalled();
  });
});
