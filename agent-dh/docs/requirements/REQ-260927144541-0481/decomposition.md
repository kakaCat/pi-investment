# 拆分计划（REQ-260927144541-0481）

> 目标：让「父卡管交付、子卡管执行」这件事在**任务/链级工具面**上看得见、说得清、查得到。
> 做法：**契约先行**（先定 task_run / task_status / task_tree 的入参与返回），再逐条落实现
> （链入口收口 → 新增 task_tree → task_status 换台账源 → task_move 角色感知+acceptance 接线 → 超时归位），
> 最后把「声明必须等于行为」固化成门禁。
> 设计依据：design/{architecture,data-model,interfaces,test-cases,use-cases}.md。
> 范围：**只含任务/链侧**；需求级工具（clear_pause 等）已移出，另立项。

## §1 改动盘点

### 新增

| 文件 | 用途 | serves |
|---|---|---|
| `src/tools/TaskTreeTool/TaskTreeTool.ts` + `prompt.ts` + `index.ts` | 只读父子结构视图工具 | FR-3 |
| `src/application/use-cases/TaskTree.ts` | task_tree 用例（只读，经端口） | FR-3 |
| `tests/task-tree.test.ts` | task_tree 单测（含未绑定/无子卡） | FR-3 |
| `tests/task-run-contract.test.ts` | task_run 参数与返回体契约 | FR-1, FR-2 |
| `tests/task-status-ledger.test.ts` | task_status 台账数据源 | FR-4 |
| `tests/task-move-role.test.ts` | 角色报错 + acceptance 修订接线 | FR-5 |

### 修改

| 文件 | 改动 | serves |
|---|---|---|
| `src/tools/AdvanceTool/AdvanceTool.ts` | 参数加 `requirement_id`；返回体与 `output.schema` 对齐 | FR-1, FR-2 |
| `src/tools/AdvanceTool/prompt.ts` | 文案补「调用即开启 autoRun」与参数语义 | FR-1 |
| `src/tools/TaskExecuteTool/TaskExecuteTool.ts` | 改为逐行委托；标 deprecated | FR-1 |
| `src/tools/TaskStatusTool/TaskStatusTool.ts` | 删 `## Workflow` 解析与直连 fs；改读台账并经端口 | FR-4 |
| `src/application/use-cases/MoveTask.ts` + `src/tools/TaskMoveTool/TaskMoveTool.ts` | 角色感知报错；参数加 `acceptance` 并接线 | FR-5 |
| `src/domain/task/TaskStatus.ts` | 暴露「角色 → 合法边」文本（供报错用，不改转移表取值） | FR-5 |
| 四个工具 `timeoutMs` | 归位到 `timeoutWriteMs`/`timeoutReadMs` | FR-6 |
| `tests/output-contract.test.ts` / `tests/tools-schema.test.ts` | 门禁全量化 + 故障注入 | FR-7 |
| `src/index.ts` | 注册 TaskTreeTool | FR-3 |
| `docs/architecture/reqboard-implement-chain-flow.md` | 工具面章节同步 | FR-1, FR-3 |

### 删除

| 符号 | 原用途 | 替代 |
|---|---|---|
| `TaskStatusTool.parseWorkflowFromTaskCard` | 读 `## Workflow`（全仓无写入方） | 台账 `lastRun`/`lastReport` |
| `AdvanceTool output.schema` 的 `subtask_executed/blocked/stopped` | 已不返回 | 实际返回键 `job_id/run_id/running` |

### 不改动（边界）

- 父卡/子卡/legacy 的**转移表取值**、子卡凭证门、父卡收尾门、懒展开时机、编排逻辑（判定逻辑一律不动）。
- 需求级工具（`clear_pause` 等）、看板 HTTP 路由与客户端。

## §2 任务表

> 依赖按表内顺序解析；被依赖任务必须排在前面（禁止前向引用）。

| key | 标题 | phase | side | 依赖 | 实施方案 | 验收标准 |
|---|---|---|---|---|---|---|
| t1 | 先定契约：任务/链工具的入参与返回长什么样 | implement | backend | - | 按 design/interfaces I-1/I-2/I-3/I-4 改 `AdvanceTool`/`TaskExecuteTool`/`TaskStatusTool` 的 `parameters` 与 `output.schema`；新建 `TaskTreeTool` 壳的参数与输出 schema（先定形状，不填实现）。 | `node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts tests/tools-schema.test.ts`：defineAdvanceTool 用例绿（3 个未声明键补齐）、新 TaskTreeTool 构造不抛。 |
| t2 | 链只留一个入口：起链工具收口，别名不再各跑一套 | implement | backend | t1 | `AdvanceTool` 参数支持 `requirement_id`（与 `task_id` 至少其一）、描述补「调用即写 autoRun」；`TaskExecuteTool` 改逐行委托同一用例与返回体并标 deprecated。 | 新增 `tests/task-run-contract.test.ts` 全绿：传 task_id / requirement_id 两种调用返回同形且 `req.autoRun=true`；都不传且未绑定 → `REQBOARD_NO_BOUND_REQ`。 |
| t3 | 一眼看清父子：新增「父卡→子卡」结构查询 | implement | backend | t1 | 新增 `TaskTree.ts` 用例 + `TaskTreeTool`（只读，经 `deps.repo`），在 `src/index.ts` 注册；返回父卡 + 子卡链（按链序）。 | 新增 `tests/task-tree.test.ts` 全绿：含 4 子卡的父卡返回 `subtasks.length=4` 且链序；无子卡返回 `[]` + note；跨窗口 → `REQBOARD_NOT_BOUND_TO_WINDOW`。 |
| t4 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落 | implement | backend | t1 | `TaskStatusTool` 删 `parseWorkflowFromTaskCard` 与 `fs` 直读，改从 `deps.repo.snapshot()` 读 `lastRun`/`lastReport`；`workflow` 键保留为 run 摘要。 | `grep -rn "## Workflow" packages/web/dsh-pmboard/src` 无输出；新增 `tests/task-status-ledger.test.ts` 全绿（无 `lastRun` 时不报错、不伪造）。 |
| t5 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改 | implement | backend | t1 | `TaskStatus.ts` 暴露「角色 → 合法边」文本；`MoveTask` 非法转移报错含角色与合法边；`TaskMoveTool` 加 `acceptance` 参数并接线 `amendTaskAcceptanceIfRequested`（无 `to` 时仅修订）。 | 新增 `tests/task-move-role.test.ts` 全绿：legacy 边推父卡报错含「父卡」与合法边；`task_move(acceptance=…)` 后台账 `task.acceptance` 已更新（不接线必红）。 |
| t6 | 超时归位：投递/查询类工具不再挂交互式长超时 | implement | backend | t2, t3, t4 | `AdvanceTool`/`TaskExecuteTool`/`RunStatusTool`/`TaskStatusTool` 的 `timeoutMs` 改用 `LIMITS.timeoutWriteMs`/`timeoutReadMs`。 | `grep -rn "timeoutInteractiveMs" src/tools/{AdvanceTool,TaskExecuteTool,RunStatusTool,TaskStatusTool}` 无命中；相关测试仍绿。 |
| t7 | 门禁固化：声明与行为不一致由测试拦住 | test | backend | t2, t3, t4, t5, t6 | `tools-schema.test.ts` 构造全部已注册工具；`output-contract.test.ts` 补 TaskTreeTool 响应源映射与全工具扫描；新增参数 DSL 形状检测与故障注入用例。 | `vitest run tests/output-contract.test.ts tests/tools-schema.test.ts` 全绿；故障注入（临时给某工具加未声明返回键）在该测试内被验证为变红。 |
| t8 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步 | test | fullstack | t7 | 回归既有链路（advance-chain / run-status-tool / task-transition-guard / decompose-tools）；确认 task_execute 别名行为一致、旧键兼容；同步 `reqboard-implement-chain-flow.md` 工具面章节。 | `vitest run packages/web/dsh-pmboard/tests/advance-chain.test.ts tests/run-status-tool.test.ts tests/task-transition-guard.test.ts` 除预存在红外全绿；文档 grep 到新增工具面说明。 |

## §2.1 需求条款 → 任务卡覆盖对照

| 需求条款 | 覆盖内容 | 接收任务 |
|---|---|---|
| FR-1 | 链入口收口、参数与 autoRun 副作用显式、别名真委托 | t1, t2, t8 |
| FR-2 | task_run 返回体与 schema 逐键对齐 | t1, t7 |
| FR-3 | 新增只读父子结构视图 task_tree | t1, t3 |
| FR-4 | task_status 改用台账数据源并走端口 | t1, t4 |
| FR-5 | task_move 角色感知报错 + acceptance 修订接线 | t5 |
| FR-6 | 任务/链级工具超时归位 | t6 |
| FR-7 | 契约门禁固化（全工具） | t7, t8 |

## §3 验收总口径（人工可见）

1. `reqboard_task_tree(parent_id=…)` 一次看清 4 张子卡各到哪、是否跑过；
2. `reqboard_task_run(task_id=…)` 返回 `job_id/run_id` 齐全，描述写明会开 autoRun；
3. 用 legacy 边推父卡 → 报错直接说明「这是父卡，合法边是 todo→in_progress→done」；
4. `task_move(task_id, acceptance="命令：… → 看到 …")` 当场改掉不可执行的验收标准。

命令与预期见 `design/test-cases.md`；证据在实施节点写 `test-evidence.md`。
