# REQ-260927144541-0481: 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

> **起因（用户原话）**：「你再梳理一下控制父卡的工具和子卡的工具，看看工具如何优化」→「立项开始优化问题」。
>
> **G1 反馈（2026-09-27）**：用户问「任务和整个需求工具可以分开吗」——本版据此**把范围收口到任务/链侧**，
> 需求级工具不再混进本需求（见「工具分层与边界」）。

## 工具分层与边界（回答「任务和需求工具能不能分开」）

**能分开，且命名已分两族**；本需求**只改任务/链侧**。

| 族 | 工具 | 操作对象 | 本需求范围 |
|---|---|---|---|
| **任务/链级** | `reqboard_task_run` / `task_execute` / `run_status` / `task_status` / `task_move` / `task_report`（+ 拟新增 `task_tree`） | 任务（t-xxxxxx）/ 链 | ✅ 范围内 |
| **需求级** | `create` / `capture` / `status` / `submit` / `move` / `ask_confirm` / `confirm_receipt` / `accept_sheet` / `note_interruption` / `clear_pause` / `decompose` | 需求（REQ-xxxxxx） | ❌ 范围外（另立项） |

**4 处必须耦合（拆不掉，属有意设计，不属"混乱"）**：

1. **窗口绑定校验**：任务/链工具靠 `openRequirementsFor(windowKey)` 确认"这些卡属于我绑定的需求"（`AdvanceTool.ts:58-61`）——拆掉＝越权可推进别人的卡；
2. **`decompose` 是桥**：需求级工具亲手产生任务卡（批准计划→落父卡）；
3. **停手守卫是跨层拦截**：需求级确认门挂起时，任务级写路径被 `assertNoPendingConfirm` 拒（`TaskMoveTool.ts:42`）——有意耦合；
4. **需求级副作用**：`task_run` 写 `req.autoRun`，链尾 rollup 改 `req.status`——任务推进天然改需求状态。

> 结论：**能分层，但入口与守卫必须保留**。本需求把任务/链侧修干净、可验收；需求级工具的同款问题（如
> `clear_pause` 参数旧式写法）**不在本需求范围**，另立项处理。

## 现状与根因（证据）

> 全部结论来自读码与实跑，逐条带 `文件:行`。父/子卡机制背景见
> [reqboard-implement-chain-flow.md](../../../docs/architecture/reqboard-implement-chain-flow.md)。
> **P7 已移出范围**（需求级工具），列在表内只为保留诊断证据。

| # | 问题 | 证据 | 范围 |
|---|---|---|---|
| P1 | `task_run` 的参数是父卡 id，实际推进**整个需求**（传同需求任意卡等效） | `AdvanceTool.ts:52-72` | ✅ |
| P2 | `task_run` 实际返回 `job_id/run_id/running/requirement_id/status`，`output.schema` 未声明；声明的 `subtask_executed/blocked/stopped` 又不返回 | `AdvanceTool.ts:36-46` vs `93-104` | ✅ |
| P3 | `task_run` 隐式写 `autoRun=true`，工具描述未写 | `AdvanceTool.ts:62-70`、`prompt.ts` | ✅ |
| P4 | `task_execute` 自称"兼容别名"，但不写 autoRun、不返回 `run_id` | `TaskExecuteTool.ts:46-52` | ✅ |
| P5 | `task_status` 读的 `## Workflow` 段落**全仓无写入方** | `grep "## Workflow" src` 只命中自身 `TaskStatusTool.ts:38/47` | ✅ |
| P6 | `task_status` 绕过端口直连 `fs.readFile`（相对 cwd） | `TaskStatusTool.ts:36` | ✅ |
| P7 | `clear_pause` 是全仓唯一旧式 `parameters: { schema: {...} }` | `ClearPauseTool.ts:17` | ❌ **范围外（另有需求级工具治理）** |
| P8 | **没有父子结构视图工具**：`status` 需求级、`task_status` 单卡级 | 只有 `run_status.currentSubtaskId/nextReady` | ✅ |
| P9 | `task_move` 角色不透明；`acceptance` 修订通道未接线 | `MoveTask.ts:45-48`；`AmendTaskAcceptance.ts` 无调用点 | ✅ |
| P10 | 投递式/查询式工具用 `timeoutInteractiveMs`（1h 交互超时） | `AdvanceTool.ts:50`、`TaskExecuteTool.ts:41`、`RunStatusTool.ts:66` | ✅ |

## 边界

### 做什么

1. **链入口收口**：`reqboard_task_run` 成为唯一链入口，参数语义与 `autoRun` 副作用显式化；
   `reqboard_task_execute` 改为**真委托**（同返回体、同副作用）并标 deprecated。
2. **契约对齐**：`task_run` 返回体与 `output.schema` 一致。
3. **父子结构可查**：新增只读工具 `reqboard_task_tree`。
4. **修死数据源**：`task_status` 改读台账 `lastRun/lastReport` 并走端口。
5. **角色感知与修订接线**：`task_move` 报错带角色与合法边；`acceptance` 参数真正落库并同步卡文档。
6. **超时归位**：任务/链级投递与查询工具改用非交互超时。
7. **门禁固化**（横切）：全工具"声明键 ⊇ 实际 return 键" + 参数 DSL 形状 + 全工具 schema 冒烟。

### 不做什么

1. **不改需求级工具**（`clear_pause` 等）——已按 G1 反馈移出范围，另立项；本需求不碰 `create/submit/move/
   ask_confirm/accept_sheet/clear_pause/decompose` 的行为。
2. **不改父/子卡的状态机语义与凭证门口径**（父卡三态、子卡三项证据、懒展开时机不动）——只让工具面如实表达。
3. **不改业务编排**（`advanceRequirement` / `selectAdvanceEvent` / `expandSubtasks` 判定逻辑不动）。
4. **不动看板 HTTP 路由与客户端**（除 `task_tree` 必要时在工具导出面登记）。
5. **不修其它窗口未提交改动引起的既存红**（`ClearPause/RunStatus/TaskMove` 的 output-contract 红属需求级/他线；
   本需求只负责 `defineAdvanceTool` 那条）。

## 产品定义

### 一句话目标

**让"父卡管交付、子卡管执行"这件事在工具面上看得见、说得清、查得到**——调用方不必读源码就知道
自己在推进哪条链、这张卡是父卡还是子卡、还差哪几张。

### 核心价值

1. **可查**：一条命令看清父子链与每张子卡的阶段/状态/run 结果（消除"混乱"）。
2. **可预期**：工具的参数、返回、副作用与描述一致（不再"传 A 跑 B""悄悄开链"）。
3. **可自证**：契约脱节与旧式 schema 由门禁拦住，不靠人记得。

## 用户与角色

| 角色 | 谁 | 在本需求里做什么 |
|---|---|---|
| 窗口 agent | 跑 reqboard 工具的会话 | 用 `task_run` 起链、用 `task_tree` 看结构、用 `task_move`/`task_report` 推进与举证 |
| 使用看板的人 | 项目操作者 | 在看板看到（并信任）与工具一致的父子结构与进度 |
| 维护者 | 改 dsh-pmboard 的开发者 | 依赖"工具声明 = 工具行为"这条不变量；新增工具时有门禁兜底 |

## 功能点

- **FR-1: 实施链收口为唯一入口，参数与副作用显式**

  `reqboard_task_run` 成为唯一链入口：参数支持 `task_id`（父卡，用于绑定与目标校验）或 `requirement_id`，
  语义写明"推进**该需求**当前 ready 事件"；`autoRun=true` 的副作用写进工具描述。`reqboard_task_execute`
  改为**真委托**（复用同一实现与返回体）并标 deprecated。
  判定：`TaskExecuteTool.ts` 无独立实现分支（逐行委托）；`ADVANCE_PROMPT` 含「开启 autoRun」字样。

- **FR-2: `task_run` 返回体与 `output.schema` 逐键对齐**

  声明 `job_id/run_id/running/requirement_id/status`，删除不再返回的 `subtask_executed/blocked/stopped`。
  判定：`vitest run tests/output-contract.test.ts` 中 `defineAdvanceTool` 用例绿。

- **FR-3: 新增只读父子结构视图工具 `reqboard_task_tree`**

  入参 `parent_id?` / `requirement_id?`（后者缺省取本窗口绑定需求）；返回父卡与其子卡链
  （每张含 `id/title/stageKind/status/dependsOn/attempt/lastRun.ok/lastReport 摘要/卡文档路径`），
  顺序按链序；无子卡时返回空数组并给 note。只读、无副作用、只读本窗口绑定需求。
  判定：对含子卡的父卡调用 → 全部子卡且顺序正确；对无子卡的父卡 → 空数组 + note。

- **FR-4: `task_status` 改用台账数据源并走端口**

  删除 `## Workflow` 解析与直连 `fs`；改读 `task.lastRun`/`task.lastReport`，经 `deps.repo`（必要时 `deps.docs`）
  端口；`workflow` 键保留但内容换成真实 run 摘要。
  判定：`grep -rn "## Workflow" packages/web/dsh-pmboard/src` 无输出；对跑过链的子卡调用能读到 run 结果。

- **FR-5: `task_move` 角色感知报错 + `acceptance` 修订接线**

  非法转移报错须含**当前角色**（父卡/子卡/legacy）与**合法边**；`acceptance` 经 `amendTaskAcceptanceIfRequested`
  真正落库并同步卡文档（无 `to` 时=仅修订不改状态）。
  判定：用 legacy 边推父卡 → 报错含「父卡」与合法边；`task_move(task_id, acceptance=…)` 后台账 `task.acceptance`
  已更新且卡文档「得到什么结果」同步。

- **FR-6: 任务/链级工具超时归位**

  `task_run`/`task_execute`（投递式）与 `run_status`/`task_status`（查询式）不得用 `timeoutInteractiveMs`。
  判定：`grep -rn "timeoutInteractiveMs" src/tools` 在任务/链级工具上无命中（弹框类不在本需求范围，允许保留）。

- **FR-7: 工具契约门禁固化（横切，全工具）**

  ① 全工具 `output.schema` 声明键 ⊇ 实际 `return` 键；② `parameters` 必须是 DSL 形状；③ `tools-schema`
  冒烟构造**全部**工具（当前 17 个）而非 4 个。
  判定：`vitest run tests/output-contract.test.ts tests/tools-schema.test.ts` 全绿；故障注入——临时给某工具加一个
  未声明的返回键，门禁必须变红。

## 决策点（需人工门裁决）

| # | 问题 | 选项 | 建议 |
|---|---|---|---|
| D-1 | `reqboard_task_execute` 如何处理 | A 保留为真委托并标 deprecated ／ B 直接删除 | **A**：删除会让存量调用方硬断 |
| D-2 | `task_tree` 返回子卡 `lastReport` 粒度 | A 只给摘要 + doc_path ／ B 给全量 | **A**：避免大返回 |
| D-3 | `task_status` 的 `workflow` 键 | A 保留键、内容换真实 run 摘要 ／ B 删键 | **A**：键是既有消费者契约 |
| D-4 | 需求级工具（clear_pause 等） | A 另开一条 chore ／ B 并入既有需求级治理 | **A**（已按 G1 反馈移出本需求） |

## 验收标准

### 可执行判定命令

```bash
cd /Users/yunpeng/pi-investment/agent-dh
# FR-2 / FR-7：契约与门禁
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts

# FR-4：死数据源清零
grep -rn "## Workflow" packages/web/dsh-pmboard/src ; echo "exit=$?（应非 0）"

# FR-6：任务/链级工具超时归位
grep -rn "timeoutInteractiveMs" packages/web/dsh-pmboard/src/tools/AdvanceTool packages/web/dsh-pmboard/src/tools/TaskExecuteTool packages/web/dsh-pmboard/src/tools/RunStatusTool packages/web/dsh-pmboard/src/tools/TaskStatusTool ; echo "exit=$?（应非 0）"
```

### 端到端判定（人工可见）

在绑定需求下跑一次链后：
1. `reqboard_task_tree(parent_id=…)` → 一次看清 4 张子卡各到哪；
2. `reqboard_task_run(task_id=…)` → 返回值里 `job_id/run_id` 齐全，且描述已写明会开 autoRun；
3. 用 legacy 边推父卡 → 报错直接说明"这是父卡，合法边是 todo→in_progress→done"。

## 参考

- 实施链流程图：[reqboard-implement-chain-flow.md](../../../docs/architecture/reqboard-implement-chain-flow.md)
- 任务状态机：[TaskStatus.ts](../../../packages/web/dsh-pmboard/src/domain/task/TaskStatus.ts)、父/子卡角色：[MoveTask.ts](../../../packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts)
- 子卡模板：[SubtaskTemplate.ts](../../../packages/web/dsh-pmboard/src/domain/task/SubtaskTemplate.ts)、子卡凭证：[subtask-evidence.ts](../../../packages/web/dsh-pmboard/src/application/internal/subtask-evidence.ts)
- 输出契约门禁：[output-contract.test.ts](../../../packages/web/dsh-pmboard/tests/output-contract.test.ts)

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1、t2、t8 |
| FR-2 | ✅ 已接收 | t1、t7 |
| FR-3 | ✅ 已接收 | t1、t3 |
| FR-4 | ✅ 已接收 | t1、t4 |
| FR-5 | ✅ 已接收 | t5 |
| FR-6 | ✅ 已接收 | t6 |
| FR-7 | ✅ 已接收 | t8、t7 |

> 无未接收条款（7 条全部有落点）。

<!-- reqboard:marks:end -->
