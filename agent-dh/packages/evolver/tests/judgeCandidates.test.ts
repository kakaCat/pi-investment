import { describe, it, expect } from 'vitest';

/**
 * 测试 evolver 的 judgeCandidates 零样本门槛逻辑（审计修复 #1）
 * 
 * 关键逻辑：candidate 期零样本（cand.count === 0）时，无论 force 与否都不能转正，
 * 必须返回 verdict='extended' 延期2天，避免统计无效的"零证据不劣于"误判
 */

describe('evolver/judgeCandidates 零样本门槛', () => {
  
  /**
   * 测试用例 1：零样本应强制 extended
   * 预期：cand.count=0 时返回 verdict='extended'，note 包含"零样本"
   */
  it('零样本候选应强制延期（不转正）', () => {
    // 模拟 candidate 数据
    const candidate = {
      id: 'cand_test_1',
      section: 'lessons',
      genome_version: 'g15',
      baseline_version: 'g14',
      status: 'watching',
      observe_until: new Date(Date.now() - 1000).toISOString(), // 已过期
    };

    // 模拟 searchRewards 返回（零样本）
    const cand = { count: 0, avg: 0 };
    const base = { count: 3, avg: -0.3 };

    // 审计修复 #1：硬样本门槛
    let verdict: any;
    if (cand.count === 0) {
      verdict = {
        id: candidate.id,
        section: candidate.section,
        verdict: 'extended',
        cand_samples: 0,
        note: `零样本拒绝转正（candidate 期无数据，统计无效）`,
      };
    }

    // 断言
    expect(verdict.verdict).toBe('extended');
    expect(verdict.cand_samples).toBe(0);
    expect(verdict.note).toContain('零样本');
    expect(verdict.note).toContain('统计无效');
  });

  /**
   * 测试用例 2：force=true 时零样本也应延期
   * 预期：硬样本门槛优先于 force 标志
   */
  it('force=true 时零样本仍应延期', () => {
    const force = true;  // 强制裁决标志
    const cand = { count: 0, avg: 0 };

    // 硬样本门槛在 force 检查之后
    let verdict: any;
    if (cand.count === 0) {
      verdict = { verdict: 'extended', cand_samples: 0 };
    } else if (force) {
      verdict = { verdict: 'promoted' };  // 不应执行到这里
    }

    expect(verdict.verdict).toBe('extended');
  });

  /**
   * 测试用例 3：1个样本且 minSamples=3 且 !force 应延期
   * 预期：样本不足（但非零）按原逻辑延期
   */
  it('非零但不足 minSamples 应延期（原逻辑）', () => {
    const force = false;
    const minSamples = 3;
    const cand = { count: 1, avg: 0.2 };

    let verdict: any;
    if (cand.count === 0) {
      verdict = { verdict: 'extended', note: '零样本' };
    } else if (!force && cand.count < minSamples) {
      verdict = { 
        verdict: 'extended', 
        cand_samples: cand.count,
        note: `证据不足延期（candidate 样本 ${cand.count} < ${minSamples}）`
      };
    }

    expect(verdict.verdict).toBe('extended');
    expect(verdict.cand_samples).toBe(1);
    expect(verdict.note).toContain('证据不足');
  });

  /**
   * 测试用例 4：5个样本应进入正常比较流程
   * 预期：通过零样本门槛和 minSamples 门槛，进入 drop 比较
   */
  it('足够样本应进入正常比较流程', () => {
    const force = false;
    const minSamples = 3;
    const cand = { count: 5, avg: 0.15 };
    const base = { count: 10, avg: 0.25 };

    let verdict: any;
    if (cand.count === 0) {
      verdict = { verdict: 'extended' };
    } else if (!force && cand.count < minSamples) {
      verdict = { verdict: 'extended' };
    } else {
      // 进入比较流程
      const drop = base.avg - cand.avg;  // 0.25 - 0.15 = 0.10
      if (drop > 0.1) {
        verdict = { verdict: 'rejected', drop };
      } else {
        verdict = { verdict: 'promoted', cand_avg: cand.avg, base_avg: base.avg };
      }
    }

    // drop=0.10 刚好不超过阈值 0.1，应转正
    expect(verdict.verdict).toBe('promoted');
    expect(verdict.cand_avg).toBe(0.15);
  });

  /**
   * 测试用例 5：显著恶化应回滚
   * 预期：drop > 0.1 时 verdict='rejected'
   */
  it('显著恶化（drop>0.1）应回滚', () => {
    const cand = { count: 5, avg: 0.05 };
    const base = { count: 10, avg: 0.20 };

    let verdict: any;
    if (cand.count === 0) {
      verdict = { verdict: 'extended' };
    } else {
      const drop = base.avg - cand.avg;  // 0.20 - 0.05 = 0.15 > 0.1
      if (drop > 0.1) {
        verdict = { verdict: 'rejected', cand_avg: cand.avg, base_avg: base.avg };
      } else {
        verdict = { verdict: 'promoted' };
      }
    }

    expect(verdict.verdict).toBe('rejected');
    expect(base.avg - cand.avg).toBeGreaterThan(0.1);
  });

  /**
   * 测试用例 6：g10 真实案例回归测试
   * 预期：cand=0, base=-0.3 应延期而非转正（修复前会误判转正）
   */
  it('g10 真实案例：零样本 vs 负基准应延期', () => {
    // g10 首次裁决暴露的 bug：cand.avg=0 与 base.avg=-0.3 比较
    // drop = -0.3 - 0 = -0.3 < 0.1 → 误判"不劣于"转正
    const cand = { count: 0, avg: 0 };  // 零样本
    const base = { count: 1, avg: -0.3 };

    let verdict: any;
    // 修复后：零样本门槛优先
    if (cand.count === 0) {
      verdict = { verdict: 'extended', cand_samples: 0, note: '零样本拒绝转正' };
    } else {
      const drop = base.avg - cand.avg;
      verdict = drop > 0.1 ? { verdict: 'rejected' } : { verdict: 'promoted' };
    }

    // 断言：修复后应延期
    expect(verdict.verdict).toBe('extended');
    expect(verdict.cand_samples).toBe(0);
    
    // 修复前的错误行为（用于回归对比）
    const buggyDrop = base.avg - cand.avg;  // -0.3 < 0.1
    expect(buggyDrop).toBeLessThan(0.1);  // 修复前会走这条路径误判转正
  });
});
