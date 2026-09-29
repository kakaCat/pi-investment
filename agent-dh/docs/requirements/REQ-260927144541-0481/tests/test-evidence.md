---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 测试证据（REQ-260927144541-0481）

> 执行时点：2026-09-27（本机 agent-dh 工作区）。命令均在 `/Users/yunpeng/pi-investment/agent-dh` 下执行，
> vitest 取仓库内 `node_modules/.bin/vitest`。每条都是**真实跑过的输出摘要**（非应然描述）。

## 一、逐功能点判定

| 功能点 | 命令 | 结果 |
|---|---|---|
| FR-2 / FR-7 契约与门禁 | `vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts` | **2 files / 66 tests 全绿**（开工前为 1 failed / 4 failed cases） |
| FR-1 链入口/别名 | `vitest run packages/web/dsh-pmboard/tests/task-run-contract.test.ts` | 6 tests 全绿（task_id 与 requirement_id 同形；别名真委托写 autoRun） |
| FR-3 父子结构 | `vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts` | 6 tests 全绿（4 子卡链序 / 无子卡 note / 跨窗口拒绝） |
| FR-4 台账数据源 | `vitest run packages/web/dsh-pmboard/tests/task-status-ledger.test.ts` | 3 tests 全绿（读 lastRun/lastReport；无 lastRun 不伪造） |
| FR-5 角色报错 + acceptance | `vitest run packages/web/dsh-pmboard/tests/task-move-role.test.ts` | 5 tests 全绿（报错含角色与合法边；修订落库并同步卡文档） |
| FR-4 死数据源清零 | `grep -rn "## Workflow" packages/web/dsh-pmboard/src` | **无输出** |
| FR-6 超时归位 | `grep -rn "timeoutInteractiveMs" packages/web/dsh-pmboard/src/tools/{AdvanceTool,TaskExecuteTool,RunStatusTool,TaskStatusTool}` | **0 命中**（该行时点早于 16:44；16:50 复测 AdvanceTool.ts:70 已回退为 `timeoutInteractiveMs`，见 **§4.4** 偏离登记——此行不再代表交付后状态） |

## 二、回归对比（防"修一处、坏三处"）

| 口径 | 开工基线 | 交付后 |
|---|---|---|
| 全量 `vitest run packages/web/dsh-pmboard/tests` | 29 files / 132 tests 失败 | **26 files / 124 tests 失败** |
| 新增失败文件 | — | **0（无新增红）** |
| 新转绿文件 | — | output-contract.test.ts、tools-dispatch.test.ts、dive-gate-prompt.test.ts |
| `tsc --noEmit -p packages/web/dsh-pmboard/tsconfig.json` | 114 个错误 | **114 个错误（零新增）** |
| 消息卫生棘轮（拼接式消息） | application 140→189、http 21→22（他线既存红） | application **189（未变）**、tools **47→29（下降）** |

> 残留红均为**其它窗口未提交改动**引起（acceptance-criteria / template-address / doc-sync / size-budget 等），
> 按需求边界第 5 条不在本需求范围；本需求只保证"不新增红、且自有的两个门禁文件全绿"。

## 三、门禁加固的故障注入（只测成功路径不算）

`output-contract.test.ts` 新增两条注入用例：给扫描器喂"带未声明返回键"的源码片段 → 差集必须非空；
给"嵌套对象的条件展开"（`...(cond ? { run: { ok } } : {})`）→ 必须扫出 `run`。原实现用
`/\{([^{}]*)\}/` 只认无花括号对象组，这类键会被整块漏掉（静默漏键 = 下一次线上 invalid output），现已修为平衡花括号扫描。

## 四、接口联调实测（integrate 节点，2026-09-27 16:50）

> 全部为**线上工具实调返回原文**（非应然描述）。时点：2026-09-27 16:50（agent-dh 本机，服务 PID 67100，
> 重启于 16:48:19，dist 构建 16:44:16）。调用窗口 = reqboard Worker `8ae828f6-441f-4b25-baa6-720853c4821f`，
> 该窗口**未绑定** REQ-260927144541-0481，故正例（I-4 读台账）与反例（I-1/I-3 跨窗口拒绝）天然分居两侧。
> 全部用例均走**无副作用路径**：错误分支在 autoRun 落账 / 投递之前返回，未触发起链。

### 4.1 请求样例 → 期望 → 实际

| # | 请求 | 期望（design/interfaces + test-cases） | 实际返回（原文摘） | 判定 |
|---|---|---|---|---|
| L1 | `task_status{task_id:"t-c42bc0"}` | I-4：success/status/progress + run/report/workflow | `success:true, status:"done", progress:100, run:{ok:true,stopReason:"completed",valueNonEmpty:true}, report:{completedCount:1,filesChangedCount:13}, workflow:{at,ok,stopReason,valueNonEmpty}` | ✅ 键集与 I-4 逐键一致 |
| L2 | `task_status{task_id:"t-zzzzzz"}` | 任务不存在 → success:false + error | `success:false, status:"not_found", progress:0, error:"任务不存在：t-zzzzzz"` | ✅ |
| L3 | `task_run{}` | TC-2 → `REQBOARD_NO_BOUND_REQ` | `success:false, status:"error", code:"REQBOARD_NO_BOUND_REQ"` | ✅ |
| L4 | `task_run{task_id:"t-3e3ebb"}` | TC-7 → `REQBOARD_NOT_BOUND_TO_WINDOW` | `success:false, task_id:"t-3e3ebb", requirement_id:"REQ-260927144541-0481", code:"REQBOARD_NOT_BOUND_TO_WINDOW"` | ✅ |
| L5 | `task_run{requirement_id:"REQ-…0481"}` | I-1 参数支持 requirement_id（须绑定） | `success:false, requirement_id:"REQ-260927144541-0481", code:"REQBOARD_NOT_BOUND_TO_WINDOW"` | ✅ 参数被消费 |
| L6 | `task_execute{task_id:"t-3e3ebb"}` | I-2 真委托 → 与 L4 **逐键相同** | 与 L4 完全同形（success/task_id/requirement_id/status/error/code） | ✅ 别名等价（非第二套实现） |
| L7 | `task_tree{}` | TC-6/I-3 缺省取本窗口绑定需求 | `success:false, requirement_id:"", parents:[], error:"REQBOARD_NO_BOUND_REQ：…请传 requirement_id"` | ✅ |
| L8 | `task_tree{parent_id:"t-3e3ebb"}` | I-3 只传 parent_id 且未绑定 | `success:false, parents:[], error:"REQBOARD_NO_BOUND_REQ：…"` | ✅ 跨窗口不返回空当成功 |
| L9 | `task_tree{requirement_id:"REQ-…0481"}` | TC-7 → `REQBOARD_NOT_BOUND_TO_WINDOW` | `success:false, requirement_id:"REQ-260927144541-0481", error:"REQBOARD_NOT_BOUND_TO_WINDOW：需求 … 不属于本窗口绑定的需求"` | ✅ |

### 4.2 联调结论

1. **I-1 返回体与 schema 对齐（已修复线上症状）**：L3–L5 的错误分支返回 `success/task_id/requirement_id/status/error/code`，
   全部在 `output.schema.properties` 内 → 绑定层**未**出现此前那种 `returned invalid output` 拒收回执（开工前 `subtask_executed/blocked/stopped` 声明与返回脱节的症状已消失）。
2. **I-2 别名等价**：L4 与 L6 同输入 → 逐键相同返回，证明 `reqboard_task_execute` 与 `reqboard_task_run` 同 factory（同参数/同返回/同 autoRun 副作用），不是各跑一套。
3. **I-3 只读 + 窗口绑定**：L7–L9 显示跨窗口/未绑定一律 `success:false` 且 `parents:[]`，不把「查不到」伪装成「空结构」。
4. **I-4 换源生效**：L1 的 `run/report/workflow` 均来自台账 `lastRun/lastReport`（`workflow` 键保留、内容换 run 摘要）；
   与本仓 `grep -rn "## Workflow" src` 无输出一致——不再依赖那个全仓无写入方的死段落。
5. **成功路径（I-1/I-3 正向）未在线上直调**：本 Worker 窗口未绑定该需求，调用 `task_run` 会命中跨窗口拒绝（L4），
   从绑定窗口直调会**真实起链**（写 autoRun + 投递后台任务），属不可逆副作用，故正向形状由契约测试覆盖：
   `task-run-contract.test.ts`(6) TC-1/TC-3、`task-tree.test.ts`(6) TC-5/TC-6 —— 本次 7 套 93 tests 全绿（见 4.3）。

### 4.3 回归复跑（本次联调时点）

`cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run` output-contract / tools-schema / contract-shapes /
tools-dispatch / task-run-contract / task-tree / task-status-ledger →
**Test Files 7 passed (7) / Tests 93 passed (93)，exit 0**（2026-09-27 16:50）。

### 4.4 遗留偏离（非本卡范围，交复核/人工裁决）

- **FR-6 / TC-12 未满足**：`src/tools/AdvanceTool/AdvanceTool.ts:70` 仍为 `timeoutMs: LIMITS.timeoutInteractiveMs`（3,600,000ms），
  而 TC-12 要求「任务/链级工具体 grep `timeoutInteractiveMs` 0 命中」；`TaskExecuteTool`（别名）继承同一值。
  `TaskStatusTool`/`TaskTreeTool` 已正确归位 `timeoutReadMs`。此项为 **D14/report3 已记录的待裁决冲突**
  （修 FR-6 用 30s 写档会掐断 `deps.jobs` 未装配时的同步兼容路径），故本卡只登记事实、不改动。
- `task_run` 的 `parent_status` 在 `task_id` 为空串时返回 `""`（L3）；契约允许 `string`，不作为缺陷，登记备查。

---

## 五、根因修复：链为什么反复失败、调用为什么反复被掐断（2026-09-27 17:35）

用户裁定：同一现象反复出现 = bug，查根因并修。结论与修复如下（每条带源或命令输出）。

### 5.1 主根因：JobsPort 从未装配 → 实施链退化为同步循环

- 证据①（代码）：`src/application/use-cases/AdvanceChain.ts:412` — `deps.jobs` 缺失时走**同步兼容路径**：
  `driveChain()` 在**调用方的工具调用栈里**跑完整条链，再返回 `dispatched:false`。
- 证据②（装配）：`src/index.ts` 的 `useCaseDeps` 原先无 `jobs` 字段；`adapters/DshJobsAdapter.ts` 只有
  `startJob/getJob`，**没有 `deps.jobs` 要求的 `start/get/available`** — 组合根即使想接也接不上。
  仓库三处注释把「JobsPort 未装配」当既成事实（`DecomposeTool.ts:5`、`http/routers/requirements.ts:410`、`index.ts:402`）。
- 后果 A（调用被反复掐断）：同步链一次跑数分钟（实测 `reqboard_task_run(t-3eebb)` 单次 >120s 超时；
  `t-acd60f` 一次 102s），且链绑定在**发起 turn 的 abort signal** 上 — turn 一中断，正在跑的子卡 workflow
  就地 `cancelled: workflow signal aborted`（advance-log 里 t-c42bc0 反复出现的那条）。
- 后果 B（谎报）：即便链推进成功，`dispatched:false` 也使工具回 `status=error / error=投递失败 / code=REQBOARD_DISPATCH_FAILED`。

### 5.2 次根因：凭证门的证据形态没有传达给干活的子代理

- 证据：`t-acd60f` 的 integrate 子卡（`t-4b44d7`）连续 2 次被判
  `子卡凭证不过：阶段 integrate 属写入族，汇报未给出改动文件`（`advance.history` 计数 `integrate写入族 = 2`）。
  该卡 `lastReport.completed` 非空（线上实调 9 条请求/响应对齐）而 `filesChanged` 为空 — 它按验收模板
  （「接口联调通过：给出请求样例与期望响应」）交了一份**结论**，门却按 `STAGE_EVIDENCE_KIND.integrate = file` 要**落盘文件**；
  两者口径未在提示词里对齐 → 重跑必复现。
- 修法（**不动门**，守住 decomposition §1.3 边界）：`buildSubtaskPrompt` 把本阶段证据形态如实写进工作要求。

### 5.3 修复与验证

| # | 改动 | 文件 | 验证 |
|---|---|---|---|
| 1 | `DshJobsAdapter` 实现 `JobsPort` 形状（`start` 透传 owner + 把 run 翻译成 DSH 生产者钩子 / `get` 复用状态映射 / `available`） | `src/adapters/DshJobsAdapter.ts` | `tests/unit/dsh-jobs-adapter.test.ts` → 14 tests 全绿（新增 3 例） |
| 2 | 组合根惰性注入 `ctx.jobs` 装配 `useCaseDeps.jobs`（不可用则告警并保留同步兜底） | `src/index.ts` | `tests/apply-wiring.test.ts` → 4 tests 全绿（修前因 `isAvailable(undefined)` 抛错而 4 红） |
| 3 | 子卡提示词补「本阶段凭证形态」（写入族要落盘产出 / 结论族要判断） | `src/application/use-cases/ExecuteTask.ts` | `tests/execute-task.test.ts` → 19 tests 全绿（新增 1 例钉两族口径） |
| 4 | dist 重建并核验 | `dist/index.mjs`（1,205,279B，17:32） | 4 个新符号 grep 各命中 1；`[verify-client] OK` |

- 回归：`execute-task / subtask-contract / execute-subtask-team / advance-chain / task-run-contract / tools-schema /
  output-contract / apply-wiring` 十套 **156 tests 全绿**（2026-09-27 17:33）；`tsc --noEmit` 在改动文件上 **0 错误**。
- 基线对照：全包 `vitest run packages/web/dsh-pmboard` = **128 failed / 2205 passed**；其中 4 红是本次 `isAvailable` 空值回归（已修），
  余 124 与修复前基线一致（layer-boundary / size-budget / message-hygiene / decompose-tools 等来自其它窗口未提交改动，
  与改动文件无交集；`src/index.ts` 在 HEAD 即 449 行 > 尺寸门 400，属既存）。
- **未做**：`AdvanceTool.ts:70` 的 `timeoutInteractiveMs`（FR-6 / t-507969 范围）。JobsPort 装上后该长超时已无害（调用立即返回），
  但「归位到 `timeoutWriteMs`」仍归 t-507969。
- **生效条件**：dist 已重建，需重启 :13080 在运行实例生效（本次随 quick_restart 部署）。

### 5.4 第三根因：JobsPort 投递形状与 DSH 生产者契约错配（2026-09-27 17:42）

修复 5.1 之后，从**已绑定**窗口实调 `reqboard_task_run({task_id:"t-acd60f"})` 得到
`{success:false, status:"error", code:"REQBOARD_DISPATCH_FAILED", error:"投递失败：Cannot read properties of undefined (reading 'bind')"}`
——投递仍恒失败，只是失败点从「退化为同步路径」挪到了「真的调 ctx.jobs.start」。

**根因（契约错配，非业务逻辑）**：

1. 应用层端口 `JobStartSpec.run` 的形状是**执行函数** `(signal: AbortSignal) => Promise<void>`
   （`src/application/ports.ts:427`；AdvanceChain 按此传入 `async (signal) => driveChain(...)`，`AdvanceChain.ts:436`）。
2. DSH 宿主契约（`@deepseek-ai/dsh-jobs` 的 `JobStart`）要求 `run` 是**同步返回 JobHooks 的工厂**：
   `run(): { cancel(reason?): void; done: Promise<JobOutcome>; readOutput?(): string }`
   （`lib/types/types.d.ts:57-83`；`JobOutcome.status` 属于 completed/killed/failed，:26-33）。
3. 实现在 `dsh-jobs-local/lib/index.js`：:138 `const hooks = spec.run()`，:152 `cancel: hooks.cancel.bind(hooks)`。
   适配器此前把 async 执行函数**原样**当 run 传入 → `spec.run()` 返回 **Promise** → `hooks.cancel` 为 `undefined`
   → `undefined.bind(hooks)` 抛 TypeError。错误串不含 "jobs" 字样，故被映射成 `REQBOARD_DISPATCH_FAILED`
   （`AdvanceTool.ts:122`）而非 `DSH_JOBS_UNAVAILABLE`。

**为什么测试没拦住**：`tests/unit/dsh-jobs-adapter.test.ts` 的 mock 只断言 `ctx.jobs.start` 的
**参数被透传**（`run` 同一性），从不调用 `run()` —— 真实契约（run() 的返回形状）从未被执行。
这正是本仓已有教训「mock 与线上数据模型脱节 → 假通过」的又一实例。

**修法（只改适配层，应用层端口形状不动）**：`DshJobsAdapter` 新增 `toProducerHooks(run)`，把
`(signal) => Promise<void>` 翻译为同步返回钩子的工厂：内部建 `AbortController`，`cancel` 触发 abort（幂等），
`done` 结算为 `{status:'completed'}` 或 `{status:'failed', detail}`（**不得 reject**）；
`start` 与 legacy `startJob` 都走这条翻译。

**验证**：

| 口径 | 命令 | 结果 |
|---|---|---|
| 适配器（新增 3 条契约用例：run() 返回 hooks / 抛错结算 failed / cancel 幂等触发 AbortSignal） | `vitest run packages/web/dsh-pmboard/tests/unit/dsh-jobs-adapter.test.ts` | **16 tests 全绿** |
| 相关回归 | `vitest run` apply-wiring / advance-chain / task-run-contract | **3 套 18 tests 全绿**（与适配器合计 34） |
| 类型 | `tsc --noEmit -p tsconfig.json` | DshJobsAdapter 相关 **0 错误** |
| 产物 | `grep -c toProducerHooks dist/index.mjs` | **4**；dist 重建 17:42（1,206,490B），`[verify-client] OK` |

**生效条件**：dist 已重建，仍需重启 :13080 后才在运行实例生效；生效后再从绑定窗口实调 task_run 复核
`status=dispatched` 且 `job_id/run_id` 齐全（届时把实调原文补记入本节）。

**同批发现（另案，未改）**：`reqboard_run_status` 在**无 active run** 时返回 `snapshot.runId=null`，
而 `RunStatusTool.ts:50` 把它声明为 `type:'string'` → 工具绑定层以
`returned invalid output: "value.snapshot.runId" must be a string` 拒收（2026-09-27 17:39 实测）。
属「声明类型 vs 实际可为 null」的契约脱节，需 schema 层决策（声明可空 / 无 run 时不发该键），本卡只登记事实。

## 五、任务→测试覆盖（covers 标注 · 验收覆盖度门禁用）

> 口径：每张任务卡标注其交付内容由哪份测试文件覆盖（`covers: t-xxx`）。同一测试文件可覆盖多张卡（契约/门禁类天然横切）。
> 全部文件位于 `packages/web/dsh-pmboard/tests/`，命令：`cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run <文件>`。

- covers: t-3e3ebb — output-contract.test.ts / tools-schema.test.ts / task-run-contract.test.ts
- covers: t-c42bc0 — output-contract.test.ts / tools-schema.test.ts / task-run-contract.test.ts
- covers: t-91b37e — task-run-contract.test.ts / tools-schema.test.ts
- covers: t-52933e — output-contract.test.ts / task-tree.test.ts
- covers: t-2838a8 — output-contract.test.ts / tools-schema.test.ts / task-run-contract.test.ts
- covers: t-d50859 — advance-chain.test.ts / task-run-contract.test.ts / execute-subtask-team.test.ts
- covers: t-b079ef — task-run-contract.test.ts / advance-chain.test.ts
- covers: t-4ef7ab — task-run-contract.test.ts / team-dispatch.test.ts
- covers: t-226f18 — team-dispatch.test.ts / execute-subtask-team.test.ts
- covers: t-6fd3e4 — advance-chain.test.ts / task-run-contract.test.ts
- covers: t-acd60f — task-tree.test.ts
- covers: t-3f8bb3 — task-tree.test.ts
- covers: t-4b44d7 — task-tree.test.ts
- covers: t-f42b5a — task-tree.test.ts
- covers: t-ca640c — task-tree.test.ts / output-contract.test.ts / tools-schema.test.ts
- covers: t-039d31 — task-status-ledger.test.ts / task-status-integration.test.ts
- covers: t-2de564 — task-status-ledger.test.ts
- covers: t-e2ccda — task-status-integration.test.ts
- covers: t-ebe92d — task-status-ledger.test.ts / task-status-integration.test.ts
- covers: t-46d23f — task-status-ledger.test.ts / output-contract.test.ts / tools-schema.test.ts
- covers: t-ac97a2 — task-move-role.test.ts / amend-acceptance.test.ts / acceptance-executable.test.ts
- covers: t-c65b1a — task-move-role.test.ts / amend-acceptance.test.ts
- covers: t-061657 — task-move-role.test.ts / acceptance-executable.test.ts
- covers: t-c67876 — task-move-role.test.ts / task-move-snapshot.test.ts
- covers: t-008040 — task-move-role.test.ts / amend-acceptance.test.ts / output-contract.test.ts
- covers: t-507969 — timeout-routing-integration.test.ts / output-contract.test.ts
- covers: t-59916c — timeout-routing-integration.test.ts
- covers: t-d80c2b — timeout-routing-integration.test.ts
- covers: t-fc43f2 — timeout-routing-integration.test.ts / task-run-contract.test.ts
- covers: t-773fbf — timeout-routing-integration.test.ts / output-contract.test.ts / tools-schema.test.ts
- covers: t-5e64cd — tools-schema.test.ts / output-contract.test.ts / contract-shapes.test.ts
- covers: t-b02159 — tools-schema.test.ts / output-contract.test.ts
- covers: t-022248 — tools-schema.test.ts / contract-shapes.test.ts / tools-dispatch.test.ts
- covers: t-8ec036 — output-contract.test.ts / tools-schema.test.ts
- covers: t-5a4790 — tools-schema.test.ts / output-contract.test.ts
- covers: t-bd7439 — advance-chain.test.ts / run-status-tool.test.ts / task-transition-guard.test.ts
- covers: t-73e493 — advance-chain.test.ts / run-status-tool.test.ts
- covers: t-3b7673 — run-status-tool.test.ts / task-transition-guard.test.ts
- covers: t-bfe2a8 — advance-chain.test.ts / run-status-tool.test.ts
- covers: t-417698 — advance-chain.test.ts / run-status-tool.test.ts / task-transition-guard.test.ts



