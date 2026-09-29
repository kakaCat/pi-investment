# 子卡实施段改走 DSH 原生 Agent Teams（FR-11 路线 A）

> 起因：REQ-260926140539-457b 的 **FR-11「基于 DSH Agent Teams 的并行任务执行（零实现成本）」**
> 从未落地——代码实际走的是自研 `deps.jobs` + `driveChain` + workflow `agent()`，且 `deps.jobs` 始终未装配。
> 2026-09-27 用户裁定：**按 FR-11 原样补实现**，并借此消掉子卡凭证门的结构性误杀（D17）。
>
> 署名：investor / w-b71bb246　状态：**契约已落、改造进行中**

## 1. 为什么路线 A 可行（可行性已核实）

宿主把 Agent Teams 暴露为 **cordis 服务** `ctx.agentTeams`（`@deepseek-ai/dsh-experimental-agent-team` 的 `TeamService`），
插件可直接调用——不是只能模型侧调工具。API 与 FR-11 逐条对得上：

| FR-11 要求 | TeamService 方法 |
|---|---|
| 共享任务板 `team_task` | `createTask` / `listTasks` / `getTask` |
| 原生 DAG `blocked_by` | `CreateTeamTaskRequest.blockedBy` |
| 事件驱动 `wait_agent` | `waitForChange(caller, timeoutMs, signal)` |
| 持久化 Worker `spawn_teammate` | `spawnTeammate(caller, request)` |
| CAS `expected_revision` | `updateTask(caller, {taskId, expectedRevision, action})` |
| 自动负载均衡（Worker 自 claim） | Worker 侧 `listTasks` → `updateTask(claim)` |
| Lead 介入 | `interrupt` / `sendMessage` |

**关键约束**：每个方法都要 `caller: Agent`（live 句柄作 authority credential）。链上正好有
`input.exec.agent`（D14 修复后 `agent-handle.ts` 可按绑定窗口兜底解析），所以不缺句柄。

**真实类型（已读 `lib/types/*.d.ts` 核实，不靠记忆）**：
- `SpawnTeammateRequest.prompt` 是 **`ContentBlock[]`**，不是字符串；`provider` 缺省 `'spawn'`（fresh）/ `'fork'`；
- `spawnTeammate` / `sendMessage` 的 `signal` **必填**；
- `TeamTaskAction = claim | release | edit | set_dependencies | complete | reopen | reassign | delete`。

## 2. 现状 vs 路线 A

| 维度 | 现状（自研） | 路线 A（FR-11 原生） |
|---|---|---|
| 子卡执行 | `workflow.start(script)` → 一次性 child subagent | `spawnTeammate` → **持久 Worker** |
| DAG | 自研 `dependsOn` + `selectAdvanceEvent` 算 ready | `blockedBy`，**DSH 自动算 ready / 解锁** |
| 调度 | `driveChain` 同步循环 ≤20 步（jobs 未装配时的兼容路径） | `waitForChange` **事件驱动，零轮询** |
| 并发 | 串行挑卡 | 多 Worker **自 claim**，天然负载均衡 |
| 冲突 | 台账 version | `expected_revision` **CAS** |
| 观测 | ❌ 跨会话不可见 → 只能靠 mtime 推断（**D17 土壤**） | ✅ Lead 可 `listMembers`/`listTasks`/`waitForChange` |

## 3. 已落契约（本次提交）

- `src/application/ports.ts` 新增 **`AgentTeamsPort`**（+ `TeamTaskViewLike` / `TeamMemberViewLike` /
  `SpawnWorkerInput` / `TeamTaskCreateInput` / `TeamTaskUpdateInput`）——application 层不 import `@deepseek-ai/*`，
  `caller` 用 `unknown` 透传，与 `WorkflowStartInput.parent` 同款。
- `src/adapters/AgentTeamsAdapter.ts`（新）——桥接 `ctx.agentTeams`：明文 prompt → `ContentBlock[]`、
  必填 signal 兜底、服务缺失时 `available()=false` 且调用抛 `DSH_TEAMS_UNAVAILABLE`（不静默成功）。

装配（下一步）：仿 `workflowEngineSvc`（`src/index.ts:208-217`）注入 `['agentTeams']`，把
`new AgentTeamsAdapter(() => teamsSvc)` 挂进 `UseCaseDeps`，与 `workflow` 并存（团队优先、workflow 兜底）。

## 4. 与 D17 的关系（为什么路线 A 能同时修 bug）

D17 的根因是 `executeSubtask` **看不见**子代理过程（子代理在独立上下文，历史不回传），
只能事后用「文件 mtime ≥ 某时间戳」推断"干没干活"。而**时间戳选谁都是错的**：
选本次 run 起点 → 杀重跑；选 `claimedAt` → 每轮重写会漂；放宽窗口 → 变弱。

路线 A 下 Lead **直接可观测**（任务板状态 + 成员状态 + `waitForChange`），
"干没干活"由 **任务卡 complete（含 CAS）/ Worker 产出**表达，**不再需要 mtime 推断**。
即：**凭证门从"推断"退回"事实"**。

> 但兼容路径仍在（`available()=false` 或旧台账），所以 D17 的 L1+L2 修复**不撤销**：
> L1 基准单调化（`min(requirement.createdAt, parent.createdAt, task.createdAt)`）、
> L2 证据形态分流（结论族 review/test 不强制 diff）。两条由 teammate `gate-fix` 并行落地。

## 4.1 步骤 4 的硬约束（2026-09-27 实测发现，先记后写）

读 `TeamTaskView` 全字段：`{ id, revision, subject, description, status, blockadingBy?, writeScopes,
ownerName?, ready, writeScopeWarnings }`——**任务板只承载"状态"，不承载"结果"**：
没有 filesChanged / 产出字段。而 `TeamService` 的邮件面只有 `sendMessage`（发送），
**没有可查询的收件箱 API**（消息投递进目标会话，插件读不到）。

因此**不能用"读任务板 → 生成 lastReport"**（我最初的草稿是错的）。可行设计只有一条：

> **Worker 自己写台账，链只等"完成"信号。**
> 1. 链为每张子卡建一张 team task（subject/description/writeScopes）；
> 2. Worker（agent，同 profile，**带 reqboard 工具**）循环：`listTasks` → `updateTask(claim)`
>    → 干活 → **调 `reqboard_task_report(task_id, …)`**（写台账 `lastReport`）→ `updateTask(complete)`；
> 3. 链 `waitForChange` 等到该 team task `completed` → 直接跑既有 `assertDoneEvidence`
>    （此时 `lastReport` 已由 Worker 写好）；
> 4. 需要持久映射：**team task id ↔ 子卡 id**（落台账 `task.teamTaskId`），否则链无法把"完成了"对回哪张卡。

**推论（对 D17 的意义）**：路线 A 下 `lastReport` 的作者从"链按 workflow 产出写"变成"Worker 直接写"，
凭证门面对的证据形态更接近"事实"。但**兼容路径仍需要 L1+L2**（system 驱动 / 服务缺失时）。

## 5. 落地步骤

1. ✅ 契约：`AgentTeamsPort` + `AgentTeamsAdapter`
2. ⬜ **gate-fix 切片**：L1 + L2（`subtask-evidence.ts` / `support.ts` / `SubtaskTemplate.ts` + 测试）
3. ⬜ 装配：`index.ts` 注入 `agentTeams`，`UseCaseDeps` 增 `teams?`
4. ✅ `executeSubtask` 团队分支（2026-09-27 落）：`SubtaskTeamRun.runSubtaskViaTeam`（新）
   + `internal/team-dispatch.ts`（新）+ `ExecuteTask` **12 行插入**——团队可用且 caller 是 live agent 时，
   建/复用 team task（description **必带台账子卡 id**）→ `ensureWorker` 幂等起 Worker → `awaitTeamTask`
   事件驱动等 completed → 读回台账 `lastReport` 合成 workflow 同款产出形状 → **下游逐字复用**
   （解析/跨卡/落账/凭证门一行没改）。台账 `TaskRecord.teamTaskId` 记住映射。
   实证：`tests/execute-subtask-team.test.ts` 4 例（团队走通 / available()=false 退回 / 无 caller 退回 /
   建任务抛错不静默成功）
5. ✅ 原生 DAG（2026-09-27 落，**未动 AdvanceChain**）：`ensureParentTeamTasks` 在派第一张卡时**一次性建好本队全部未收口子卡**的 team task，
   `blockedBy` 串成链 → `TeamService` **自动算 ready**（依赖未完成 → ready=false）→ Worker 自 claim ready 卡。
   已 `done`/`canceled` 的卡不再放回板上（避免收口过的活被重认领）；落账与凭证门仍留在链里（安全）。
   实证：`tests/execute-subtask-team.test.ts` 新增「全队 DAG」例（review/test 两张、blockedBy=[tt-1]、映射落台账）
6. ⬜ 验证：既有 `execute-task` / `advance-chain` / `task-run-contract` 不回归 + 新增团队路径用例
7. ⬜ 同批纠正 REQ-260926140539-457b 的 `verification.md` 错误归因（把"受阻于宿主能力 deps.jobs 未装配"
   改为"被自研机制替换且未接通；路线 A 已补实现"）

## 6. 风险与边界

- `ctx.agentTeams` 是 **experimental**（包名 `dsh-experimental-agent-team`）——插件配置未启用时 `available()=false`，
  必须保留兼容路径，不能假设它一定在。
- 团队是 **per top-level Session 的隐式 Team**（`TeamId` = 根 Session），跨窗口/跨需求是否会串台需实测。
- 不改：父卡三态、子卡三项证据口径、懒展开时机、需求级状态机（沿用既有边界）。

## 7. 团队边界：一个父卡 = 一个团队（2026-09-27 用户裁定）

原生 `TeamService` 的 `TeamId` = **根 Session**（"identifies the implicit team rooted at one top-level
Session"）——一个会话只有一个隐式团队，"父卡级团队"在原生层落不了。故落成**逻辑分区**：

| 组成 | 实现 |
|---|---|
| 队边界 | team task 的 description **首段** = `[reqboard:parent=<父卡id>]`（`parentMarker()`） |
| 队的执行者 | 每个父卡一个 Worker，名字 `reqboard-<父卡id>`（名字即幂等键） |
| 隔离 | Worker 循环**第 0 步**：只认领 description 带**本队标记**的任务，别的父卡的不碰（`belongsToParent()`） |

**这条裁定修掉了一个真缺陷**：步骤 4 初版 Worker 循环写的是"挑 pending 且 ready 的任务"，**没按父卡过滤**
→ N 个父卡 N 个 Worker 会互相抢活（同一个隐式团队 = 同一块任务板）。已钉死并补用例。
