import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { generateRTMData } from '../src/application/internal/rtm-integration.js';
import type { TaskRecord } from '../src/shared/protocol.js';

describe('Decompose RTM Integration', () => {
  let testDir: string;
  let reqDir: string;

  beforeEach(() => {
    // 创建临时测试目录
    testDir = mkdtempSync(join(tmpdir(), 'decompose-rtm-test-'));
    reqDir = join(testDir, 'REQ-TEST');
    const frDir = join(reqDir, 'functional-requirements');
    mkdirSync(frDir, { recursive: true });

    // 创建测试 FR 文件
    writeFileSync(join(frDir, 'FR-1-test-feature.md'), `# FR-1: 测试功能1

**验收标准**:
- A1: 验收项1
- A2: 验收项2
`);

    writeFileSync(join(frDir, 'FR-2-test-feature.md'), `# FR-2: 测试功能2

**验收标准**:
- A1: 验收项1
- A2: 验收项2
`);

    writeFileSync(join(frDir, 'FR-3-test-feature.md'), `# FR-3: 测试功能3

**验收标准**:
- A1: 验收项1
`);
  });

  afterEach(() => {
    // 清理测试目录
    if (testDir) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('完全覆盖：2个任务覆盖3个FR，返回coverage_rate=100%', async () => {
    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '任务1',
        requirementRefs: ['FR-1', 'FR-2'],
        status: 'todo',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
      {
        id: 't-2',
        title: '任务2',
        requirementRefs: ['FR-3'],
        status: 'todo',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    const result = await generateRTMData(reqDir, tasks);

    // 验证 task_coverage
    expect(result.task_coverage).toHaveLength(2);
    expect(result.task_coverage[0].covers_frs).toEqual(['FR-1', 'FR-2']);
    expect(result.task_coverage[0].covers_acceptance).toContain('FR-1-A1');
    expect(result.task_coverage[0].covers_acceptance).toContain('FR-2-A1');
    expect(result.task_coverage[1].covers_frs).toEqual(['FR-3']);

    // 验证 coverage_check
    expect(result.coverage_check.total_frs).toBe(3);
    expect(result.coverage_check.covered_frs).toBe(3);
    expect(result.coverage_check.coverage_rate).toBe(100);
    expect(result.coverage_check.unreceived_clauses).toEqual([]);
  });

  it('部分覆盖：2个任务只覆盖2个FR，返回coverage_rate=67%', async () => {
    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '任务1',
        requirementRefs: ['FR-1'],
        status: 'todo',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
      {
        id: 't-2',
        title: '任务2',
        requirementRefs: ['FR-2'],
        status: 'todo',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    const result = await generateRTMData(reqDir, tasks);

    // 验证 coverage_check
    expect(result.coverage_check.total_frs).toBe(3);
    expect(result.coverage_check.covered_frs).toBe(2);
    expect(result.coverage_check.coverage_rate).toBe(67); // 2/3 ≈ 67%
    expect(result.coverage_check.unreceived_clauses).toEqual(['FR-3']);
  });

  it('兼容性：无FR文件时返回空数据不报错', async () => {
    // 删除所有 FR 文件
    rmSync(join(reqDir, 'functional-requirements'), { recursive: true, force: true });

    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '任务1',
        requirementRefs: [],
        status: 'todo',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    const result = await generateRTMData(reqDir, tasks);

    // 无 FR 文件，应该返回空数据（0/0 = 100%）
    expect(result.task_coverage).toHaveLength(1);
    expect(result.coverage_check.total_frs).toBe(0);
    expect(result.coverage_check.coverage_rate).toBe(100); // 0/0 定义为 100%
  });
});
