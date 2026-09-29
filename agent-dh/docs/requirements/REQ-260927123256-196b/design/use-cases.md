---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
---

# 用户场景（REQ-260927123256-196b）

> 读者：工程 / agent。只承载需求文档放不下的多角色 / 多分支场景；功能点明细见 requirement.md。
> 角色：**人**（在弹框作答的看板操作者）、**窗口 agent**（调 `reqboard_*` 工具的会话）、**维护者**。

## 场景总览 <!-- serves: FR-1, FR-2, FR-3, FR-4 -->

| 场景 | 角色 | 触发 | 完成标志 | serves |
|---|---|---|---|---|
| UC-1 | 人 + 窗口 agent | 确认门发起，人不在 | agent 停住不动，不产出任何下游产物 | FR-1, FR-2 |
| UC-2 | 窗口 agent | 调用方执行预算有限 | 显式传 `inline_grace_ms` → 拿 ticket、后续取回执 | FR-3 |
| UC-3 | 窗口 agent + 人 | 阻塞等待被 deadline / 取消中止 | `reqboard_status` 查到挂起；人作答或重新发起后解除 | FR-4 |
| UC-4 | 人 | 弹框点「取消」 | 工具中性返回、节点未推进、无挂起残留 | FR-1 |
| UC-5 | 窗口 agent | 中止后想重试同一确认门 | 重新发起覆盖旧记录，弹框重现 | FR-4 |

## UC-1 确认门缺省阻塞（人不在，agent 就停住） <!-- serves: FR-1, FR-2 -->

- **用例角色**：人（作答方）+ 窗口 agent（等待方）
- **前置条件**：弹框通道可用；本窗口绑定进行中需求；目标产物尚未确认
- **交互流程**：
  1. 窗口 agent 调 `reqboard_ask_confirm(target=artifact, kind=design)`（**不传** `inline_grace_ms`）
  2. 工具登记 ticket 后 `await questions.ask(...)` → 弹框出现在界面，工具调用未返回，agent loop 停在这一步
  3. 人看到弹框 → 点「确认推进」→ 工具返回 `{confirmed:true, advanced:true}`，需求按闸门推进
- **异常流**：① 阻塞期间角色同回合的**并行**写工具调用 → 被 `REQBOARD_CONFIRM_PENDING` 拒绝且不写盘（见 UC-3/TC-6）；
  ② 人一直不答 → 工具在 `timeoutInteractiveMs`（1h）超时 → 转入 UC-3
- **后置条件**：登记记录被 `settle`，守卫放行；返回体不含 `pending`/`ticket`
- **完成标志**：FR-1 —— `ask` 永不 resolve 时，工具在观测窗内**仍未返回**（旧实现此时已返回 `pending:true`）

## UC-2 显式宽限逃生舱（调用方预算有限） <!-- serves: FR-3 -->

- **用例角色**：窗口 agent
- **前置条件**：`pendingConfirms` 已装配（生产组合根始终装配）；调用方执行预算（如 120s）短于可能等待时长
- **交互流程**：
  1. agent 显式调 `reqboard_ask_confirm(..., inline_grace_ms: 20000)`——**主动声明放弃阻塞**
  2. 20s 内作答 → 同步落章（返回体与旧语义逐字一致）
  3. 超 20s → 返回 `{success:true, confirmed:false, pending:true, ticket:'pc-…'}`，弹框留屏、后台继续等
  4. 人作答 → 后台落章 + 推进 + 唤醒窗口；agent 调 `reqboard_confirm_receipt(ticket)` 取回执
- **异常流**：① `inline_grace_ms` 为 0 / 负数 / 非数 → 拒绝 `REQBOARD_INVALID_INPUT`；
  ② 传了正数但非阻塞能力未装配 → 拒绝 `REQBOARD_NONBLOCK_UNAVAILABLE`（**不静默回落为阻塞**）
- **后置条件**：确认结果落台账；调用方回合不因等待而超时
- **完成标志**：FR-3 —— 传 `inline_grace_ms` 才有 `pending`；不传则不出现该键

## UC-3 阻塞被中止后仍可查、可续 <!-- serves: FR-4, FR-6 -->

- **用例角色**：窗口 agent + 人
- **前置条件**：一个缺省阻塞的确认门正在等待；调用方回合被 deadline 打断 / 用户中止 agent
- **交互流程**：
  1. `questions.ask` 以 `ASK_ABORTED`（或 `exec.signal.aborted`）拒绝
  2. 工具**不 settle** 该记录，改为 `markInterrupted`（写 `interruptedAt`）；返回
     `{success:false, pending:true, ticket, interrupted:true, note}`，`note` 含取回执与看板两条恢复路径
  3. agent 调 `reqboard_status` → `pending_confirms` 列出该 ticket（`interrupted:true` + `recovery`）
  4. 人走看板一键确认（写台账 `confirmedAt`）→ 下一次守卫判定发现「台账已落章」→ 自动放行
  5. 或 agent 重新发起 `reqboard_ask_confirm` → 旧记录被 settle 作废、新弹框重现
- **异常流**：① 人既不答也不确认 → 记录在 `(interruptedAt ?? createdAt) + 1h` 后过期，守卫自动放行；
  ② 台账里需求被删除 → 守卫按「未知目标」保守拦截（宁可拦不可放）
- **后置条件**：不出现「弹框被丢掉、既没落章也没留痕」的静默态
- **完成标志**：FR-4 —— 构造中止用例后 `reqboard_status` 能查到挂起记录，且写路径继续被拒

## UC-4 用户取消弹框 = 中性未作答 <!-- serves: FR-1, FR-6 -->

- **用例角色**：人
- **前置条件**：缺省阻塞等待中，弹框可见
- **交互流程**：
  1. 人点弹框「取消」→ 宿主以 `ASK_CANCELLED` 拒绝 `ask`
  2. 工具 `settle` 该记录后返回中性结论：`{success:false, confirmed:false, advanced:false, note:'用户未作答（取消/暂离）：节点未推进…'}`
  3. 返回体**无** `pending`/`ticket`；节点未推进；守卫放行
- **异常流**：取消后 agent 仍不得自行推进——需求状态与产物落章不变（`confirmedAt` 未写）
- **后置条件**：无挂起残留；稍后可重新发起确认
- **完成标志**：与需求「端到端判定」第 3 条一致（取消弹框 → 中性未作答、节点未推进、无下游产物）

## UC-5 重新发起 = 显式解除 <!-- serves: FR-4 -->

- **用例角色**：窗口 agent
- **前置条件**：本窗口存在一条未作答记录（阻塞中中止、或显式宽限后台等待中）
- **交互流程**：
  1. 新一次 `reqboard_ask_confirm` 开始前，先 `settle` 本窗口既有未作答记录为
     `{confirmed:false, advanced:false}`（作废）
  2. 登记新 ticket → 重新弹框 → 人作答 → 落章/推进
- **异常流**：旧记录已在台账落章（人已通过看板确认）→ 新调用可能命中「已确认产物早返回」，直接返回不再弹框
- **后置条件**：本窗口同一时刻只有一条权威挂起
- **完成标志**：`pendingForWindow` 始终只反映最新 ticket
