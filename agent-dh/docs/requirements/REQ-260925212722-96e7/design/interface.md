# 接口设计

> REQ-260925212722-96e7: REQ 流水线 Dive 模式重构

## 工具接口变更 «serves: FR-7, FR-9»

### reqboard_decompose «serves: FR-7»

**变更**: 增加 armed 锁检查

**签名**: 不变

```typescript
interface ReqboardDecomposeArgs {
  requirement_id?: string;
  tasks?: Task[];
}
```

**新增行为**:
```typescript
// 检查 armed 锁
if (req.dive?.activation === 'armed') {
  throw new Error(
    'dive 自动流程已启用，不允许手动拆分。' +
    '请等待自动流程完成，或调用 reqboard_clear_pause() 解除锁定。' +
    '错误码: REQBOARD_DIVE_ARMED'
  );
}

// 检查暂停状态
if (req.advance?.pausedReason?.includes('auto_decompose_failed')) {
  throw new Error(
    '自动拆分失败，流程已暂停。' +
    '请先调用 reqboard_clear_pause() 清除暂停状态。' +
    '错误码: REQBOARD_DIVE_PAUSED'
  );
}
```

**错误码**:
- `REQBOARD_DIVE_ARMED`: dive 自动流程已启用
- `REQBOARD_DIVE_PAUSED`: 流程已暂停

### reqboard_move «serves: FR-4, FR-5, FR-6, FR-7»

**变更**: 增加 armed 锁检查

**签名**: 不变

```typescript
interface ReqboardMoveArgs {
  to: StageType;
  requirement_id?: string;
  reason?: string;
}
```

**新增行为**:
```typescript
// 检查 armed 锁（针对 implementing 阶段）
if (req.dive?.activation === 'armed' && args.to === 'implementing') {
  throw new Error(
    'dive 自动流程已启用，不允许手动推进到 implementing。' +
    '实施阶段由 reqboard_task_run 自动执行。' +
    '错误码: REQBOARD_DIVE_ARMED'
  );
}

// 调用门禁检查
if (args.to === 'decomposing') {
  const gateResult = await designGateCheck(req);
  if (!gateResult.passed) {
    throw new Error(
      `设计门禁检查失败: ${gateResult.message}` +
      `未覆盖的 FR: ${gateResult.gaps.join(', ')}` +
      '错误码: REQBOARD_GATE_FAILED'
    );
  }
}

if (args.to === 'implementing') {
  const gateResult = await taskCoverageGateCheck(req);
  if (!gateResult.passed) {
    throw new Error(
      `拆分门禁检查失败: ${gateResult.message}` +
      `未接收的 FR: ${gateResult.orphan_clauses.join(', ')}` +
      '错误码: REQBOARD_GATE_FAILED'
    );
  }
}

if (args.to === 'archived') {
  const gateResult = await acceptanceGateCheck(req);
  if (!gateResult.passed) {
    throw new Error(
      `验收门禁检查失败: ${gateResult.message}` +
      `未通过的 FR: ${gateResult.failed_clauses.map(c => c.id).join(', ')}` +
      '错误码: REQBOARD_GATE_FAILED'
    );
  }
}
```

**错误码**:
- `REQBOARD_DIVE_ARMED`: dive 自动流程已启用
- `REQBOARD_GATE_FAILED`: 门禁检查失败

### reqboard_task_move «serves: FR-7»

**变更**: 增加 armed 锁检查

**签名**: 不变

```typescript
interface ReqboardTaskMoveArgs {
  task_id: string;
  to: TaskStatus;
  reason?: string;
}
```

**新增行为**:
```typescript
// 检查 armed 锁（针对父子卡模式）
const task = await getTask(args.task_id);
const req = await getRequirement(task.requirementId);

if (req.dive?.activation === 'armed' && task.parentId) {
  throw new Error(
    'dive 自动流程已启用，父子卡模式下不允许手动推进子任务。' +
    '请在父卡上调用 reqboard_task_run。' +
    '错误码: REQBOARD_DIVE_ARMED'
  );
}
```

**错误码**:
- `REQBOARD_DIVE_ARMED`: dive 自动流程已启用

### reqboard_clear_pause (新增) «serves: FR-9»

**用途**: 清除暂停状态，解除 armed 锁

**签名**:
```typescript
interface ReqboardClearPauseArgs {
  requirement_id?: string;
  force?: boolean;  // 强制解除，即使没有暂停原因
}

interface ReqboardClearPauseResult {
  success: boolean;
  requirement_id: string;
  cleared: {
    pausedReason?: string;
    activation?: string;  // armed → disarmed
  };
  message: string;
}
```

**行为**:
```typescript
// 清除暂停原因
if (req.advance?.pausedReason) {
  delete req.advance.pausedReason;
}

// 解除 armed 锁
if (req.dive?.activation === 'armed') {
  req.dive.activation = 'disarmed';
}

// 写入评论
await addComment(req.id, {
  type: 'system',
  content: '已清除暂停状态并解除 armed 锁'
});
```

**使用场景**:
- 自动拆分失败后，修复问题，清除暂停状态
- 需要手动介入时，解除 armed 锁
- 紧急情况下的 break glass 操作

## 内部 API «serves: FR-2, FR-3»

### ReqboardDiveManager «serves: FR-2»

**职责**: 在 agent 回合结束时检查并发起续跑

**接口**:
```typescript
class ReqboardDiveManager extends Service {
  static inject = ['agents', 'reqboard'];
  
  constructor(ctx: Context) {
    super(ctx, 'reqboard-dive');
    
    // 在 agent 回合结束时触发
    ctx.on('agent/turn-end', async (event) => {
      await this.checkAndContinue(event.agentId);
    });
  }
  
  async checkAndContinue(agentId: string): Promise<void> {
    // 1. 获取该 agent 绑定的需求
    const requirements = await this.getAgentRequirements(agentId);
    
    // 2. 筛选出 armed 且 active 的需求
    const activeDives = requirements.filter(
      req => req.dive?.activation === 'armed' && 
             req.dive?.phase === 'active'
    );
    
    // 3. 对每个需求发起 followup
    for (const req of activeDives) {
      await this.followupRequirement(agentId, req);
    }
  }
  
  private async followupRequirement(
    agentId: string, 
    req: Requirement
  ): Promise<void> {
    const agent = this.ctx.agents.get(agentId);
    if (!agent) return;
    
    const config = STAGE_CONFIGS[req.dive.currentStage];
    
    // 检查回合数限制
    if (req.dive.roundsInStage >= config.maxRounds) {
      await this.blockRequirement(req, 'max_rounds_exceeded');
      return;
    }
    
    // 发起新回合
    const message = this.buildFollowupMessage(req);
    await agent.followup(message);
    
    // 更新回合数
    req.dive.roundsInStage += 1;
    await this.ctx.reqboard.updateRequirement(req);
  }
  
  private buildFollowupMessage(req: Requirement): string {
    const stage = req.dive.currentStage;
    return `继续执行 ${stage} 阶段任务（需求 ${req.id}）`;
  }
  
  private async blockRequirement(
    req: Requirement, 
    reason: string
  ): Promise<void> {
    req.dive.phase = 'blocked';
    req.dive.blockedReason = reason;
    await this.ctx.reqboard.updateRequirement(req);
    
    // 发送通知
    await this.ctx.notification.send({
      title: `需求 ${req.id} 已阻塞`,
      content: `原因: ${reason}`,
      level: 'high'
    });
  }
}
```

### 门禁函数 «serves: FR-4, FR-5, FR-6»

**设计门禁** «serves: FR-4»

```typescript
async function designGateCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const uncovered = rtm.functional_requirements.filter(
    fr => fr.design_refs.length === 0
  );
  
  if (uncovered.length > 0) {
    return {
      passed: false,
      code: 'design_incomplete',
      gaps: uncovered.map(fr => fr.id),
      message: `${uncovered.length} 个 FR 未被设计覆盖，禁止推进`
    };
  }
  
  return { passed: true };
}
```

**拆分门禁** «serves: FR-5»

```typescript
async function taskCoverageGateCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const uncovered = rtm.functional_requirements.filter(
    fr => fr.task_refs.length === 0
  );
  
  if (uncovered.length > 0) {
    return {
      passed: false,
      code: 'task_coverage_incomplete',
      orphan_clauses: uncovered.map(fr => fr.id),
      message: `${uncovered.length} 个 FR 未被任何任务接收，禁止推进`
    };
  }
  
  return { passed: true };
}
```

**验收门禁** «serves: FR-6»

```typescript
async function acceptanceGateCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const failed = rtm.functional_requirements.filter(
    fr => fr.acceptance_status !== 'passed'
  );
  
  if (failed.length > 0) {
    return {
      passed: false,
      code: 'acceptance_incomplete',
      failed_clauses: failed.map(fr => ({
        id: fr.id,
        status: fr.acceptance_status
      })),
      message: `${failed.length} 个 FR 验收未通过，禁止归档`
    };
  }
  
  return { passed: true };
}
```

### confirm-settle.ts 修改 «serves: FR-3»

**原代码**:
```typescript
// 第 223 行
await executeDecompose(deps, {...}, exec);  // ❌ 需要 live driver
```

**修改后**:
```typescript
// 使用后台 job
const job = await deps.jobs.start({
  type: 'reqboard-decompose',
  payload: {
    requirement_id: req.id,
    tasks: approvedPlan.tasks
  }
});

// 设置 autoRun
req.advance = req.advance || {};
req.advance.autoRun = true;

// 设置 dive armed
if (req.dive) {
  req.dive.activation = 'armed';
  req.dive.phase = 'active';
}

await deps.reqboard.updateRequirement(req);
```

## 错误码体系 «serves: FR-7, FR-9»

| 错误码 | 含义 | 恢复方式 |
|--------|------|----------|
| REQBOARD_DIVE_ARMED | dive 自动流程已启用 | 调用 reqboard_clear_pause() |
| REQBOARD_DIVE_PAUSED | 流程已暂停 | 调用 reqboard_clear_pause() |
| REQBOARD_GATE_FAILED | 门禁检查失败 | 修复问题后重试 |
| REQBOARD_DIVE_BLOCKED | 连续失败已阻塞 | 人工介入修复 |

## 接口向后兼容性 «serves: FR-7»

**原则**: 只增不改

- 工具签名不变
- 新增行为只在 dive 模式下触发
- 老需求（dive=undefined）行为完全不变
- 新增错误码向下兼容（不影响现有错误处理）