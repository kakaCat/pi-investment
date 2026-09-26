import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { generateRTMData } from '../../../../web/dsh-pmboard/src/application/internal/rtm-integration.js';
import { generateAcceptanceTracking } from '../../../../web/dsh-pmboard/src/application/internal/submit-rtm-integration.js';
import { checkAcceptanceGate } from '../../../../web/dsh-pmboard/src/application/internal/accept-sheet-rtm-integration.js';
import { generateStatusRTM } from '../../../../web/dsh-pmboard/src/application/internal/status-rtm-integration.js';
import type { TaskRecord, VerificationSheet } from '../../../../web/dsh-pmboard/src/shared/protocol.js';

describe('RTM E2E - 完整流程', () => {
  let testDir: string;
  let reqDir: string;

  beforeEach(() => {
    // 创建临时测试目录
    testDir = mkdtempSync(join(tmpdir(), 'rtm-e2e-'));
    reqDir = join(testDir, 'REQ-TEST');
    const frDir = join(reqDir, 'functional-requirements');
    mkdirSync(frDir, { recursive: true });

    // 创建 3 个 FR 文件（每个 4 个验收项）
    writeFileSync(join(frDir, 'FR-1-feature.md'), `# FR-1: 核心功能

**验收标准**:
- A1: 能够扫描 FR 文件
- A2: 能够解析 FR 编号和标题
- A3: 能够提取验收标准
- A4: 能够识别 FR 依赖关系
`);

    writeFileSync(join(frDir, 'FR-2-coverage.md'), `# FR-2: 覆盖度追踪

**验收标准**:
- A1: 能够追踪任务覆盖 FR
- A2: 能够计算覆盖率
- A3: 能够识别未覆盖 FR
- A4: 能够生成覆盖度报告
`);

    writeFileSync(join(frDir, 'FR-3-acceptance.md'), `# FR-3: 验收门禁

**验收标准**:
- A1: 能够检查验收状态
- A2: 能够计算通过率
- A3: 能够判定门禁状态
- A4: 能够决定是否归档
`);
  });

  afterEach(() => {
    if (testDir) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('完整流程：拆分 → 提交 → 验收 → 归档', async () => {
    // ========== 阶段 1：拆分（decompose）==========
    const tasks: TaskRecord[] = [
      {
        id: 't-1',
        title: '实现 FR-1 和 FR-2',
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
      {
        id: 't-2',
        title: '实现 FR-3',
        requirementRefs: ['FR-3'],
        status: 'done',
        phase: 'implement',
        side: 'backend',
        dependsOn: ['t-1'],
        createdAt: Date.now(),
        createdBy: { kind: 'agent', sessionId: 'test' },
        updatedAt: Date.now(),
        updatedBy: { kind: 'agent', sessionId: 'test' },
      } as TaskRecord,
    ];

    const decomposeResult = await generateRTMData(reqDir, tasks);

    // 验证拆分阶段：全部覆盖
    expect(decomposeResult.coverage_check.total_frs).toBe(3);
    expect(decomposeResult.coverage_check.covered_frs).toBe(3);
    expect(decomposeResult.coverage_check.unreceived_clauses).toEqual([]);
    expect(decomposeResult.coverage_check.coverage_rate).toBe(100);

    expect(decomposeResult.task_coverage).toHaveLength(2);
    expect(decomposeResult.task_coverage[0].covers_frs).toEqual(['FR-1', 'FR-2']);
    expect(decomposeResult.task_coverage[1].covers_frs).toEqual(['FR-3']);

    // ========== 阶段 2：提交验收（submit）==========
    const submitResult = generateAcceptanceTracking(reqDir);

    // 验证提交阶段：生成 12 个验收项（3个FR × 4个验收标准）
    expect(submitResult.acceptance_tracking_count).toBe(12);
    expect(submitResult.acceptance_tracking).toHaveLength(12);
    expect(submitResult.is_rework).toBe(false);

    // 所有项初始状态为 pending
    for (const item of submitResult.acceptance_tracking) {
      expect(item.status).toBe('pending');
    }

    // ========== 阶段 3a：第一次验收（部分通过）==========
    // 模拟验收单：10 passed + 2 failed
    const sheet1: VerificationSheet = {
      version: 1,
      items: [
        ...submitResult.acceptance_tracking.slice(0, 10).map((item, i) => ({
          id: item.acceptance_id,
          source: { kind: 'task' as const, taskId: 't-1' },
          criterion: item.description,
          howToVerify: item.verification,
          status: 'passed' as const,
          evidence: `通过证据 ${i + 1}`,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'tester' },
          opinion: null
        })),
        ...submitResult.acceptance_tracking.slice(10, 12).map(item => ({
          id: item.acceptance_id,
          source: { kind: 'task' as const, taskId: 't-2' },
          criterion: item.description,
          howToVerify: item.verification,
          status: 'failed' as const,
          evidence: null,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'tester' },
          opinion: 'Need rework'
        }))
      ],
      reworkOnly: false,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const acceptResult1 = checkAcceptanceGate(sheet1);

    // 验证第一次验收：部分通过，门禁阻塞
    expect(acceptResult1.gate_check.total).toBe(12);
    expect(acceptResult1.gate_check.passed).toBe(10);
    expect(acceptResult1.gate_check.failed).toBe(2);
    expect(acceptResult1.gate_check.pending).toBe(0);
    expect(acceptResult1.gate_check.pass_rate).toBe(83); // 10/12
    expect(acceptResult1.gate_check.gate_status).toBe('blocked');
    expect(acceptResult1.should_archive).toBe(false);

    // ========== 阶段 3b：返工后第二次验收（全部通过）==========
    // 模拟续验：只重新验收之前 failed 的 2 项
    const reworkTracking = submitResult.acceptance_tracking.slice(10, 12).map(item => ({
      ...item,
      status: 'failed' as const,
      judged_at: Date.now(),
      judged_by: 'tester',
      user_feedback: 'Need rework'
    }));

    const submitReworkResult = generateAcceptanceTracking(reqDir, reworkTracking);

    // 验证续验：只生成 2 项
    expect(submitReworkResult.acceptance_tracking_count).toBe(2);
    expect(submitReworkResult.is_rework).toBe(true);

    // 模拟全部通过的验收单
    const sheet2: VerificationSheet = {
      version: 2,
      items: [
        ...sheet1.items.slice(0, 10), // 保留之前 passed 的 10 项
        ...submitReworkResult.acceptance_tracking.map((item, i) => ({
          id: item.acceptance_id,
          source: { kind: 'task' as const, taskId: 't-2' },
          criterion: item.description,
          howToVerify: item.verification,
          status: 'passed' as const,
          evidence: `返工后通过 ${i + 1}`,
          decidedAt: Date.now(),
          decidedBy: { kind: 'human' as const, sessionId: 'tester' },
          opinion: null
        }))
      ],
      reworkOnly: true,
      generatedAt: Date.now(),
      generatedBy: { kind: 'agent' as const, sessionId: 'test' }
    };

    const acceptResult2 = checkAcceptanceGate(sheet2);

    // 验证第二次验收：全部通过，门禁打开，应该归档
    expect(acceptResult2.gate_check.total).toBe(12);
    expect(acceptResult2.gate_check.passed).toBe(12);
    expect(acceptResult2.gate_check.failed).toBe(0);
    expect(acceptResult2.gate_check.pending).toBe(0);
    expect(acceptResult2.gate_check.pass_rate).toBe(100);
    expect(acceptResult2.gate_check.gate_status).toBe('passed');
    expect(acceptResult2.should_archive).toBe(true);

    // ========== 阶段 4：状态查询（status）==========
    const statusResult = generateStatusRTM(reqDir, tasks, sheet2);

    // 验证状态查询：覆盖度 100%
    expect(statusResult.fr_coverage.total_frs).toBe(3);
    expect(statusResult.fr_coverage.covered_frs).toBe(3);
    expect(statusResult.fr_coverage.coverage_rate).toBe(100);

    // 验证状态查询：验收进度 100%
    expect(statusResult.fr_acceptance_progress).toBeDefined();
    expect(statusResult.fr_acceptance_progress!.total).toBe(12);
    expect(statusResult.fr_acceptance_progress!.passed).toBe(12);
    expect(statusResult.fr_acceptance_progress!.gate_status).toBe('passed');

    // ========== 流程验证完成 ==========
    console.log('✅ RTM 完整流程测试通过！');
    console.log('  拆分阶段：3个FR 全部覆盖');
    console.log('  提交阶段：生成 12 个验收项');
    console.log('  第一次验收：10/12 通过，门禁阻塞');
    console.log('  返工续验：2 项重新验收');
    console.log('  第二次验收：12/12 通过，门禁打开，自动归档');
    console.log('  状态查询：覆盖度 100%，验收进度 100%');
  });
});
