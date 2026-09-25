# 测试策略

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## 测试目标 «serves: FR-10»

### 行为等价验证 «serves: FR-10»

1. **手动模式保持不变**：老需求的所有操作行为与重构前完全一致
2. **自动流程端到端**：dive 模式下从立项到归档全流程自动化
3. **门禁有效性**：RTM 门禁正确阻塞不完整的推进
4. **armed 锁有效性**：dive 模式下禁止手动绕过
5. **错误恢复**：暂停/阻塞/解锁机制正常工作

### 测试覆盖率目标 «serves: FR-10»

- 单元测试覆盖率 > 80%
- 集成测试覆盖核心流程
- E2E 测试覆盖完整场景

## 单元测试 «serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7»

### 测试文件结构 «serves: FR-10»

```
packages/web/dsh-pmboard/tests/
├── unit/
│   ├── dive/
│   │   ├── ReqboardDiveManager.test.ts
│   │   └── stage-configs.test.ts
│   ├── gate/
│   │   ├── design-gate.test.ts
│   │   ├── task-coverage-gate.test.ts
│   │   └── acceptance-gate.test.ts
│   └── use-cases/
│       ├── Decompose.armed-check.test.ts
│       ├── MoveRequirement.armed-check.test.ts
│       └── MoveTask.armed-check.test.ts
└── integration/
    └── dive-flow.test.ts
```

### ReqboardDiveManager 测试 «serves: FR-2»

```typescript
describe('ReqboardDiveManager', () => {
  describe('checkAndContinue', () => {
    it('应该为 armed + active 的需求发起 followup', async () => {
      // Arrange
      const req = createRequirement({
        dive: {
          activation: 'armed',
          phase: 'active',
          currentStage: 'implementing',
          roundsInStage: 2,
          maxRoundsPerStage: 50
        }
      });
      
      const agent = createMockAgent();
      
      // Act
      await manager.checkAndContinue(agent.id);
      
      // Assert
      expect(agent.followup).toHaveBeenCalledWith(
        expect.stringContaining('继续执行 implementing 阶段任务')
      );
      expect(req.dive.roundsInStage).toBe(3);
    });
    
    it('应该在达到最大回合数时阻塞需求', async () => {
      // Arrange
      const req = createRequirement({
        dive: {
          activation: 'armed',
          phase: 'active',
          currentStage: 'implementing',
          roundsInStage: 50,
          maxRoundsPerStage: 50
        }
      });
      
      // Act
      await manager.checkAndContinue(agentId);
      
      // Assert
      expect(req.dive.phase).toBe('blocked');
      expect(req.dive.blockedReason).toBe('max_rounds_exceeded');
    });
    
    it('应该跳过 disarmed 的需求', async () => {
      // Arrange
      const req = createRequirement({
        dive: {
          activation: 'disarmed',
          phase: 'active'
        }
      });
      
      // Act
      await manager.checkAndContinue(agentId);
      
      // Assert
      expect(agent.followup).not.toHaveBeenCalled();
    });
  });
});
```

### 门禁测试 «serves: FR-4, FR-5, FR-6»

```typescript
describe('designGateCheck', () => {
  it('应该通过所有 FR 都有 design_refs 的检查', async () => {
    // Arrange
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', design_refs: ['architecture.md#section-1'] },
        { id: 'FR-2', design_refs: ['data-model.md#section-2'] }
      ]
    };
    
    // Act
    const result = await designGateCheck(req);
    
    // Assert
    expect(result.passed).toBe(true);
  });
  
  it('应该拒绝有 FR 未覆盖的情况', async () => {
    // Arrange
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', design_refs: ['architecture.md#section-1'] },
        { id: 'FR-2', design_refs: [] }  // 未覆盖
      ]
    };
    
    // Act
    const result = await designGateCheck(req);
    
    // Assert
    expect(result.passed).toBe(false);
    expect(result.code).toBe('design_incomplete');
    expect(result.gaps).toEqual(['FR-2']);
  });
});

describe('taskCoverageGateCheck', () => {
  it('应该通过所有 FR 都有 task_refs 的检查', async () => {
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', task_refs: ['t-001'] },
        { id: 'FR-2', task_refs: ['t-002', 't-003'] }
      ]
    };
    
    const result = await taskCoverageGateCheck(req);
    
    expect(result.passed).toBe(true);
  });
  
  it('应该拒绝有 FR 未接收的情况', async () => {
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', task_refs: ['t-001'] },
        { id: 'FR-2', task_refs: [] }  // 未接收
      ]
    };
    
    const result = await taskCoverageGateCheck(req);
    
    expect(result.passed).toBe(false);
    expect(result.orphan_clauses).toEqual(['FR-2']);
  });
});

describe('acceptanceGateCheck', () => {
  it('应该通过所有 FR 都验收通过的检查', async () => {
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', acceptance_status: 'passed' },
        { id: 'FR-2', acceptance_status: 'passed' }
      ]
    };
    
    const result = await acceptanceGateCheck(req);
    
    expect(result.passed).toBe(true);
  });
  
  it('应该拒绝有 FR 验收未通过的情况', async () => {
    const rtm = {
      functional_requirements: [
        { id: 'FR-1', acceptance_status: 'passed' },
        { id: 'FR-2', acceptance_status: 'failed' }
      ]
    };
    
    const result = await acceptanceGateCheck(req);
    
    expect(result.passed).toBe(false);
    expect(result.failed_clauses).toEqual([
      { id: 'FR-2', status: 'failed' }
    ]);
  });
});
```

### armed 锁测试 «serves: FR-7»

```typescript
describe('reqboard_decompose armed check', () => {
  it('应该拒绝 armed 时的手动拆分', async () => {
    // Arrange
    const req = createRequirement({
      dive: { activation: 'armed' }
    });
    
    // Act & Assert
    await expect(
      reqboard_decompose({ requirement_id: req.id })
    ).rejects.toThrow('REQBOARD_DIVE_ARMED');
  });
  
  it('应该允许 disarmed 时的手动拆分', async () => {
    const req = createRequirement({
      dive: { activation: 'disarmed' }
    });
    
    await expect(
      reqboard_decompose({ requirement_id: req.id })
    ).resolves.not.toThrow();
  });
  
  it('应该允许没有 dive 字段的老需求手动拆分', async () => {
    const req = createRequirement({
      dive: undefined
    });
    
    await expect(
      reqboard_decompose({ requirement_id: req.id })
    ).resolves.not.toThrow();
  });
});

describe('reqboard_move armed check', () => {
  it('应该拒绝 armed 时手动推进到 implementing', async () => {
    const req = createRequirement({
      dive: { activation: 'armed' }
    });
    
    await expect(
      reqboard_move({ to: 'implementing', requirement_id: req.id })
    ).rejects.toThrow('REQBOARD_DIVE_ARMED');
  });
  
  it('应该允许 armed 时推进到其他阶段', async () => {
    const req = createRequirement({
      dive: { activation: 'armed' }
    });
    
    await expect(
      reqboard_move({ to: 'design', requirement_id: req.id })
    ).resolves.not.toThrow();
  });
});

describe('reqboard_task_move armed check', () => {
  it('应该拒绝 armed 时手动推进子任务', async () => {
    const req = createRequirement({
      dive: { activation: 'armed' }
    });
    
    const task = createTask({
      requirementId: req.id,
      parentId: 't-parent'
    });
    
    await expect(
      reqboard_task_move({ task_id: task.id, to: 'done' })
    ).rejects.toThrow('REQBOARD_DIVE_ARMED');
  });
  
  it('应该允许 armed 时推进父任务', async () => {
    const task = createTask({
      parentId: null
    });
    
    await expect(
      reqboard_task_move({ task_id: task.id, to: 'done' })
    ).resolves.not.toThrow();
  });
});
```

## 集成测试 «serves: FR-3»

### confirm-settle.ts 集成测试 «serves: FR-3»

```typescript
describe('confirm-settle integration', () => {
  it('批准拆分计划应该启动后台 job 并设置 autoRun', async () => {
    // Arrange
    const req = createRequirement({ status: 'decomposing' });
    const plan = createPlan({ requirement_id: req.id });
    
    // Act
    await confirmPlanApproval(req, plan);
    
    // Assert
    expect(deps.jobs.start).toHaveBeenCalledWith({
      type: 'reqboard-decompose',
      payload: {
        requirement_id: req.id,
        tasks: plan.tasks
      }
    });
    
    const updatedReq = await getRequirement(req.id);
    expect(updatedReq.advance.autoRun).toBe(true);
    expect(updatedReq.dive.activation).toBe('armed');
  });
  
  it('后台 job 应该成功拆分并创建任务', async () => {
    // Arrange
    const req = createRequirement();
    const tasks = [
      { key: 't1', title: 'Task 1' },
      { key: 't2', title: 'Task 2', depends_on: ['t1'] }
    ];
    
    // Act
    const job = await deps.jobs.start({
      type: 'reqboard-decompose',
      payload: { requirement_id: req.id, tasks }
    });
    
    await waitForJobCompletion(job.id);
    
    // Assert
    const createdTasks = await getTasks(req.id);
    expect(createdTasks).toHaveLength(2);
    expect(createdTasks[0].title).toBe('Task 1');
    expect(createdTasks[1].depends_on).toEqual([createdTasks[0].id]);
  });
});
```

## E2E 测试 «serves: FR-10»

### 完整流程测试 «serves: FR-10»

```typescript
describe('Dive E2E', () => {
  it('应该完成从立项到归档的全流程', async () => {
    // 1. 创建需求（启用 dive）
    const req = await reqboard_create({
      title: 'E2E Test Requirement',
      category: 'feature',
      enableDive: true
    });
    
    expect(req.dive.activation).toBe('armed');
    expect(req.dive.phase).toBe('active');
    
    // 2. brainstorming 阶段
    // agent 自动写需求文档
    await waitForStage(req.id, 'brainstorming');
    await waitForFile(`docs/requirements/${req.id}/requirement.md`);
    
    // 用户确认需求文档
    await confirmArtifact(req.id, 'requirement');
    
    // 应该自动推进到 design
    await waitForStage(req.id, 'design');
    
    // 3. design 阶段
    // agent 自动写设计文档
    await waitForFiles(`docs/requirements/${req.id}/design/*.md`);
    
    // 用户确认设计文档
    await confirmArtifact(req.id, 'design');
    
    // 应该自动推进到 decomposing
    await waitForStage(req.id, 'decomposing');
    
    // 4. decomposing 阶段
    // agent 自动写拆分计划
    await waitForFile(`docs/requirements/${req.id}/decomposition.md`);
    
    // 用户批准拆分计划
    await confirmPlan(req.id);
    
    // 应该自动拆分并推进到 implementing
    await waitForStage(req.id, 'implementing');
    const tasks = await getTasks(req.id);
    expect(tasks.length).toBeGreaterThan(0);
    
    // 5. implementing 阶段
    // agent 自动执行所有任务
    await waitForAllTasksDone(req.id);
    
    // 应该自动推进到 accepting
    await waitForStage(req.id, 'accepting');
    
    // 6. accepting 阶段
    // agent 提交验收材料
    await waitForArtifact(req.id, 'verification');
    
    // 用户验收通过
    await acceptRequirement(req.id);
    
    // 应该推进到 archived
    await waitForStage(req.id, 'archived');
    
    // 7. 验证全流程数据
    const finalReq = await getRequirement(req.id);
    expect(finalReq.dive.phase).toBe('complete');
    expect(finalReq.dive.stagesCompleted).toEqual([
      'brainstorming',
      'design',
      'decomposing',
      'implementing',
      'accepting'
    ]);
  });
  
  it('应该在 RTM 门禁失败时阻塞推进', async () => {
    // Arrange
    const req = await createRequirement({ enableDive: true });
    
    // 创建不完整的设计（遗漏 FR-2）
    await createDesignDocs(req.id, {
      'architecture.md': 'serves: FR-1'
      // FR-2 未覆盖
    });
    
    await confirmArtifact(req.id, 'design');
    
    // Act & Assert
    // 尝试推进到 decomposing 应该失败
    await expect(
      reqboard_move({ to: 'decomposing', requirement_id: req.id })
    ).rejects.toThrow('design_incomplete');
    
    // 需求应该停留在 design
    const updatedReq = await getRequirement(req.id);
    expect(updatedReq.status).toBe('design');
  });
  
  it('应该在 armed 时阻塞手动工具', async () => {
    const req = await createRequirement({ 
      status: 'decomposing',
      dive: { activation: 'armed' }
    });
    
    // 尝试手动拆分应该失败
    await expect(
      reqboard_decompose({ requirement_id: req.id })
    ).rejects.toThrow('REQBOARD_DIVE_ARMED');
    
    // 清除 armed 锁后应该成功
    await reqboard_clear_pause({ requirement_id: req.id });
    await expect(
      reqboard_decompose({ requirement_id: req.id })
    ).resolves.not.toThrow();
  });
});
```

## 性能测试 «serves: FR-10»

### 性能指标 «serves: FR-10»

```typescript
describe('Performance', () => {
  it('Dive 续跑检查应该在 1 秒内完成', async () => {
    const start = Date.now();
    await manager.checkAndContinue(agentId);
    const elapsed = Date.now() - start;
    
    expect(elapsed).toBeLessThan(1000);
  });
  
  it('RTM 门禁检查应该在 2 秒内完成', async () => {
    const start = Date.now();
    await designGateCheck(req);
    const elapsed = Date.now() - start;
    
    expect(elapsed).toBeLessThan(2000);
  });
  
  it('不应该影响老需求的性能', async () => {
    // 老需求（无 dive）
    const oldReq = createRequirement({ dive: undefined });
    
    const start = Date.now();
    await reqboard_decompose({ requirement_id: oldReq.id });
    const elapsed = Date.now() - start;
    
    // 应该与重构前性能相当（设基准为 500ms）
    expect(elapsed).toBeLessThan(500);
  });
});
```

## 测试数据准备 «serves: FR-10»

### Mock 工厂 «serves: FR-10»

```typescript
function createRequirement(overrides?: Partial<Requirement>): Requirement {
  return {
    id: `REQ-${Date.now()}`,
    title: 'Test Requirement',
    category: 'feature',
    status: 'brainstorming',
    dive: undefined,
    ...overrides
  };
}

function createMockAgent(): MockAgent {
  return {
    id: 'agent-test',
    followup: jest.fn().mockResolvedValue(undefined)
  };
}

function createRTM(frs: Array<{
  id: string;
  design_refs?: string[];
  task_refs?: string[];
  acceptance_status?: string;
}>): RTM {
  return {
    functional_requirements: frs.map(fr => ({
      id: fr.id,
      design_refs: fr.design_refs || [],
      task_refs: fr.task_refs || [],
      acceptance_status: fr.acceptance_status || 'pending'
    }))
  };
}
```

## 验收标准 «serves: FR-10»

### 测试通过标准 «serves: FR-10»

- [ ] 所有单元测试通过（>80% 覆盖率）
- [ ] 所有集成测试通过
- [ ] E2E 测试通过（完整流程）
- [ ] 性能测试通过（Dive < 1s, 门禁 < 2s）
- [ ] 老需求回归测试通过（行为不变）

### 验证命令 «serves: FR-10»

```bash
# 运行所有测试
pnpm test

# 运行单元测试
pnpm test:unit

# 运行集成测试
pnpm test:integration

# 运行 E2E 测试
pnpm test:e2e

# 测试覆盖率报告
pnpm test:coverage

# 性能测试
pnpm test:perf
```

### 预期输出 «serves: FR-10»

```
✓ ReqboardDiveManager (5/5)
✓ Gate checks (9/9)
✓ Armed lock (12/12)
✓ confirm-settle integration (2/2)
✓ E2E full flow (3/3)
✓ Performance (3/3)

Tests:       34 passed, 34 total
Coverage:    85.3% statements
             82.1% branches
             88.7% functions
             84.9% lines
```