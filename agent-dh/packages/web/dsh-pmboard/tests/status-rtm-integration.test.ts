import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { generateStatusRTM } from '../src/application/internal/status-rtm-integration.js';
import type { TaskRecord, VerificationSheet } from '../src/shared/protocol.js';

describe('Status RTM Integration', () => {
  let testDir: string;
  let reqDir: string;

  beforeEach(() => {
    // 创建临时测试目录
    testDir = mkdtempSync(join(tmpdir(), 'status-rtm-test-'));
    reqDir = join(testDir, 'REQ-TEST');
    const frDir = join(reqDir, 'functional-requirements');
    mkdirSync(frDir, { recursive: true });

    // 创建 3 个 FR 文件
    writeFileSync(join(frDir, 'FR-1-test.md'), `# FR-1: 测试功能1
**验收标准**:
- A1: 验收项1
- A2: 验收项2
`);

    writeFileSync(join(frDir, 'FR-2-test.md'), `# FR-2: 测试功能2
**验收标准**:
- A1: 验收项1
- A2: 验收项2
`);

    writeFileSync(join(frDir, 'FR-3-test.md'), `# FR-3: 测试功能3
**验收标准**:
- A1: 验收项1
- A2: 验收项2
`);
  });

  afterEach(() => {
    if (testDir) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('返回 fr_coverage（total_frs=3, covered_frs=2, unreceived_clauses=[FR-3], coverage_rate=67%）', () => {
    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '任务1',
        requirementRefs: ['FR-1', 'FR-2'],
        status: 'done',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    const result = generateStatusRTM(reqDir, tasks);

    // 验证 fr_coverage
    expect(result.fr_coverage.total_frs).toBe(3);
    expect(result.fr_coverage.covered_frs).toBe(2);
    expect(result.fr_coverage.unreceived_clauses).toEqual(['FR-3']);
    expect(result.fr_coverage.coverage_rate).toBe(67); // 2/3 ≈ 67%
    
    // 无验收单时不应该有 fr_acceptance_progress
    expect(result.fr_acceptance_progress).toBeUndefined();
  });

  it('返回 fr_acceptance_progress（total=12, passed=10, failed=2, pass_rate=83%, gate_status=blocked）', () => {
    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '任务1',
        requirementRefs: ['FR-1'],
        status: 'done',
        phase: 'implement',
        side: 'backend',
        dependsOn: [],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    // 创建验收单（12项：10 passed + 2 failed）
    const verificationSheet: VerificationSheet = {
      version: 1,
      items: [
        ...Array.from({ length: 10 }, (_, i) => ({
          id: `item-${i + 1}`,
          source: { kind: 'task' as const, taskId: 't-1' },
          criterion: `验收项${i + 1}`,
          howToVerify: `验证方式${i + 1}`,
          status: 'passed' as const,
          evidence: `已通过 ${i + 1}`,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: null
        })),
        {
          id: 'item-11',
          source: { kind: 'task' as const, taskId: 't-1' },
          criterion: '验收项11',
          howToVerify: '验证方式11',
          status: 'failed' as const,
          evidence: null,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: 'Need fix'
        },
        {
          id: 'item-12',
          source: { kind: 'task' as const, taskId: 't-1' },
          criterion: '验收项12',
          howToVerify: '验证方式12',
          status: 'failed' as const,
          evidence: null,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'test' },
          opinion: 'Need rework'
        }
      ],
      reworkOnly: false,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const result = generateStatusRTM(reqDir, tasks, verificationSheet);

    // 验证 fr_acceptance_progress
    expect(result.fr_acceptance_progress).toBeDefined();
    expect(result.fr_acceptance_progress!.total).toBe(12);
    expect(result.fr_acceptance_progress!.passed).toBe(10);
    expect(result.fr_acceptance_progress!.failed).toBe(2);
    expect(result.fr_acceptance_progress!.pending).toBe(0);
    expect(result.fr_acceptance_progress!.pass_rate).toBe(83); // 10/12 ≈ 83%
    expect(result.fr_acceptance_progress!.gate_status).toBe('blocked');
  });

  it('兼容性：无FR文件时返回空数据不报错', () => {
    // 删除所有 FR 文件
    rmSync(join(reqDir, 'functional-requirements'), { recursive: true, force: true });

    const tasks: TaskRecord[] = [];

    const result = generateStatusRTM(reqDir, tasks);

    // 无 FR 文件，应该返回空数据（0/0 = 100%）
    expect(result.fr_coverage.total_frs).toBe(0);
    expect(result.fr_coverage.covered_frs).toBe(0);
    expect(result.fr_coverage.coverage_rate).toBe(100); // 0/0 定义为 100%
    expect(result.fr_acceptance_progress).toBeUndefined();
  });
});
