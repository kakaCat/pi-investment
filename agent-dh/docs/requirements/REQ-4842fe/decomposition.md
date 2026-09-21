# REQ-4842fe 拆分：变更盘点与任务批次

> 上游：plan.md（已获批准）+ design/（7 份）。本文件只做**代码层面变更盘点**与批次编排，不二次创作设计（与设计矛盾时退回设计改计划）。

## 1. 代码层面变更盘点

### 1.1 新增

| 路径 | 内容 | 卡 |
|---|---|---|
| `src/domain/task/SubtaskTemplate.ts` | StageKind 枚举、类型→子卡映射表、validateExplicitStages、buildSubtaskSpecs | t1 |
| `src/application/ports.ts`（增接口） | `WorkflowRunner` 端口 | t4 |
| `src/adapters/WorkflowEngineRunner.ts` | 唯一封装 `ctx.workflowEngine.start`（run.result + finally dispose） | t4 |
| `src/application/internal/workflow-script.ts` | 子卡脚本生成器 + `assertScriptContract`（hook 白名单门禁） | t4 |
| `src/application/use-cases/ExecuteTask.ts` | 单张子卡闭环（run → report → 凭证 → done） | t5 |
| `src/application/internal/subtask-evidence.ts` | 子卡凭证口径（三项校验，豁免窗口活动） | t5 |
| `src/application/use-cases/AdvanceChain.ts` | 事件链执行器（事件类型/单飞锁/幂等/恢复扫描/熔断） | t7 |
| `src/tools/AdvanceTool/` | 工具 `reqboard_task_run`（壳 + types） | t10 |
| `tests/SubtaskTemplate.spec.ts` | 映射表与逃生舱口用例 | t1 |
| `tests/LazyExpand.spec.ts` | 懒展开与幂等用例 | t6 |
| `tests/AdvanceChain.spec.ts` | 事件链/暂停/恢复/熔断用例 | t7 |
| `tests/WorkflowScriptContract.spec.ts` | 脚本 hook 白名单门禁用例 | t4 |

### 1.2 修改

| 路径 | 改动 | 卡 |
|---|---|---|
| `src/domain/task/TaskStatus.ts` | 新增 `SUBTASK_TRANSITIONS`；`assertTaskTransition` 增 role 入参；人工门增 `done>in_progress`、`done>canceled` | t2 |
| `src/domain/requirement/RequirementStatus.ts` | `implementing` 增 `design` 并列入 `HUMAN_ONLY_REQ_TRANSITIONS` | t2 |
| `src/domain/limits.ts` | 增 `MAX_PARALLEL_PARENTS`、停滞/失败熔断阈值 | t9 |
| `src/shared/protocol.ts` | TaskRecord 增 `parentId/stageKind/attempt/revisions`；RequirementRecord 增 `autoRun`；`AdvanceRecord` 类型；INV-1/2/3 校验 | t3 |
| `src/application/use-cases/MoveTask.ts` | 开工同事务懒展开；并发上限校验；子卡转移收紧 | t6 / t9 |
| `src/application/use-cases/Decompose.ts` | 改动面重叠拦截；显式 `stages` 透传 | t9 / t1 |
| `src/application/use-cases/AskConfirm.ts` + `MoveRequirement.ts` | 批准计划即自动 decompose + `autoRun=true` + 触发首个事件；放行 `decomposing>implementing` | t10 |
| `src/application/internal/support.ts` | 凭证门分叉：子卡走新口径（`assertDoneEvidence` 按 role 分派） | t5 |
| `src/tools/index.ts`、`src/index.ts` | 注册 `AdvanceTool` | t10 |
| `tests/plugin-schema.smoke.test.ts` | PLUGINS 增 AdvanceTool | t10 |
| `src/client/*`（渲染层） | 父子卡折叠展示、进度、autoRun 徽标与控制面 | t11 |

### 1.3 删除 / 下线

| 对象 | 处置 | 卡 |
|---|---|---|
| `TaskExecuteTool.ts:93` 的 `ctx.tools.workflow(...)` 调用 | 删除（依赖被禁工具，且与引擎消费方式冲突） | t10 |
| `generate-workflow-script.ts:8` 的 `ctx.subagent(...)` 生成逻辑 | 删除（引擎无 ctx，必炸） | t10 |
| `tests/reqboard-task-execute.test.ts` 的 grep 式断言 | 替换为 `WorkflowScriptContract.spec.ts` 的契约断言 | t10 / t4 |
| `TaskExecuteTool` 目录 | 下线（由 AdvanceTool + ExecuteTask 取代）；若保号则改薄壳转发 | t10 |

## 2. 批次与依赖（依赖安全序，无前向引用）

| 批次 | 卡 | 依赖来源 |
|---|---|---|
| 批 1 · 接口与契约 | t1 → t2 / t3 / t4 | t1 是映射表，被本批全部依赖 |
| 批 2 · 叶子与展开 | t5（t3,t4）、t6（t3） | 依赖批 1 已定义的契约与 adapter |
| 批 3 · 事件链 | t7（t5,t6） | 依赖叶子执行与懒展开落地 |
| 批 4 · 分支能力与接线 | t8（t7）、t9（t7）、t10（t7） | 三者均只依赖 t7，可并行 |
| 批 5 · 界面与验收 | t11（t6,t10）、t12（t8,t9,t10,t11） | t11 依赖展开与工具接线；t12 收口 |

**前向引用检查**：每张卡的 depends_on 均指向同批更早或早前批次已定义的 key，无后向引用。

## 3. 卡质量自检（薄卡拒落三条）

- ✅ 每卡都有 `implementation`（改哪些文件 + 步骤 + 验证方式），见 plan.md 任务细节；
- ✅ 每卡 acceptance 均可证伪（命令 / 断言词 / 文件路径锚点，已通过门禁校验）；
- ✅ 每卡可独立验收：新窗口零会话历史时，凭卡内 implementation + acceptance + 引用文档路径即可开工（design/ 下 7 份为共用上下文）。

## 4. 边界校验

- 本拆分与 design/ 一致，无二次创作；若实施中发现设计矛盾 → 退回 design 重交计划并重新批准；
- 不越范围：不引入存量卡迁移、不改看板视觉体系、不恢复被禁 delegation 组（requirement §5 边界）；
- 条款覆盖：FR-1、FR-1b、FR-2~FR-16 全部有承接卡（要求文档 §4 清单逐条映射）。
