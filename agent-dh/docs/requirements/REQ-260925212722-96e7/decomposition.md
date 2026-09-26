# REQ-260925212722-96e7 拆分计划

> REQ 流水线 Dive 模式重构（架构演进）

## 一、代码层面变更盘点

### 新增文件（6个核心 + 5个测试 + 1个迁移 = 12个）

#### 核心应用代码

1. **packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts**
   - Dive 续跑管理器（Service 类）
   - 在回合结束时检查并发起 followup

2. **packages/web/dsh-pmboard/src/application/dive/stage-configs.ts**
   - 阶段配置定义（STAGE_CONFIGS 常量）
   - 混合模式配置接口

3. **packages/web/dsh-pmboard/src/application/gate/design-gate.ts**
   - 设计门禁：检查 FR 设计覆盖度

4. **packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts**
   - 拆分门禁：检查任务覆盖度

5. **packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts**
   - 验收门禁：检查验收完成度

6. **packages/web/dsh-pmboard/src/application/gate/index.ts**
   - 门禁系统统一导出

#### 测试代码

7. **packages/web/dsh-pmboard/tests/dive/dive-manager.test.ts**
   - ReqboardDiveManager 单元测试

8. **packages/web/dsh-pmboard/tests/gate/design-gate.test.ts**
   - 设计门禁测试

9. **packages/web/dsh-pmboard/tests/gate/task-coverage-gate.test.ts**
   - 拆分门禁测试

10. **packages/web/dsh-pmboard/tests/gate/acceptance-gate.test.ts**
    - 验收门禁测试

11. **packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts**
    - E2E 完整流程测试

#### 数据库迁移

12. **packages/web/dsh-pmboard/migrations/add-requirement-dive.sql**
    - 添加 Requirement.dive 字段的 SQL 迁移（如需要）

### 修改文件（6个）

1. **packages/web/dsh-pmboard/src/shared/protocol.ts**
   - 新增 RequirementDive 接口
   - 扩展 Requirement 接口添加 dive 字段

2. **packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts**
   - 修复自动开跑：改用 deps.jobs.start

3. **packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts**
   - 增加 armed 锁检查

4. **packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts**
   - 增加 armed 锁检查
   - 集成 RTM 门禁

5. **packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts**
   - 增加父子卡模式下的 armed 锁检查

6. **packages/web/dsh-pmboard/src/index.ts**
   - 注册 ReqboardDiveManager 服务

### 删除文件（0个）

无删除文件，保持向后兼容。

---

## 二、任务拆分（DAG）

### 批次1：数据结构与基础设施（并行）

#### t1: 扩展数据结构
- **phase**: implement
- **side**: fullstack
- **depends_on**: []
- **requirement_refs**: ["FR-1"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/shared/protocol.ts`
  2. 新增 `RequirementDive` 接口定义（phase/activation/currentStage 等字段）
  3. 扩展 `Requirement` 接口添加 `dive?: RequirementDive` 字段
  4. 确保类型定义完整且兼容现有代码
- **acceptance**:
  ```bash
  # 1. 编译通过
  cd packages/web/dsh-pmboard && pnpm build
  
  # 2. 类型检查通过
  grep "dive?: RequirementDive" src/shared/protocol.ts
  grep "interface RequirementDive" src/shared/protocol.ts
  
  # 3. 字段定义完整（包含 phase/activation/currentStage 等）
  ```

#### t2: 阶段配置定义
- **phase**: implement
- **side**: backend
- **depends_on**: []
- **requirement_refs**: ["FR-8"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/dive/stage-configs.ts`
  2. 定义 `StageConfig` 接口（requiresConfirmation/autoExecute/maxRounds）
  3. 实现 `STAGE_CONFIGS` 常量，配置所有阶段
  4. implementing 设为全自动（requiresConfirmation: false, autoExecute: true）
  5. accepting 设为需确认（requiresConfirmation: true, autoExecute: false）
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/dive/stage-configs.ts
  
  # 2. 导出正确
  grep "export const STAGE_CONFIGS" src/application/dive/stage-configs.ts
  grep "export interface StageConfig" src/application/dive/stage-configs.ts
  
  # 3. 配置正确
  grep "implementing.*requiresConfirmation: false" src/application/dive/stage-configs.ts
  grep "accepting.*autoExecute: false" src/application/dive/stage-configs.ts
  ```

---

### 批次2：修复自动开跑（立即收益）

#### t3: 修复 confirm-settle 自动拆分
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-3"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts`
  2. 定位第 223 行附近的 `await executeDecompose(deps, {...}, exec)` 调用
  3. 改用 `deps.jobs.start()` 启动后台 job
  4. job payload 包含 requirement_id 和 tasks
  5. 设置 autoRun=true 标记
  6. 确保提示词注入逻辑正常（G3 闸门不跳过）
- **acceptance**:
  ```bash
  # 1. 代码已改用 jobs.start
  grep "deps.jobs.start" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts
  
  # 2. 不再直接调用 executeDecompose
  ! grep "await executeDecompose(deps, .*, exec)" packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts
  
  # 3. E2E 测试：创建需求 → 提交计划 → 批准 → 检查 autoRun=true
  # （人工测试，确认自动拆分成功、G3 闸门提示词注入成功）
  ```

---

### 批次3：RTM 门禁实现（强制覆盖）

#### t4: 设计门禁
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-4"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/gate/design-gate.ts`
  2. 实现 `designGateCheck(req: Requirement): Promise<GateResult>` 函数
  3. 读取 RTM 数据（从 docs/requirements/<REQ>/rtm.json 或数据库）
  4. 检查所有 functional_requirements 的 design_refs 是否非空
  5. 返回 GateResult（passed/code/gaps/message）
  6. 创建单元测试 `tests/gate/design-gate.test.ts`
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/gate/design-gate.ts
  
  # 2. 导出正确
  grep "export.*designGateCheck" src/application/gate/design-gate.ts
  
  # 3. 单元测试通过
  cd packages/web/dsh-pmboard && pnpm test -- design-gate.test.ts
  
  # 4. 集成测试：design 阶段跳过一个 FR → 尝试推进 → 被拒绝
  ```

#### t5: 拆分门禁
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-5"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts`
  2. 实现 `taskCoverageGateCheck(req: Requirement): Promise<GateResult>` 函数
  3. 检查所有 functional_requirements 的 task_refs 是否非空
  4. 返回 GateResult（passed/orphan_clauses）
  5. 创建单元测试 `tests/gate/task-coverage-gate.test.ts`
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts
  
  # 2. 导出正确
  grep "export.*taskCoverageGateCheck" src/application/gate/task-coverage-gate.ts
  
  # 3. 单元测试通过
  pnpm test -- task-coverage-gate.test.ts
  
  # 4. 集成测试：拆分计划遗漏一个 FR → 被拒绝
  ```

#### t6: 验收门禁
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-6"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts`
  2. 实现 `acceptanceGateCheck(req: Requirement): Promise<GateResult>` 函数
  3. 检查所有 functional_requirements 的 acceptance_status
  4. 返回 GateResult（passed/failed_clauses）
  5. 创建单元测试 `tests/gate/acceptance-gate.test.ts`
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts
  
  # 2. 导出正确
  grep "export.*acceptanceGateCheck" src/application/gate/acceptance-gate.ts
  
  # 3. 单元测试通过
  pnpm test -- acceptance-gate.test.ts
  
  # 4. 集成测试：验收单有失败项 → 无法归档
  ```

#### t7: 门禁系统统一导出
- **phase**: implement
- **side**: backend
- **depends_on**: ["t4", "t5", "t6"]
- **requirement_refs**: ["FR-4", "FR-5", "FR-6"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/gate/index.ts`
  2. 导出所有门禁函数和 GateResult 接口
  3. 提供统一的门禁调用接口
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/gate/index.ts
  
  # 2. 导出完整
  grep "export.*from './design-gate'" src/application/gate/index.ts
  grep "export.*from './task-coverage-gate'" src/application/gate/index.ts
  grep "export.*from './acceptance-gate'" src/application/gate/index.ts
  grep "export interface GateResult" src/application/gate/index.ts
  ```

---

### 批次4：门禁集成到推进流程

#### t8: 集成门禁到 MoveRequirement
- **phase**: implement
- **side**: backend
- **depends_on**: ["t7"]
- **requirement_refs**: ["FR-4", "FR-5", "FR-6"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
  2. 在 design → decomposing 推进前调用 `designGateCheck`
  3. 在 decomposing → implementing 推进前调用 `taskCoverageGateCheck`
  4. 在 accepting → archived 推进前调用 `acceptanceGateCheck`
  5. 门禁不通过时抛出错误，阻塞推进
- **acceptance**:
  ```bash
  # 1. 代码包含门禁检查
  grep "designGateCheck" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
  grep "taskCoverageGateCheck" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
  grep "acceptanceGateCheck" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
  
  # 2. E2E 测试：门禁不通过时推进被阻塞
  # （在 dive-full-flow.test.ts 中验证）
  ```

---

### 批次5：Dive 管理器实现

#### t9: 实现 ReqboardDiveManager
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1", "t2"]
- **requirement_refs**: ["FR-2"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts`
  2. 实现 Service 类，inject ['agents', 'reqboard']
  3. 实现 `checkAndContinue(agentId: string)` 方法
  4. 检查 dive 状态（armed && active）
  5. 检查回合数限制（roundsInStage < maxRoundsPerStage）
  6. 调用 `ctx.agents.get(agentId).followup()` 发起续跑
  7. 创建单元测试 `tests/dive/dive-manager.test.ts`
- **acceptance**:
  ```bash
  # 1. 文件存在
  ls packages/web/dsh-pmboard/src/application/dive/ReqboardDiveManager.ts
  
  # 2. 类定义正确
  grep "export default class ReqboardDiveManager extends Service" src/application/dive/ReqboardDiveManager.ts
  
  # 3. 依赖注入正确
  grep "static inject = \['agents', 'reqboard'\]" src/application/dive/ReqboardDiveManager.ts
  
  # 4. 单元测试通过
  pnpm test -- dive-manager.test.ts
  ```

#### t10: 注册 DiveManager 到插件
- **phase**: implement
- **side**: backend
- **depends_on**: ["t9"]
- **requirement_refs**: ["FR-2"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/index.ts`
  2. 导入 ReqboardDiveManager
  3. 在插件构造函数中注册服务：`ctx.plugin(ReqboardDiveManager, config)`
  4. 确保 DiveManager 在合适的时机被调用（回合结束时）
- **acceptance**:
  ```bash
  # 1. 导入语句存在
  grep "import.*ReqboardDiveManager" packages/web/dsh-pmboard/src/index.ts
  
  # 2. 注册调用存在
  grep "ctx.plugin(ReqboardDiveManager" packages/web/dsh-pmboard/src/index.ts
  
  # 3. 插件启动成功（启动 DSH 不报错）
  cd agent-dh && ./scripts/start.sh --check
  ```

---

### 批次6：armed 锁机制

#### t11: Decompose 工具增加 armed 检查
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-7"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`
  2. 在执行前检查 `req.dive?.activation === 'armed'`
  3. 如果 armed，抛出错误：`dive 自动流程已启用，不允许手动拆分`
  4. 提示使用 `reqboard_clear_pause()` 解除锁定
- **acceptance**:
  ```bash
  # 1. 代码包含 armed 检查
  grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts
  
  # 2. 错误提示正确
  grep "不允许手动拆分" packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts
  
  # 3. E2E 测试：armed 时调用 reqboard_decompose → 被拒绝
  ```

#### t12: MoveRequirement 工具增加 armed 检查
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-7"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
  2. 在推进到 implementing 前检查 `req.dive?.activation === 'armed'`
  3. 如果 armed，抛出错误：`dive 自动流程已启用，不允许手动推进`
- **acceptance**:
  ```bash
  # 1. 代码包含 armed 检查
  grep "dive?.activation === 'armed'" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
  
  # 2. 只在 to === 'implementing' 时检查
  grep "args.to === 'implementing'" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
  
  # 3. E2E 测试：armed 时手动推进 → 被拒绝
  ```

#### t13: MoveTask 工具增加父子卡检查
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-7"]
- **implementation**:
  1. 修改 `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
  2. 检查任务的 parentId（父子卡模式）
  3. 检查需求的 `dive?.activation === 'armed'`
  4. 如果 armed 且是子任务，抛出错误：`父子卡模式下不允许手动推进子任务`
  5. 提示使用 `reqboard_task_run` 在父卡上执行
- **acceptance**:
  ```bash
  # 1. 代码包含 armed + parentId 检查
  grep "dive?.activation === 'armed'.*task.parentId" packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts
  
  # 2. 错误提示正确
  grep "reqboard_task_run" packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts
  
  # 3. E2E 测试：armed + 子任务时手动推进 → 被拒绝
  ```

---

### 批次7：解锁机制

#### t14: 实现 reqboard_clear_pause 工具
- **phase**: implement
- **side**: backend
- **depends_on**: ["t1"]
- **requirement_refs**: ["FR-9"]
- **implementation**:
  1. 在 `packages/web/dsh-pmboard/src/application/use-cases/` 创建 ClearPause.ts
  2. 实现清除 pausedReason
  3. 实现 disarm（设置 dive.activation = 'disarmed'）
  4. 记录解锁日志到需求评论
  5. 在 `packages/tools/reqboard/src/index.ts` 注册工具
- **acceptance**:
  ```bash
  # 1. 用例文件存在
  ls packages/web/dsh-pmboard/src/application/use-cases/ClearPause.ts
  
  # 2. 工具注册存在
  grep "reqboard_clear_pause" packages/tools/reqboard/src/index.ts
  
  # 3. E2E 测试：clear_pause() → dive.activation = 'disarmed'
  ```

---

### 批次8：E2E 测试与验证

#### t15: E2E 完整流程测试
- **phase**: test
- **side**: fullstack
- **depends_on**: ["t3", "t8", "t10", "t11", "t12", "t13", "t14"]
- **requirement_refs**: ["FR-10"]
- **implementation**:
  1. 创建 `packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts`
  2. 测试完整流程：立项 → brainstorming → design → decomposing → implementing → accepting → archived
  3. 测试自动续跑（不需要用户输入"继续"）
  4. 测试门禁阻塞（有遗漏时无法推进）
  5. 测试 armed 锁机制（手动工具被拒绝）
  6. 测试解锁机制（clear_pause 生效）
- **acceptance**:
  ```bash
  # 1. 测试文件存在
  ls packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts
  
  # 2. 测试通过
  cd packages/web/dsh-pmboard && pnpm test -- dive-full-flow.test.ts
  
  # 3. 覆盖全部阶段和功能点
  grep "brainstorming.*design.*decomposing.*implementing.*accepting.*archived" tests/e2e/dive-full-flow.test.ts
  ```

#### t16: 集成测试与文档
- **phase**: review
- **side**: doc
- **depends_on**: ["t15"]
- **requirement_refs**: ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5", "FR-6", "FR-7", "FR-8", "FR-9", "FR-10"]
- **implementation**:
  1. 运行全量测试套件：`pnpm test`
  2. 检查测试覆盖率（目标 >80%）
  3. 更新文档：docs/architecture/reqboard-dive-mode.md
  4. 更新使用指南：docs/guides/dive-mode-usage.md
  5. 记录已知限制和未来优化点
- **acceptance**:
  ```bash
  # 1. 全量测试通过
  cd packages/web/dsh-pmboard && pnpm test
  
  # 2. 文档已更新
  ls docs/architecture/reqboard-dive-mode.md
  ls docs/guides/dive-mode-usage.md
  
  # 3. 构建成功
  cd agent-dh && pnpm build
  
  # 4. DSH 启动成功
  ./scripts/start.sh --check
  ```

---

## 三、依赖关系图（DAG）

```
批次1（并行）:
  t1: 扩展数据结构
  t2: 阶段配置定义

批次2:
  t3: 修复 confirm-settle [依赖 t1] ✨ 立即收益

批次3（并行）:
  t4: 设计门禁 [依赖 t1]
  t5: 拆分门禁 [依赖 t1]
  t6: 验收门禁 [依赖 t1]

批次4:
  t7: 门禁统一导出 [依赖 t4, t5, t6]
  t8: 集成门禁到 MoveRequirement [依赖 t7]

批次5:
  t9: 实现 ReqboardDiveManager [依赖 t1, t2]
  t10: 注册 DiveManager [依赖 t9]

批次6（并行）:
  t11: Decompose 增加 armed 检查 [依赖 t1]
  t12: MoveRequirement 增加 armed 检查 [依赖 t1]
  t13: MoveTask 增加父子卡检查 [依赖 t1]

批次7:
  t14: 实现 clear_pause 工具 [依赖 t1]

批次8:
  t15: E2E 完整流程测试 [依赖 t3, t8, t10, t11, t12, t13, t14]
  t16: 集成测试与文档 [依赖 t15]
```

---

## 四、风险与缓解

### 风险1：自动续跑失控

**描述**: Dive 逻辑有 bug，无限循环消耗资源

**缓解**:
- maxRoundsPerStage 限制（每阶段默认 3-50 回合）
- 熔断机制（连续失败 3 次自动 disarm）
- 监控和告警（回合数异常时通知）

### 风险2：门禁误判阻塞正常流程

**描述**: RTM 门禁检查逻辑有误，阻塞合法推进

**缓解**:
- 充分的单元测试和集成测试
- 门禁检查结果可追溯（记录到需求评论）
- 提供门禁豁免机制（紧急情况下可跳过）

### 风险3：armed 锁太严格

**描述**: 紧急情况无法手动处理

**缓解**:
- 实现 break glass 解锁机制（reqboard_clear_pause）
- 清晰的错误提示和恢复路径
- 文档说明紧急操作流程

### 风险4：向后兼容性问题

**描述**: 老需求可能受影响

**缓解**:
- dive 字段可选（Requirement.dive?）
- 老需求（无 dive 字段）继续手动模式
- 充分的回归测试

---

## 五、验收标准总览

### 功能完整性

- ✅ 10 个 FR 全部实现
- ✅ 16 个任务卡全部完成
- ✅ E2E 测试覆盖全流程

### 质量指标

- ✅ 自动开跑成功率 > 95%
- ✅ 提示词注入成功率 = 100%
- ✅ RTM 覆盖率 = 100%（强制）
- ✅ 单元测试覆盖率 > 80%

### 用户体验

- ✅ 用户不需要输入"继续"（自动续跑）
- ✅ 只在关键节点需要确认（混合模式）
- ✅ 错误提示清晰，恢复路径明确

### 向后兼容

- ✅ 老需求可以继续用手动模式
- ✅ 现有工具签名不变
- ✅ 现有数据结构扩展性添加

---

## 六、实施优先级

### P0 - 立即收益（1-2天）

- t1, t3: 修复自动开跑问题

### P1 - 核心能力（3-5天）

- t2, t4-t8: RTM 门禁系统
- t9, t10: Dive 管理器

### P2 - 强化约束（2-3天）

- t11-t14: armed 锁机制与解锁

### P3 - 验证与推广（2-3天）

- t15, t16: E2E 测试与文档

---

## 七、估算

**总工作量**: 约 8-13 天

**关键路径**: t1 → t3 → t8 → t10 → t15 → t16

**并行度**: 批次1、3、6 可并行，可压缩到 6-9 天

---

## 八、交付物清单

### 代码

- [ ] 12 个新增文件（6 核心 + 5 测试 + 1 迁移）
- [ ] 6 个修改文件
- [ ] 0 个删除文件

### 测试

- [ ] 单元测试（design/task/acceptance 门禁、dive-manager）
- [ ] E2E 测试（dive-full-flow）
- [ ] 测试覆盖率报告

### 文档

- [ ] docs/architecture/reqboard-dive-mode.md（架构设计）
- [ ] docs/guides/dive-mode-usage.md（使用指南）
- [ ] docs/rfcs/REQ-260925212722-96e7-retrospective.md（复盘）

---

**编写日期**: 2026-09-25  
**编写人**: Claude (session-4211950d)  
**需求ID**: REQ-260925212722-96e7
