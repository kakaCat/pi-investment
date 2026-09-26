# 测试用例

## 单元测试

### 1. 设计门禁测试（design-gate.test.ts）

#### 测试用例 1.1：FR 全部被设计覆盖
- **输入**：所有 FR 都有 design_refs
- **预期**：`passed: true`
- **状态**：✓ 通过

#### 测试用例 1.2：部分 FR 未被覆盖
- **输入**：FR-1 无 design_refs
- **预期**：`passed: false, code: 'design_incomplete', gaps: ['FR-1']`
- **状态**：✓ 通过

#### 测试用例 1.3：空需求
- **输入**：无 FR
- **预期**：`passed: true`（无 FR 视为通过）
- **状态**：✓ 通过

### 2. 任务覆盖门禁测试（task-coverage-gate.test.ts）

#### 测试用例 2.1：FR 全部被任务接收
- **输入**：所有 FR 都有 task_refs
- **预期**：`passed: true`
- **状态**：✓ 通过

#### 测试用例 2.2：部分 FR 未被接收
- **输入**：FR-2 无 task_refs
- **预期**：`passed: false, code: 'task_coverage_incomplete', orphan_clauses: ['FR-2']`
- **状态**：✓ 通过

#### 测试用例 2.3：空需求
- **输入**：无 FR
- **预期**：`passed: true`
- **状态**：✓ 通过

### 3. 验收门禁测试（acceptance-gate.test.ts）

#### 测试用例 3.1：FR 全部验收通过
- **输入**：所有 FR acceptance_status = 'passed'
- **预期**：`passed: true`
- **状态**：✓ 通过

#### 测试用例 3.2：部分 FR 验收未通过
- **输入**：FR-3 acceptance_status = 'failed'
- **预期**：`passed: false, code: 'acceptance_incomplete', failed_clauses: [{id: 'FR-3', status: 'failed'}]`
- **状态**：✓ 通过

#### 测试用例 3.3：空需求
- **输入**：无 FR
- **预期**：`passed: true`
- **状态**：✓ 通过

## E2E 测试

### 完整 Dive 流程测试（dive-full-flow.test.ts）

#### 测试用例 4.1：创建需求并启用 Dive
- **步骤**：创建需求 → 设置 dive.activation = 'armed'
- **预期**：dive 状态正确初始化
- **状态**：✓ 通过

#### 测试用例 4.2：自动续跑检查
- **步骤**：armed 需求 → 调用 checkAndContinue
- **预期**：返回 true，发起续跑
- **状态**：✓ 通过

#### 测试用例 4.3：disarmed 不续跑
- **步骤**：disarmed 需求 → 调用 checkAndContinue
- **预期**：返回 false，不续跑
- **状态**：✓ 通过

#### 测试用例 4.4：设计门禁阻塞推进
- **步骤**：design → decomposing，但有 FR 未覆盖
- **预期**：推进被拒绝
- **状态**：✓ 通过

#### 测试用例 4.5：任务覆盖门禁阻塞推进
- **步骤**：decomposing → implementing，但有 FR 未接收
- **预期**：推进被拒绝
- **状态**：✓ 通过

#### 测试用例 4.6：验收门禁阻塞归档
- **步骤**：accepting → archived，但有 FR 未通过
- **预期**：归档被拒绝
- **状态**：✓ 通过

#### 测试用例 4.7：armed 锁定 Decompose
- **步骤**：armed 需求 → 手动调用 reqboard_decompose
- **预期**：被拒绝，提示使用自动流程
- **状态**：✓ 通过

#### 测试用例 4.8：armed 锁定 MoveRequirement
- **步骤**：armed 需求 → 手动推进到 implementing
- **预期**：被拒绝
- **状态**：✓ 通过

#### 测试用例 4.9：armed 锁定 MoveTask
- **步骤**：armed 需求 → 手动推进子任务
- **预期**：被拒绝
- **状态**：✓ 通过

#### 测试用例 4.10：ClearPause 解锁
- **步骤**：armed + paused 需求 → 调用 clear_pause
- **预期**：pausedReason 清除，dive.activation = 'disarmed'
- **状态**：✓ 通过

#### 测试用例 4.11：阶段配置生效
- **步骤**：检查各阶段 STAGE_CONFIGS
- **预期**：implementing 为全自动，accepting 需人工确认
- **状态**：✓ 通过

## 集成测试

### 自动开跑测试

#### 测试用例 5.1：批准计划后自动拆分
- **步骤**：批准拆分计划 → 检查是否使用 jobs.start
- **预期**：后台 job 执行，不需要 live driver
- **状态**：✓ 通过（代码审查）

## 测试覆盖率

- **单元测试**：9/9 通过（100%）
- **E2E 测试**：11/11 通过（100%）
- **整体测试**：1983/2035 通过（97.4%）

## 测试环境

- 测试框架：Vitest 2.1.9
- 运行环境：Node.js
- 测试时长：~8 秒
