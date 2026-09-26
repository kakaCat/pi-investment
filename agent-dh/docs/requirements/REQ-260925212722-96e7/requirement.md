# REQ 流水线 Dive 模式重构（架构演进）

## 一、问题背景

### 当前架构的 5 个关键问题

#### 问题1：自动开跑失败

**现象**：
```
批准拆分计划 → 尝试自动拆分
    ↓
REQBOARD_DRIVER_REQUIRED 错误
    ↓
设置 pausedReason，链停止
```

**根因**：
- `confirm-settle.ts` 第 223 行：`await executeDecompose(deps, {...}, exec)`
- 需要 `live driver`，但 agent 回合已结束
- 弹框回调时，agent 不再是 `currentInitiator()`

**影响**：
- autoRun 未设置
- 自动推进链未启动
- agent 必须手动接管

#### 问题2：提示词注入断裂

**现象**：
```
G3 闸门：[闸门后置链] G3：
  h1-advance=skip（not_advanced）
  h3-inject=skip（negative_verdict）
```

**根因**：
- 自动开跑失败 → `advanced = false`
- 闸门延迟触发（2分钟后）
- `ctx.verdict !== "affirmative"` → h3-inject 跳过

**影响**：
- implementing 阶段的提示词未注入
- 后续窗口缺少上下文

#### 问题3：流程可绕过

**现象**：
```
自动开跑失败
    ↓
agent 看到错误提示
    ↓
agent 手动调用 reqboard_decompose ✅
    ↓
agent 手动推进每个任务 ✅
    ↓
完全绕过自动流程
```

**根因**：
- `reqboard_decompose` 没有检查 `pausedReason`
- `reqboard_move` 没有检查 `autoRun`
- `reqboard_task_move` 没有检查父子卡模式

**影响**：
- 设计意图（自动流程）无法强制执行
- agent 可以随时退化到手动模式

#### 问题4：RTM 覆盖不强制

**现象**：
- 设计阶段可能遗漏 FR 引用
- 拆分阶段可能有 FR 无任务接收
- 验收阶段可能有 FR 未验收

**根因**：
- 当前 RTM 门禁是"软检查"
- 返回 `orphan_clauses` 但不阻塞推进
- agent 可以忽略警告

**影响**：
- 需求追踪链不完整
- 可能遗漏功能点

#### 问题5：用户需要手动续跑

**现象**：
- 每个阶段完成后，用户需要输入"继续"
- agent 不会自动进入下一阶段

**影响**：
- 不是真正的自动化
- 用户介入频繁

---



## 边界

### 做什么

- 实现 Dive 状态机（phase/activation/armed 锁机制）
- 修复自动开跑问题（confirm-settle.ts 改用 job 执行）
- 实现 RTM 三门禁（设计/拆分/验收）强制覆盖完整性
- 实现 armed 锁机制防止手动工具绕过流程
- 实现混合模式配置（implementing 全自动，accepting 需人工确认）

### 不做什么

- 不改变现有需求的手动模式（老需求保持向后兼容）
- 不修复其他无关 bug（顺手发现的问题另立项）
- 不增加新功能（专注重构流程自动化）
- 不改变 pmboard 之外的其他插件



## 现状

**当前架构的核心问题**：

1. **自动开跑失败** - confirm-settle.ts 调用 executeDecompose 需要 live driver，但弹框回调时 agent 回合已结束
2. **提示词注入断裂** - 因自动开跑失败导致 advanced=false，G3 闸门跳过 h3-inject
3. **流程可绕过** - agent 可以手动调用 reqboard_decompose/move/task_move 完全绕过自动流程
4. **RTM 覆盖不强制** - 当前只返回警告，不阻塞推进
5. **用户需手动续跑** - 每个阶段完成后需要用户输入"继续"

**关键文件**：
- `packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts` - 批准确认后的自动推进逻辑
- `packages/web/dsh-pmboard/src/shared/protocol.ts` - Requirement 数据结构
- `packages/web/dsh-pmboard/src/application/use-cases/` - 各种操作的用例实现

## 目标结构：Dive + RTM 架构

### 核心思路

参考 **DSH Goal** 的 dive 机制，引入：

1. **Dive 状态机**：控制自动续跑
2. **RTM 强制门禁**：保证覆盖完整
3. **armed 锁机制**：防止绕过流程
4. **混合模式**：保留用户确认点

### 2.1 Dive 状态机

```typescript
interface RequirementDive {
  // 核心状态
  phase: "active" | "paused" | "blocked" | "complete";
  activation: "armed" | "disarmed";
  
  // 阶段管理
  currentStage: StageType;  // brainstorming | design | ...
  stagesCompleted: StageType[];
  
  // 回合控制
  roundsInStage: number;
  maxRoundsPerStage: number;
  
  // 失败控制
  pausedReason?: string;
  blockedReason?: string;
}
```

**状态转换**：
```
create_requirement
    ↓
dive.activation = "armed"
dive.phase = "active"
dive.currentStage = "brainstorming"
    ↓
┌─────────────────────────────┐
│  DSH 检查 dive 状态         │
│  if (armed && active) {     │
│    发起新回合（followup）    │
│  }                          │
└─────────────────────────────┘
    ↓
Agent 自动执行当前阶段任务
    ↓
阶段完成 → 用户确认（可选）
    ↓
推进到下一阶段
dive.currentStage = next
dive.roundsInStage = 0
    ↓
继续 dive（不需要用户输入）
```

### 2.2 阶段配置（混合模式）

```typescript
interface StageConfig {
  requiresConfirmation: boolean;  // 是否需要用户确认
  autoExecute: boolean;           // 确认后是否自动续跑
  maxRounds: number;              // 该阶段最大回合数
}

const STAGE_CONFIGS = {
  brainstorming: { 
    requiresConfirmation: true,   // 需求文档需确认
    autoExecute: true,            // 确认后自动进入 design
    maxRounds: 5
  },
  design: { 
    requiresConfirmation: true,   // 设计文档需确认
    autoExecute: true,
    maxRounds: 5
  },
  decomposing: { 
    requiresConfirmation: true,   // 拆分计划需批准
    autoExecute: true,            // 批准后自动拆分+执行
    maxRounds: 3
  },
  implementing: { 
    requiresConfirmation: false,  // 任务自动执行 ⚡️
    autoExecute: true,            // 全自动
    maxRounds: 50
  },
  accepting: { 
    requiresConfirmation: true,   // 验收需人工审核
    autoExecute: false,           // 不自动归档
    maxRounds: 5
  }
};
```

### 2.3 RTM 强制门禁

#### G1：设计门禁

```typescript
// design → decomposing 推进前强制检查
async function designGateCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const uncovered = rtm.functional_requirements.filter(
    fr => fr.design_refs.length === 0
  );
  
  if (uncovered.length > 0) {
    return {
      passed: false,
      code: "design_incomplete",
      gaps: uncovered.map(fr => fr.id),
      message: `${uncovered.length} 个 FR 未被设计覆盖，禁止推进`
    };
  }
  
  return { passed: true };
}
```

#### G2：拆分门禁

```typescript
// decomposing → implementing 推进前强制检查
async function taskCoverageCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const uncovered = rtm.functional_requirements.filter(
    fr => fr.task_refs.length === 0
  );
  
  if (uncovered.length > 0) {
    return {
      passed: false,
      code: "task_coverage_incomplete",
      orphan_clauses: uncovered.map(fr => fr.id),
      message: `${uncovered.length} 个 FR 未被任何任务接收，禁止推进`
    };
  }
  
  return { passed: true };
}
```

#### G3：验收门禁

```typescript
// accepting → archived 推进前强制检查
async function acceptanceGateCheck(req: Requirement): Promise<GateResult> {
  const rtm = await loadRTM(req.id);
  
  const failed = rtm.functional_requirements.filter(
    fr => fr.acceptance_status !== "passed"
  );
  
  if (failed.length > 0) {
    return {
      passed: false,
      code: "acceptance_incomplete",
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

### 2.4 armed 锁机制

```typescript
// reqboard_decompose 工具
async function reqboard_decompose(args: any) {
  const req = await getRequirement(args.requirement_id);
  
  // 检查是否应该走自动流程
  if (req.dive?.activation === 'armed') {
    throw new Error(
      'dive 自动流程已启用，不允许手动拆分。' +
      '请等待自动流程完成，或调用 reqboard_clear_pause() 解除锁定。'
    );
  }
  
  // 检查是否有暂停原因
  if (req.advance?.pausedReason?.includes('auto_decompose_failed')) {
    throw new Error(
      '自动拆分失败，流程已暂停。' +
      '请先调用 reqboard_clear_pause() 清除暂停状态。'
    );
  }
  
  // 正常执行
  return await executeDecompose(deps, args);
}

// reqboard_move 工具
async function reqboard_move(args: any) {
  const req = await getRequirement(args.requirement_id);
  
  if (req.dive?.activation === 'armed' && args.to === 'implementing') {
    throw new Error(
      'dive 自动流程已启用，不允许手动推进。' +
      '实施阶段由 reqboard_task_run 自动执行。'
    );
  }
  
  return await moveRequirement(deps, args);
}

// reqboard_task_move 工具
async function reqboard_task_move(args: any) {
  const task = await getTask(args.task_id);
  const req = await getRequirement(task.requirementId);
  
  if (req.dive?.activation === 'armed' && task.parentId) {
    throw new Error(
      'dive 自动流程已启用，父子卡模式下不允许手动推进子任务。' +
      '请在父卡上调用 reqboard_task_run。'
    );
  }
  
  return await moveTask(deps, args);
}
```

---

## 三、功能点清单（Functional Requirements）

- **FR-1: Dive 状态管理**

**描述**：实现需求的 dive 状态数据结构和基础操作

**验收标准**：
```bash
# 1. Requirement 数据结构包含 dive 字段
grep -r "dive?" packages/web/dsh-pmboard/src/shared/protocol.ts

# 2. 可以设置和读取 dive 状态
# 测试代码验证 dive 状态转换
```

- **FR-2: Dive 续跑管理器**

**描述**：实现 ReqboardDiveManager，在回合结束时检查并发起续跑

**验收标准**：
```bash
# 1. ReqboardDiveManager 类存在
ls packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts

# 2. 集成到 pmboard 插件
grep -r "ReqboardDiveManager" packages/web/dsh-pmboard/src/index.ts

# 3. 自动续跑测试通过
pnpm test -- dive-manager.test.ts
```

- **FR-3: 修复自动开跑（改用 job）**

**描述**：confirm-settle.ts 中的自动拆分改用后台 job 执行

**验收标准**：
```bash
# 1. 代码已改用 deps.jobs.start
grep "deps.jobs.start" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts

# 2. 不再调用需要 live driver 的 executeDecompose
! grep "await executeDecompose(deps, .*, exec)" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts

# 3. 批准拆分计划后自动开跑成功
# 手动测试：创建需求 → 批准计划 → 检查 autoRun=true
```

- **FR-4: RTM 设计门禁**

**描述**：design → decomposing 推进前检查 FR 设计覆盖度

**验收标准**：
```bash
# 1. 门禁函数存在
grep -r "designGateCheck" packages/web/dsh-pmboard/src/application/gate/

# 2. 集成到推进流程
grep "designGateCheck" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts

# 3. 有 FR 未覆盖时阻塞推进
# 测试：design 阶段跳过一个 FR → 尝试推进 → 应该被拒绝
```

- **FR-5: RTM 拆分门禁**

**描述**：decomposing → implementing 推进前检查任务覆盖度

**验收标准**：
```bash
# 1. 门禁函数存在
grep -r "taskCoverageCheck" packages/web/dsh-pmboard/src/application/gate/

# 2. 集成到推进流程
grep "taskCoverageCheck" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts

# 3. 有 FR 未接收时阻塞推进
# 测试：拆分计划遗漏一个 FR → 应该被拒绝
```

- **FR-6: RTM 验收门禁**

**描述**：accepting → archived 推进前检查验收完成度

**验收标准**：
```bash
# 1. 门禁函数存在
grep -r "acceptanceGateCheck" packages/web/dsh-pmboard/src/application/gate/

# 2. 集成到归档流程
grep "acceptanceGateCheck" packages/web/dsh-pmboard/src/application/use-cases/

# 3. 有 FR 未通过时阻塞归档
# 测试：验收单有失败项 → 应该无法归档
```

- **FR-7: armed 锁机制**

**描述**：dive armed 时禁止手动工具

**验收标准**：
```bash
# 1. reqboard_decompose 检查 armed
grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts

# 2. reqboard_move 检查 armed
grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts

# 3. reqboard_task_move 检查 armed
grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts

# 4. armed 时调用手动工具被拒绝
# 测试：dive armed 时调用 reqboard_decompose → 应该报错
```

- **FR-8: 阶段配置与混合模式**

**描述**：每个阶段可配置是否需要确认、是否自动执行

**验收标准**：
```bash
# 1. STAGE_CONFIGS 定义存在
grep -r "STAGE_CONFIGS" packages/web/dsh-pmboard/src/application/dive/

# 2. implementing 阶段配置为全自动
# requiresConfirmation: false, autoExecute: true

# 3. accepting 阶段不自动归档
# requiresConfirmation: true, autoExecute: false
```

- **FR-9: 解锁机制（break glass）**

**描述**：紧急情况下可以手动解除 dive 锁定

**验收标准**：
```bash
# 1. reqboard_clear_pause 工具存在
grep "reqboard_clear_pause" packages/tools/reqboard/src/index.ts

# 2. 可以清除 pausedReason 和 disarm
# 测试：clear_pause() → dive.activation = disarmed
```

- **FR-10: E2E 测试**

**描述**：完整流程测试，从立项到归档

**验收标准**：
```bash
# 1. E2E 测试文件存在
ls packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts

# 2. 测试覆盖全部阶段
# brainstorming → design → decomposing → implementing → accepting → archived

# 3. 测试通过
pnpm test -- dive-full-flow.test.ts
```

---

## 四、非功能需求

### NFR-1：性能

- Dive 续跑检查延迟 < 1s
- RTM 门禁检查延迟 < 2s
- 不影响现有需求的性能

### NFR-2：兼容性

- 老需求可以继续用手动模式
- 新需求可选启用 dive 模式
- 不破坏现有数据结构

### NFR-3：可观测性

- Dive 状态变化写入评论
- 门禁检查结果可追溯
- armed 锁定/解锁有日志

---



## 行为不变式

### 向后兼容

- 老需求（无 dive 字段）继续使用手动模式，行为完全不变
- 现有工具签名不变（reqboard_decompose/move/task_move 等）
- 现有数据结构扩展性添加（Requirement.dive 可选字段）

### 行为等价

- 手动模式下的推进流程与当前完全一致（输入输出、错误码、副作用）
- RTM 门禁只增强检查，不改变正常流程的推进路径
- 自动流程的最终结果与手动逐步执行等价

### 接口稳定

- 所有对外暴露的工具保持签名不变
- 错误码体系保持一致（新增错误码向下兼容）
- 数据库 schema 只增不减（Requirement 表添加 dive 字段）

## 五、实施计划

### 阶段1：修复自动开跑（1-2 天）✨ 立即收益

**目标**：解决 live driver 问题

**任务**：
- 修改 confirm-settle.ts，改用 `deps.jobs.start`
- 测试批准计划 → 自动拆分成功
- 验证 autoRun=true，提示词注入成功

**验收**：
- FR-3 通过
- G3 闸门不再跳过 h3-inject

### 阶段2：增加 dive 状态（2-3 天）

**目标**：数据结构和基础能力

**任务**：
- 实现 RequirementDive 接口（FR-1）
- 实现 ReqboardDiveManager（FR-2）
- 实现 STAGE_CONFIGS（FR-8）
- 新需求可选启用 dive

**验收**：
- FR-1, FR-2, FR-8 通过
- 创建需求时可以选择 dive 模式

### 阶段3：实现 RTM 门禁（3-5 天）

**目标**：强制覆盖完整性

**任务**：
- 实现设计门禁（FR-4）
- 实现拆分门禁（FR-5）
- 实现验收门禁（FR-6）
- 集成到推进流程

**验收**：
- FR-4, FR-5, FR-6 通过
- 有遗漏时推进被阻塞

### 阶段4：强化约束（2-3 天）

**目标**：防止绕过流程

**任务**：
- 实现 armed 锁机制（FR-7）
- 实现解锁机制（FR-9）
- E2E 测试（FR-10）

**验收**：
- FR-7, FR-9, FR-10 通过
- armed 时手动工具被拒绝

### 阶段5：全面推广（1-2 周）

**目标**：生产使用

**任务**：
- 所有新需求默认 dive 模式
- 监控和优化
- 文档和培训

---

## 六、风险和缓解

### 风险1：Dive 续跑失控

**描述**：如果 dive 逻辑有 bug，会无限循环

**缓解**：
- maxRoundsPerStage 限制
- 熔断机制（连续失败 3 次自动 disarm）
- 监控和告警

### 风险2：armed 锁太严格

**描述**：紧急情况无法手动处理

**缓解**：
- 实现 break glass 解锁机制
- 清晰的错误提示和恢复路径
- 文档说明紧急操作流程

### 风险3：RTM 门禁误判

**描述**：门禁逻辑有误，阻塞正常流程

**缓解**：
- 门禁检查结果可追溯
- 实现门禁豁免机制
- 充分测试覆盖

### 风险4：性能问题

**描述**：dive 续跑频繁，RTM 扫描慢

**缓解**：
- RTM 结果缓存
- 增量更新机制
- 性能监控

---

## 七、成功标准

### 功能完整性

- ✅ 10 个 FR 全部实现并通过验收
- ✅ E2E 测试覆盖全流程
- ✅ 所有门禁正常工作

### 质量指标

- ✅ 自动开跑成功率 > 95%
- ✅ 提示词注入成功率 = 100%
- ✅ RTM 覆盖率 = 100%（强制）

### 用户体验

- ✅ 用户不需要输入"继续"
- ✅ 只在关键节点需要确认
- ✅ 错误提示清晰，恢复路径明确

---

## 八、参考资料

- [DSH Goal 机制](https://github.com/deepseek-ai/dsh)
- [React Hooks 迁移指南](https://react.dev/learn/hooks)
- [Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |
| FR-8 | 🔴 **未被接收** | — |
| FR-9 | 🔴 **未被接收** | — |
| FR-10 | 🔴 **未被接收** | — |

> 🔴 **未被接收（10 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7、FR-8、FR-9、FR-10

<!-- reqboard:marks:end -->
