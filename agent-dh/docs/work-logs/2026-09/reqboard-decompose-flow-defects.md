---
id: reqboard-decompose-flow-defects
title: 拆分（decompose）节点流程缺陷清单与修复方案
summary: 拆分流程 6 条缺陷的实测证据、根因定位与逐条修法——需求批准后不落库、无守卫、恢复路径被堵、返回体契约不合法、RTM 不刷新。
type: worklog
status: living
updated: 2026-09-27
owners: [w-9f2c6c84]
tags: [reqboard, decompose, rtm, known-issues, defects]
---

# 拆分（decompose）节点流程缺陷清单与修复方案

**发现时间**：2026-09-27 · **发现场景**：REQ-202609262349-1518 在 `implementing` 停了数日、
台账任务数 0、DAG/泳道/实施覆盖度全空，排查后定位如下 6 条。
**状态：全部未修**（本文档只做诊断与方案，代码未改动）。

**共同根因**：**"落库"被排到了"批准"之后**。批准动作只推进状态，把落库委托给一个
**可能根本不存在监听者**的事件机制；此后所有依赖"台账有任务"的功能（DAG、泳道、
实施覆盖度、覆盖度门禁）全部落空，且**没有一处会报错**。

---

## D1 · 批准计划不落库（硬编码 0 张卡）

- **症状**：需求进入 `implementing`，但台账该需求任务数 = 0。
- **证据**：`src/application/internal/confirm-settle.ts:232`
  ```ts
  const createdCount = 0 // 任务将由 Dive 续跑时创建
  ```
  同块注释亦自述："先落章 → 自动落库任务卡 → 自动进实施"，**但落库那步没有实现**。
- **影响**：DAG 层级 / 泳道 / 实施覆盖度全空；`reqboard_task_move`/`task_report` 无对象可用。
- **建议修法**：把落库移入批准动作内部（同步执行）：落章 → **调用 decompose 落库** → 进实施 → `autoRun=true`。
  Dive 只负责"开跑执行"，不再负责"落库"。
- **风险**：中——改的是批准主路径，需跑 `confirm-settle` / `plan-mode` / `auto-chain-approval` 相关测试回归。
- **验收**：批准一个带任务表的计划后，**同一请求返回时**台账该需求任务数 = 计划卡数；
  失败时**不得推进**到 implementing，且写失败留痕。

## D2 · 委托前提不成立 → 静默停滞、零告警

- **症状**：D1 的落库被"委托给 Dive"，但需求 `dive = null`，无人触发。
- **证据**：
  ```
  autoRun = True
  dive    = null          ← Dive 未启用
  失败评论数 = 0          ← 无任何失败留痕
  ```
  失败分支（`confirm-settle.ts:254-283`）**只在抛异常时触发**；"委托从未被触发"属静默停滞，
  既不写 `advance.pausedReason` 也不告警。
- **建议修法**：① 推进前检查是否存在可消费该事件的一方（Dive armed / 监听者），否则**拒绝推进**；
  ② 推进后若 N 秒内仍无任务，写 `advance.pausedReason` + 告警（失败响亮化）。
- **风险**：中。
- **验收**：构造 `dive=null` 的批准路径 → 必须停在 `decomposing` 或产生显式失败留痕；二选一皆可，但**不得静默**。

## D3 · 无守卫：允许"计划有任务、台账却 0 任务"进入实施

- **症状**：`decomposing → implementing` 转移不校验任务是否已落库。
- **证据**：状态时间线 00:08(decomposing) → 00:29(implementing)，同一时刻评论自曝
  「自动拆分 **0 张卡**」——**0 张卡本身就是红旗，却无代码对它做出反应**。
- **建议修法**：转移守卫加一条——目标态为 implementing 时，若计划有任务但台账无该需求任务 → 拒绝并给出修复指引。
- **风险**：低（新增前置校验）。
- **验收**：模拟"计划 14 卡 / 台账 0 任务"→ 转移被拒，错误信息含恢复指引。

## D4 · 系统推荐的恢复路径被条款门禁堵死

- **症状**：批准后未落库时，系统提示"手动调 `reqboard_decompose` 重试"，但**该调用被拒绝**。
- **证据**（实测报错）：
  ```
  reqboard_decompose 未执行：需求条款 FR-1..FR-9 —— 既没有被任何任务卡接收、
  也没有标「本轮不做」…（requirement_uncovered）
  ```
  根因：门禁 `assertClauseCoverageGate` 的双源（`rawTasks.requirement_refs` ∪
  `decomposition.md` 的任务表）**都拿不到 FR 引用**——已批准的计划卡里没有 `requirement_refs`。
- **当前绕过**（本需求即如此）：调用时**显式传 `tasks`**，key 与计划一致、并补 `requirement_refs`。
- **建议修法**：① 条款门禁放行"计划已批准且其 RTM/任务表含 FR 对照"的情形；
  或 ② 修正错误提示，给出**实际可用**的恢复命令（含传参示例）。
- **风险**：中（门禁放宽需谨慎，避免漏拦真缺条款）。
- **验收**：对一个"计划卡无 refs"的已批准计划，恢复路径**可用**（或提示与实际一致）。

## D5 · `reqboard_decompose` 返回体不合契约（成功却报错）★根因已定位

- **症状**：工具**执行成功**（任务确实落库），但调用方收到
  `tool "reqboard_decompose" returned invalid output: "value.task_coverage" must be an object`。
- **根因**（确切，一处契约不匹配）：
  ```ts
  // 声明的输出契约：src/tools/DecomposeTool/DecomposeTool.ts:45
  task_coverage: { type: 'object', additionalProperties: true }   // ← 对象
  // 实际返回：src/application/internal/rtm-integration.ts:11 / :53
  task_coverage: Array<{...}>                                     // ← 数组
  task_coverage: taskCoverage.map(tc => ({...}))                  // ← 返回数组
  ```
- **影响**：agent 会误判失败并**重试**，理论上有重复落库风险（现由"已有任务即拒绝"的幂等守卫兜住）。
- **建议修法**（二选一，需先定设计意图）：
  A. schema 改为 `{ type: 'array', items: {...} }`；或
  B. 返回值包成对象（如 `{ tasks: [...] }`）。
- **风险**：低（1 行）。
- **验收**：`reqboard_decompose` 成功返回时不再触发 schema 校验错误。

## D6 · `rtm-decomposing.yml` 只在批准计划时刷新

- **症状**：任务落库/状态变化后，实施覆盖度**不更新**，长期停在 0%。
- **证据**：`tools/reqboard/src/rtm/generator.ts` 的 `filesForTrigger`
  ```
  task:status / task:report → ['rtm-implementing.yml', 'rtm-implementing/<task>.yml']
  confirm:plan             → ['rtm-decomposing.yml', ...]   ← 唯一刷新点（一次性）
  ```
- **连带影响**：FR-7 要求"批准计划时校验实施覆盖度 100%"，但批准时通常无任务（D1）→
  `total=0` 走"不拦截"边界；此后又不刷新 → **该门禁双重失效**
  （`ConfirmArtifact.ts:91` 注释亦自曝此数据流限制）。
- **建议修法**：把 `rtm-decomposing.yml` 纳入 `task:status`/`task:report` 的刷新集合。
- **风险**：低。
- **验收**：任务落库后触发一次任务状态变更 → 实施覆盖度随之变化。

---

## 修复顺序建议（低风险先行）

1. **D5**（1 行契约）+ **D6**（刷新集合）——低风险，可立即做
2. **D3**（守卫）+ **D2**（响亮化）——中低风险，防再次静默停滞
3. **D1**（同步落库）——最根本，但需回归批准路径
4. **D4**（门禁/提示修正）——依赖 D1 落地后其紧迫性下降

## 与 REQ-202609262349-1518 的关系

- D1/D2/D3 的直接受害需求（该需求在 implementing 停了数日、零任务零告警）。
- 该需求的**恢复已完成**：补 `requirement_refs` 重新落库 → 14 卡在位，
  补 `decomposition.md §1 对照表` → design_to_tasks 40/40、实施覆盖度 100%。
- 本清单属**独立于该需求**的流程修复，建议**另立需求**实施。


---

## D7 · agent 侧任务流转工具缺失（影响面最大）

- **症状**：路由提示词/节点纪律要求「调 reqboard_task_move(to=in_progress) 取任务卡全文」，
  但该工具**不存在**，agent 无法推进任何任务状态。
- **证据**：
  1. src/tools/ 下**无 TaskMoveTool**；
  2. 实际注册的 15 个工具名中**既无 reqboard_task_move 也无 reqboard_move**；
  3. 但 tests/apply-wiring.test.ts 断言宿主应注册 **15 个工具且期望集合含这两个名字** →
     该测试**当前 4/4 失败**，即缺口的直接证据；
  4. 能力本身存在，但只在 HTTP 层：src/http/routers/tasks.ts:72 handleTaskMove ←
     src/http/routes.ts:235 POST .../task/move（看板 UI 走这条）。
- **影响**：**agent 驱动的任务流转全断**（开工 / 汇报后转 done / review·测试态推进）。
  本需求 14 张卡停在 todo 即其直接后果；全仓 465 个任务的 agent 侧流转同样受影响。
- **为何长期未暴露**：看板人工操作走 HTTP 路由仍可用，"人点得动"掩盖了"agent 调不动"；
  而失败的那条测试被淹没在 193 个基线失败里。
- **建议修法**（二选一，推荐 A）：
  - **A（推荐）**：新增 src/tools/TaskMoveTool/（+ 对应 reqboard_move），复用已有 handleTaskMove
    的校验逻辑（decompose-tools.test.ts:422 已有"reqboard_task_move 边界"测试可复用），
    注册后对齐 apply-wiring 的期望集合。
  - **B**：若产品意图是"状态流转只由人/看板操作"，则删掉提示词里对 reqboard_task_move 的指引，
    并同步修正 apply-wiring.test.ts 的期望集合。
  - **判断**：倾向 A——本仓流水线纪律（"任务开工/完成用 reqboard_task_move 推进"）与
    五道人工门的自动化设计都依赖 agent 能推进任务；选 B 等于放弃"agent 自主跑完任务链"。
- **风险**：中（新增工具 + 注册 + 需跑 apply-wiring/decompose-tools/tools-schema 三组测试并重启验证）。
- **验收**：agent 可调 reqboard_task_move 把任务从 todo 推到 in_progress/done；
  apply-wiring.test.ts 的工具集合断言通过。


---

## D8 · 任务级状态校验只在 HTTP 路由（需求级缺陷的同构另一半）

- **症状**：任务状态可被多处代码**直接赋值**而不经状态机校验，非法任务流转不会报错。
- **证据**（实测各写入点）：
  ```
  ExecuteTask.ts:225  t.status = 'in_progress'      ← 子卡链执行，无校验
  ExecuteTask.ts:260  t.status = 'done'             ← 无校验
  AdvanceChain.ts:138 parent.status = 'in_progress' ← 父卡链，无校验
  AdvanceChain.ts:171 parent.status = 'done'        ← 无校验
  failure-handling.ts:44 t.status = 'todo'          ← 失败回退，无校验
  http/routers/tasks.ts:81  assertTaskTransition(...) ← ★唯一校验点（看板按钮）
  ```
- **性质**：与已修的 **需求级**缺陷**同构**——当时 `transitionRequirement` 直接 `req.status = to` 无校验，
  已在收敛点补 `assertReqTransition`；**任务侧至今没有等价的收敛点**，校验只挂在看板 HTTP 路由上。
- **影响**：子卡链/父卡链的执行路径（`reqboard_task_execute` / `reqboard_task_run` / `reqboard_task_run` 链）
  可造出**非法任务流转**且零报错；看板点按钮反而比自动链更严格——校验强度与执行者错配。
- **建议修法**：抽一个**任务级收敛点**（如 `transitionTask(task, to, opts)`），内部调
  `assertTaskTransition(from, to, actor.kind)` + 记录状态事件；把 `ExecuteTask` / `AdvanceChain` /
  `failure-handling` / HTTP 路由四处统一改为经它流转（与 `transitionRequirement` 对称）。
  逃生舱（`allowIllegalTransition`）同样保留给迁移/回填。
- **风险**：中（改 4 处写入点 + 需跑 execute-task / advance-chain / failure-handling / tools-dispatch 回归）。
- **验收**：非法任务流转（如 `todo → done` 若不在表内、或越权 human-only 转移）被拒且状态不变；
  四处写入点全部经收敛点；新增单测锁定（对齐 `transition-guard.test.ts` 的 5 个用例形态）。

### 根治思路（D1–D8 的共同教训）

> **每个状态机都必须有唯一且会自校验的收敛点。**
> 需求侧已补（本轮交付）；任务侧仍缺（本卡）。此外"阶段推进不校验任务完整性"（D3）
> 是另一类缺口——**跨状态机的完整性约束**，需在推进守卫里一并表达。
