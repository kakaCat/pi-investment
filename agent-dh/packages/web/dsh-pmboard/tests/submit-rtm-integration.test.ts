import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { generateAcceptanceTracking } from '../src/application/internal/submit-rtm-integration.js';
import type { AcceptanceTracking } from '../../../../tools/reqboard/src/types/rtm.js';

describe('Submit RTM Integration', () => {
  let testDir: string;
  let reqDir: string;

  beforeEach(() => {
    // 创建临时测试目录
    testDir = mkdtempSync(join(tmpdir(), 'submit-rtm-test-'));
    reqDir = join(testDir, 'REQ-TEST');
    const frDir = join(reqDir, 'functional-requirements');
    mkdirSync(frDir, { recursive: true });

    // 创建测试 FR 文件（共12个验收项）
    writeFileSync(join(frDir, 'FR-1-test.md'), `# FR-1: 测试功能1

**验收标准**:
- A1: 验收项1-1
- A2: 验收项1-2
- A3: 验收项1-3
- A4: 验收项1-4
`);

    writeFileSync(join(frDir, 'FR-2-test.md'), `# FR-2: 测试功能2

**验收标准**:
- A1: 验收项2-1
- A2: 验收项2-2
- A3: 验收项2-3
- A4: 验收项2-4
`);

    writeFileSync(join(frDir, 'FR-3-test.md'), `# FR-3: 测试功能3

**验收标准**:
- A1: 验收项3-1
- A2: 验收项3-2
- A3: 验收项3-3
- A4: 验收项3-4
`);
  });

  afterEach(() => {
    // 清理测试目录
    if (testDir) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('提交验收：3个FR（12个验收项），返回acceptance_tracking_count=12', () => {
    const result = generateAcceptanceTracking(reqDir);

    // 验证返回值
    expect(result.acceptance_tracking_count).toBe(12);
    expect(result.acceptance_tracking).toHaveLength(12);
    expect(result.is_rework).toBe(false);

    // 验证所有项的初始状态为 pending
    for (const item of result.acceptance_tracking) {
      expect(item.status).toBe('pending');
      expect(item.evidence).toBeNull();
      expect(item.judged_at).toBeNull();
      expect(item.judged_by).toBeNull();
    }

    // 验证包含所有 FR 的验收项
    const frIds = new Set(result.acceptance_tracking.map(t => t.fr_id));
    expect(frIds.size).toBe(3);
    expect(frIds.has('FR-1')).toBe(true);
    expect(frIds.has('FR-2')).toBe(true);
    expect(frIds.has('FR-3')).toBe(true);
  });

  it('续验：上版2项failed，本次只生成这2项（不重复生成passed项）', () => {
    // 模拟上一版的验收追踪（10项passed，2项failed）
    const prevTracking: AcceptanceTracking[] = [];
    
    // 10项 passed
    for (let i = 1; i <= 10; i++) {
      const frId = `FR-${Math.ceil(i / 4)}`;
      const aId = `${frId}-A${((i - 1) % 4) + 1}`;
      prevTracking.push({
        acceptance_id: aId,
        fr_id: frId,
        description: `验收项${i}`,
        verification: '验证方式',
        status: 'passed',
        evidence: `已通过 ${i}`,
        judged_at: Date.now(),
        judged_by: 'test-user',
        user_feedback: null
      });
    }
    
    // 2项 failed
    prevTracking.push({
      acceptance_id: 'FR-3-A3',
      fr_id: 'FR-3',
      description: '验收项11',
      verification: '验证方式',
      status: 'failed',
      evidence: null,
      judged_at: Date.now(),
      judged_by: 'test-user',
      user_feedback: 'Need rework'
    });
    
    prevTracking.push({
      acceptance_id: 'FR-3-A4',
      fr_id: 'FR-3',
      description: '验收项12',
      verification: '验证方式',
      status: 'failed',
      evidence: null,
      judged_at: Date.now(),
      judged_by: 'test-user',
      user_feedback: 'Fix required'
    });

    const result = generateAcceptanceTracking(reqDir, prevTracking);

    // 验证只生成了2项（上版的failed项）
    expect(result.acceptance_tracking_count).toBe(2);
    expect(result.acceptance_tracking).toHaveLength(2);
    expect(result.is_rework).toBe(true);

    // 验证生成的项是上版failed的项
    expect(result.acceptance_tracking[0].acceptance_id).toBe('FR-3-A3');
    expect(result.acceptance_tracking[1].acceptance_id).toBe('FR-3-A4');

    // 验证状态重置为 pending
    for (const item of result.acceptance_tracking) {
      expect(item.status).toBe('pending');
      expect(item.evidence).toBeNull();
      expect(item.judged_at).toBeNull();
      expect(item.judged_by).toBeNull();
    }

    // 验证保留了 user_feedback（返工原因）
    expect(result.acceptance_tracking[0].user_feedback).toBe('Need rework');
    expect(result.acceptance_tracking[1].user_feedback).toBe('Fix required');
  });

  it('兼容性：无FR文件时返回空数据不报错', () => {
    // 删除所有 FR 文件
    rmSync(join(reqDir, 'functional-requirements'), { recursive: true, force: true });

    const result = generateAcceptanceTracking(reqDir);

    // 无 FR 文件，应该返回空数据
    expect(result.acceptance_tracking_count).toBe(0);
    expect(result.acceptance_tracking).toHaveLength(0);
    expect(result.is_rework).toBe(false);
  });
});
