# REQ-260925110957-552d 拆分清单（decomposition）

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 任务编号 | 标题 |
|--------|---------|------|
| FR-4 | t1 | 领域类型定义 |
| FR-3 | t1 | 领域类型定义 |
| FR-9 | t1 | 领域类型定义 |
| FR-3 | t2 | 台账迁移 |
| FR-1 | t3 | DSH jobs 适配器 |
| FR-7 | t4 | workflow schema 适配器 |
| FR-4 | t5 | 写集冲突检测 |
| FR-4 | t6 | 批调度器 |
| FR-5 | t7 | 孤儿回收 |
| FR-3 | t8 | checkpoint 管理器 |
| FR-1 | t9 | 后台执行器 |
| FR-3 | t9 | 后台执行器 |
| FR-4 | t9 | 后台执行器 |
| FR-5 | t9 | 后台执行器 |
| FR-1 | t10 | 投递用例 |
| FR-2 | t11 | 查询用例 |
| FR-3 | t12 | 仓储层扩展 |
| FR-5 | t12 | 仓储层扩展 |
| FR-9 | t12 | 仓储层扩展 |
| FR-1 | t13 | AdvanceChain 改造 |
| FR-6 | t13 | AdvanceChain 改造 |
| FR-7 | t14 | ExecuteTask 改造 |
| FR-5 | t15 | 选择器改造 |
| FR-7 | t16 | workflow script 改造 |
| FR-1 | t17 | reqboard_task_run 改造 |
| FR-8 | t17 | reqboard_task_run 改造 |
| FR-2 | t18 | reqboard_run_status 新增 |
| FR-8 | t18 | reqboard_run_status 新增 |
| FR-8 | t19 | 工具注册与提示词 |
| FR-1 | t20 | 集成测试 |
| FR-3 | t20 | 集成测试 |
| FR-5 | t20 | 集成测试 |
| FR-6 | t20 | 集成测试 |
| FR-1 | t21 | E2E 测试 |
| FR-2 | t21 | E2E 测试 |
| FR-3 | t21 | E2E 测试 |
| FR-4 | t21 | E2E 测试 |
| FR-5 | t21 | E2E 测试 |
| FR-6 | t21 | E2E 测试 |
| FR-7 | t21 | E2E 测试 |
| FR-9 | t21 | E2E 测试 |
| FR-8 | t22 | 构建验证 |
| FR-8 | t23 | 部署验证 |

> 需求：REQ 实施链重构：ctx.jobs 异步化 + 写集并行 + 中断可续
> 拆分日期：2026-09-25
> 目标：把 REQ 流水线的子卡执行从「一次工具调用同步跑完整条链」改成「注册后台任务、立即返回、跑完通知」，让拆分产物携带写集并按写集分批真并行，同时补齐中断恢复语义

## 1. 代码层面变更盘点

### 1.1 新增文件

**领域层（domain/）**
- `domain/write-set.ts` - 写集类型定义与冲突检测算法（路径前缀、目录冲突）
- `domain/job-spec.ts` - 后台任务规格类型（jobId / runId / status / heartbeat）
- `domain/checkpoint.ts` - checkpoint 类型（runId / stepIndex / currentSubtaskId / heartbeatAt）

**应用层（application/）**
- `application/use-cases/StartSubtaskChain.ts` - FR-1 投递式调用入口（认领+注册后台任务+立即返回）
- `application/use-cases/QueryRunStatus.ts` - FR-2 运行态查询用例（快照投影）
- `application/internal/batch-scheduler.ts` - FR-4 写集分批调度器（批内并发 / 批间串行）
- `application/internal/orphan-recovery.ts` - FR-5 孤儿回收逻辑（超时判定+退回todo/resume）
- `application/internal/checkpoint-manager.ts` - FR-3 checkpoint 管理器（写入/读取/清理）
- `application/internal/background-runner.ts` - 后台执行器（循环+取消信号+心跳）

**基础设施层（infrastructure/）**
- `infrastructure/dsh-jobs-adapter.ts` - DSH 原生 ctx.jobs 适配器（start/get 的薄封装）
- `infrastructure/workflow-schema-adapter.ts` - FR-7 引擎 schema 产出适配器（agent(prompt,{schema})）

**工具层（tools/）**
- `tools/reqboard_run_status.ts` - FR-2 新增工具：运行态查询

**测试（tests/）**
- `tests/unit/write-set.test.ts` - 写集冲突检测单测
- `tests/unit/batch-scheduler.test.ts` - 分批调度单测
- `tests/unit/orphan-recovery.test.ts` - 孤儿回收单测
- `tests/integration/background-execution.test.ts` - 后台执行集成测试
- `tests/integration/interrupt-resume.test.ts` - 中断恢复集成测试
- `tests/e2e/task-chain.test.ts` - 完整链 E2E 测试

### 1.2 修改文件

**领域层（domain/）**
- `domain/types.ts` - 增加 `filesPlanned?: string[]`（TaskRecord）、运行态字段（RequirementRecord.advance）
- `domain/limits.ts` - 增加孤儿超时阈值、心跳超时阈值常量

**应用层（application/）**
- `application/use-cases/AdvanceChain.ts` - 移除同步循环，改为注册后台任务；补 scanAndResume 的 exec 透传
- `application/use-cases/ExecuteTask.ts` - 改为被后台循环调用（不自带循环）；引擎调用改 schema 产出；先执行后认领
- `application/internal/advance-select.ts` - 选择器补 resume 分支（in_progress 孤儿卡可选）
- `application/internal/workflow-script.ts` - 改用 `agent(prompt, {schema})`，定义结构化产出 schema

**仓储层（repositories/）**
- `repositories/RequirementRepository.ts` - 增加 checkpoint 读写方法、运行态更新方法
- `repositories/TaskRepository.ts` - 增加孤儿查询、批量状态更新方法

**工具层（tools/）**
- `tools/reqboard_task_run.ts` - 改为投递式（调 StartSubtaskChain），返回 dispatched/running + job_id
- `tools/reqboard_task_execute.ts` - 更新为兼容别名，指向 reqboard_task_run

**基础设施层（infrastructure/）**
- `infrastructure/tools/index.ts` - 注册新工具 reqboard_run_status
- `infrastructure/prompts/implementing.txt` - 更新工具描述（投递≠完成，跑完由通知唤醒）

**迁移（migrations/）**
- `migrations/schema-version-8.ts` - 台账版本递增，新增字段迁移逻辑

### 1.3 删除内容

- `application/use-cases/AdvanceChain.ts` 中的同步循环（for i < 20）
- `application/use-cases/ExecuteTask.ts` 中的「先认领后执行」逻辑（改为先执行后认领）
- `application/internal/advance-select.ts` 中只认 `status==='todo'` 的硬限制

## 2. 任务依赖与批次

### 批次 1：数据契约与类型定义（无依赖，并行）

**t1: 领域类型定义**
- 新增 `domain/write-set.ts`、`domain/job-spec.ts`、`domain/checkpoint.ts`
- 修改 `domain/types.ts` 增加新字段
- 修改 `domain/limits.ts` 增加超时常量

**t2: 台账迁移**
- 新增 `migrations/schema-version-8.ts`
- 实现 schemaVersion 7→8 迁移逻辑

### 批次 2：基础设施适配器（依赖批次1）

**t3: DSH jobs 适配器**
- 新增 `infrastructure/dsh-jobs-adapter.ts`
- 封装 ctx.jobs.start / ctx.jobs.get

**t4: workflow schema 适配器**
- 新增 `infrastructure/workflow-schema-adapter.ts`
- 定义 schema、封装 agent(prompt, {schema})

### 批次 3：核心算法实现（依赖批次1，写集不交可并行）

**t5: 写集冲突检测**
- 新增 `domain/write-set.ts` 实现
- 新增 `tests/unit/write-set.test.ts`

**t6: 批调度器**
- 新增 `application/internal/batch-scheduler.ts`
- 新增 `tests/unit/batch-scheduler.test.ts`

**t7: 孤儿回收**
- 新增 `application/internal/orphan-recovery.ts`
- 新增 `tests/unit/orphan-recovery.test.ts`

**t8: checkpoint 管理器**
- 新增 `application/internal/checkpoint-manager.ts`

### 批次 4：用例层重构（依赖批次2、3）

**t9: 后台执行器**
- 新增 `application/internal/background-runner.ts`
- 实现循环+取消信号+心跳

**t10: 投递用例**
- 新增 `application/use-cases/StartSubtaskChain.ts`
- 实现认领+注册+立即返回

**t11: 查询用例**
- 新增 `application/use-cases/QueryRunStatus.ts`
- 实现快照投影

**t12: 仓储层扩展**
- 修改 `repositories/RequirementRepository.ts`
- 修改 `repositories/TaskRepository.ts`

### 批次 5：既有用例改造（依赖批次4）

**t13: AdvanceChain 改造**
- 修改 `application/use-cases/AdvanceChain.ts`
- 移除同步循环，改注册后台任务
- 补 scanAndResume 的 exec 透传

**t14: ExecuteTask 改造**
- 修改 `application/use-cases/ExecuteTask.ts`
- 改为被后台循环调用
- 先执行后认领
- 引擎调用改 schema 产出

**t15: 选择器改造**
- 修改 `application/internal/advance-select.ts`
- 补 resume 分支

**t16: workflow script 改造**
- 修改 `application/internal/workflow-script.ts`
- 改用 agent(prompt, {schema})

### 批次 6：工具接口（依赖批次5）

**t17: reqboard_task_run 改造**
- 修改 `tools/reqboard_task_run.ts`
- 改为投递式调用

**t18: reqboard_run_status 新增**
- 新增 `tools/reqboard_run_status.ts`
- 实现运行态查询

**t19: 工具注册与提示词**
- 修改 `infrastructure/tools/index.ts`
- 修改 `infrastructure/prompts/implementing.txt`
- 修改 `tools/reqboard_task_execute.ts`

### 批次 7：集成与 E2E 测试（依赖批次6）

**t20: 集成测试**
- 新增 `tests/integration/background-execution.test.ts`
- 新增 `tests/integration/interrupt-resume.test.ts`

**t21: E2E 测试**
- 新增 `tests/e2e/task-chain.test.ts`
- 验证完整流程与验收标准

### 批次 8：构建与交付（依赖批次7）

**t22: 构建验证**
- 执行 `pnpm build`
- 验证 dist/index.mjs 生成
- 验证 lib/client.js 生成

**t23: 部署验证**
- 重启 profile
- 验证工具表出现 reqboard_run_status
- 验证 mtime 不旧于 src

## 3. 写集声明与并行度

**批次 1（类型定义，写集不交，可并行）**
- t1 改 domain/，t2 改 migrations/，无冲突

**批次 2（适配器，写集不交，可并行）**
- t3、t4 各自独立文件，无冲突

**批次 3（核心算法，写集不交，可并行）**
- t5、t6、t7、t8 各自独立文件，无冲突

**批次 4（用例层，写集不交，可并行）**
- t9、t10、t11 各自独立文件；t12 改 repositories/，与其他无冲突

**批次 5（既有用例改造，**有目录冲突 application/**，必须串行）**
- t13 改 AdvanceChain.ts
- t14 改 ExecuteTask.ts（依赖 t13 已完成）
- t15 改 advance-select.ts（可与 t13 并行，但与 t14 共享 application/internal/）
- t16 改 workflow-script.ts（可与 t13 并行）

**实际执行顺序**：
1. t13 先（AdvanceChain 调用 StartSubtaskChain）
2. t15、t16 与 t13 并行（不依赖 AdvanceChain 内部实现）
3. t14 后（ExecuteTask 被后台循环调用，需 AdvanceChain 已改造）

**批次 6（工具接口，写集不交，可并行）**
- t17、t18 各自独立文件；t19 改 infrastructure/ 与 tools/，路径不冲突

**批次 7（测试，**有目录冲突 tests/**，必须串行）**
- t20 先（集成测试）
- t21 后（E2E 测试依赖 t20 验证的组件）

**批次 8（构建与部署，必须串行）**
- t22 先（构建产物）
- t23 后（使用 t22 的产物）

## 4. 共享文件先后顺序说明

**application/ 目录冲突（批次5）**：
- t13 (AdvanceChain) → t14 (ExecuteTask)：依赖关系
- t15 (advance-select)、t16 (workflow-script) 可与 t13 并行

**tests/ 目录冲突（批次7）**：
- t20 (集成测试) → t21 (E2E 测试)：组件验证 → 流程验证

**构建链（批次8）**：
- t22 (构建) → t23 (部署)：产物生成 → 产物使用

## 5. 交付标准（对应需求 §9 验收怎么跑）

- [ ] t21 的 E2E 测试全绿，覆盖 A1-A9
- [ ] t22 的构建验证通过，dist/lib 产物完整且新鲜
- [ ] t23 的部署验证通过，工具表可见 reqboard_run_status，调用返回结构化结果
- [ ] 回归验证：同一会话的 tool call aborted 计数归零（需真实会话数据）
- [ ] reqboard_task_run 失败率从 61.3% 降到个位数（需运行统计）

## 6. 兼容性保证

- 旧台账（schemaVersion=7、无 filesPlanned）读取后行为不变：视作「写集未知」→ 全串行
- 旧调用方拿到 dispatched 后若轮询，reqboard_run_status 可满足
- 迁移可回滚：删除/回滚本需求后，新字段被忽略即可回到旧行为

## 7. 风险与缓解

**风险 1**：原生 ctx.jobs 不可用（DSH 版本不支持）
- 缓解：启动时检测 ctx.jobs 存在性，不存在时显式报错并拒绝投递，不静默降级为同步

**风险 2**：写集分批算法复杂度过高
- 缓解：限制单链子卡数上限（如 50），超限时拒绝或降级为全串行

**风险 3**：孤儿回收误判（正常跑的卡被退回）
- 缓解：超时阈值保守设置（3 分钟），心跳机制确认真孤儿

**风险 4**：提示词未同步导致模型误解
- 缓解：t19 同步更新提示词，E2E 测试覆盖新语义

**风险 5**：部署缺环（改 src 不生效）
- 缓解：t22/t23 锁死构建与部署验证，交付判据 A10 强制走完全流程

## 8. 任务-功能点覆盖矩阵

| 任务 | 覆盖功能点 | 说明 |
|------|-----------|------|
| t1 | FR-4, FR-3, FR-9 | 写集类型+checkpoint类型+运行态字段 |
| t2 | FR-3 | 台账迁移 |
| t3 | FR-1 | DSH jobs 适配器 |
| t4 | FR-7 | workflow schema 适配器 |
| t5 | FR-4 | 写集冲突检测 |
| t6 | FR-4 | 批调度器 |
| t7 | FR-5 | 孤儿回收 |
| t8 | FR-3 | checkpoint 管理器 |
| t9 | FR-1, FR-3, FR-4, FR-5 | 后台执行器 |
| t10 | FR-1 | 投递用例 |
| t11 | FR-2 | 查询用例 |
| t12 | FR-3, FR-5, FR-9 | 仓储层扩展 |
| t13 | FR-1, FR-6 | AdvanceChain 改造 |
| t14 | FR-7 | ExecuteTask 改造 |
| t15 | FR-5 | 选择器改造 |
| t16 | FR-7 | workflow script 改造 |
| t17 | FR-1, FR-8 | reqboard_task_run 改造 |
| t18 | FR-2, FR-8 | reqboard_run_status 新增 |
| t19 | FR-8 | 工具注册与提示词 |
| t20 | FR-1, FR-3, FR-5, FR-6 | 集成测试 |
| t21 | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9 | E2E 测试 |
| t22 | FR-8 | 构建验证 |
| t23 | FR-8 | 部署验证 |

**覆盖完整性确认**：
- FR-1（投递式调用）: t3, t9, t10, t13, t17, t20, t21 ✓
- FR-2（运行态查询）: t11, t18, t21 ✓
- FR-3（checkpoint+解耦）: t1, t2, t8, t9, t12, t20, t21 ✓
- FR-4（写集并行）: t1, t5, t6, t9, t21 ✓
- FR-5（孤儿回收）: t7, t9, t12, t15, t20, t21 ✓
- FR-6（exec透传）: t13, t20 ✓
- FR-7（schema产出）: t4, t14, t16, t21 ✓
- FR-8（工具契约）: t17, t18, t19, t22, t23 ✓
- FR-9（运行态可观测）: t1, t12, t21 ✓

全部9条功能点均有任务覆盖，无「本轮不做」项。