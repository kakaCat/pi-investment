# REQ-260927123256-196b: pm 确认弹框改为真正阻塞（与原生 ask_user_question 等待语义对齐）

> **现象（用户实测）**：`reqboard_ask_confirm` 的确认弹框出现在界面上，agent loop 却继续往下跑；
> 原生 `ask_user_question` 弹框出现时 loop 会停住、等作答。
>
> 本文给出**已定位的根因**（含代码行）、要达成什么、边界与可证伪验收。

## 现状与根因（证据）

两条路径**用的是同一条弹框通道**，差别只在**调用方等不等**：

`ctx.userQuestions.ask()` → `user-questions/request` waterfall → 客户端
`@deepseek-ai/dsh-client-ui-user-questions` 渲染（原生与 pm 共用）。

| 维度 | 原生 `ask_user_question` | pm `reqboard_ask_confirm` |
|---|---|---|
| 实现 | `@deepseek-ai/dsh-tool-ask-user/lib/index.js:96-111`：`await ctx.userQuestions.ask(...)`，**不设宽限** | `src/application/use-cases/AskConfirm.ts:154-157`：`raceAsk(ask, LIMITS.confirmInlineGraceMs)` 赛跑 |
| 宽限 | 无（等到作答 / 取消 / 中止） | 30s（`src/domain/limits.ts:41`：`confirmInlineGraceMs: 30_000`） |
| 超宽限行为 | ——（不存在） | `src/application/internal/pending-confirm.ts:78-121` `suspendConfirm`：登记内存 ticket（`PendingConfirmRegistry`）+ **立即返回** `{success:true, confirmed:false, advanced:false, pending:true, ticket}`；而 `ask` 的 promise **继续挂着**（`void ask.then(...)`）→ **弹框留在界面上、工具已返回、loop 已继续** |
| 作答后 | 工具正常返回 → loop 继续 | 后台 `settle` 落章/推进 + `deliver()` 唤醒窗口；agent 调 `reqboard_confirm_receipt(ticket)` 取回执 |

**设计动机（历史）**：避免"人不在 → 弹框把调用方回合/工具 deadline 打死"（REQ-2cd3 事故；
`timeoutInteractiveMs` 后来抬到 1h）。代价 = **loop 不停**。

**现状缓解**：挂起期间同窗口写路径已被代码级拒绝（`src/application/internal/support.ts:344`
`assertNoPendingConfirm`，接在 `reqboard_submit` / `reqboard_decompose` / `reqboard_move` /
`reqboard_task_move` 入口，REQ-260927100007-b8ba FR-9）——但 agent 仍在跑、仍在烧 token、
仍在做被拒的尝试，界面也看不出"agent 在等"。

**对照**：`reqboard_capture`（立项四问）与 `reqboard_accept_sheet`（验收）**没有**宽限赛跑，
仍是 `await` 阻塞（`src/application/use-cases/CaptureRequirement.ts:143`、`AcceptSheet.ts:66,161`）
——它们的表现与原生一致。

## 边界

### 做什么

1. **缺省阻塞**：`reqboard_ask_confirm` 不传 `inline_grace_ms` 时，工具一直等到**作答 / 取消 / 中止**
   才返回；删除"30s 到点即自动放行 loop"这一缺省行为。返回体恢复旧同步语义（`confirmed`/`advanced`/…，
   不再返回 `pending`/`ticket`）。
2. **例外显式化**：只当调用方**显式**传正数 `inline_grace_ms` 时，才启用非阻塞投递（保留
   `pending` + `ticket` + `reqboard_confirm_receipt` + 后台落章 + 唤醒窗口）。
3. **中止必须响亮**：阻塞期间若工具被调用方 deadline / 用户取消而中止，必须留下**可查的挂起记录**
   （ticket 可凭 `reqboard_status` / 回执路径找回），不得静默把这次确认丢掉。

### 不做什么

1. 不改 `reqboard_capture` / `reqboard_accept_sheet` 的阻塞语义（它们本就阻塞；若要统一口径另立需求）。
2. 不动 DSH 宿主与客户端的弹框通道（`@deepseek-ai/dsh-client-ui-user-questions`）与原生
   `ask_user_question` 语义——本需求只改 pm 插件侧的等待策略。
3. 不改 Dive 的投递路径（"一条人类消息 = 两轮 loop"是 `agent.followup` 直投纪律造成的，
   属 REQ-260927100007-b8ba FR-11，不在本需求范围内）。

## 产品定义

### 一句话目标

确认门弹框一旦出现，**人不作答，agent 就不得再往下走一步**——与原生 `ask_user_question` 的等待语义一致。

### 核心价值

1. **语义可预期**：看到弹框＝agent 正在等，而不是"门已放行、agent 自己往前跑"；避免用户误判确认已被采纳。
2. **不白烧 token**：挂起期间不再产生被守卫拒绝的工具调用与多余轮次。
3. **不丢回答**：任何中止路径都留可查凭据，作答后仍能落章与推进（不静默降级）。

### 与现状的区别

现状 = "超 30s 不判失败的放行"；改后 = "**缺省阻塞**，非阻塞必须显式声明"。

## 用户与角色

| 角色 | 谁 | 在本需求里做什么 |
|---|---|---|
| 使用看板的人 | 项目的操作者 | 在弹框作答；看到的是"agent 正在等待"，而不是 agent 已经在跑 |
| 窗口 agent | 跑 reqboard 工具的会话 | 调 `reqboard_ask_confirm`；阻塞期间不产出任何下游产物 |
| 维护者 | 改 dsh-pmboard 的开发者 | 依赖唯一的等待策略；新增弹框入口时不必再各自决定宽限 |

## 功能点

- **FR-1: 确认弹框缺省阻塞到作答**

  `reqboard_ask_confirm` 未显式传 `inline_grace_ms` 时，工具必须等到人作答（或取消/中止）才返回；
  返回体与旧同步语义一致（`confirmed`/`advanced`/`note` 等既有键），**不得**出现 `pending:true`/`ticket`。
  判定：`questions.ask` 永不 resolve + 调用工具 → 工具 30s 时**仍未返回**（旧实现此时返回 `pending:true`）。

- **FR-2: 阻塞期间 loop 不得产出下游产物**

  阻塞等待期间，同窗口的 `reqboard_submit` / `reqboard_decompose` / `reqboard_move` /
  `reqboard_task_move` 仍被代码级拒绝（`REQBOARD_CONFIRM_PENDING`），且拒绝信息含取回执的两条路径；
  `reqboard_status` 与 `reqboard_confirm_receipt` 保持可用。
  判定：`tests/confirm-pending-guard.test.ts` 全绿 + 阻塞中实测写路径被拒且不写盘。

- **FR-3: 非阻塞投递仅由显式宽限启用（逃生舱保留）**

  只有调用方显式传正数 `inline_grace_ms` 时才走"宽限赛跑 → 挂起 ticket → 后台落章 → 唤醒窗口"；
  非法值（0/负数/非数）显式拒绝、不静默回落。判定：传 `inline_grace_ms: 20` + `ask` 永不 resolve →
  返回 `pending:true` 且 ticket 非空；不传 → 不出现 `pending` 键。

- **FR-4: 中止路径响亮且可续**

  阻塞期间被 deadline / 取消中止时，必须：(a) 留下可查的挂起记录（或结构化错误，含 ticket/恢复命令）；
  (b) 该窗口的写路径继续被守卫拦住，直到人作答或显式解除；(c) 不出现"弹框被丢掉、既没落章也没留痕"的静默态。
  判定：构造"调用方中止"用例 → `reqboard_status` 能查到挂起/断点，写路径被拒。

- **FR-5: 提示词与工具描述与新语义一致**

  `AskConfirmTool` 的参数说明与 pm 提示词必须写明：**缺省阻塞**；传 `inline_grace_ms` 等于主动放弃阻塞、
  须自行承受到期后 loop 继续跑的后果；并保留 `reqboard_confirm_receipt` 的取回执指引。
  判定：`tests/tools-schema.test.ts` / 提示词快照测试全绿；工具描述文本含"缺省阻塞"。

- **FR-6: 兼容性不退化**

  已确认产物的早返回（不重复弹框）、看板确认通道（`fallback=board`）、
  文字证据路径（`evidence`）、挂起 ticket 的回执契约（`PendingConfirmationOutcome`）逐字不变。
  判定：`npx vitest run tests/ask-confirm.test.ts tests/ask-confirm-pending.test.ts
  tests/confirm-receipt.test.ts tests/confirm-pending-guard.test.ts` 全绿。

## 决策点（需人工门裁决）

| # | 问题 | 选项 | 建议 |
|---|---|---|---|
| D-1 | 缺省到底是"阻塞"还是"保留非阻塞、只把 agent 的停手纪律写进提示词"？ | A 缺省阻塞（本需求 FR-1 口径）／B 维持现状 + 只做提示词纪律 | **A**：B 治不了"界面上看不出 agent 在等"与"守卫拒绝前的空转" |
| D-2 | 阻塞等待的上限 | A 沿用工具超时 1h（`timeoutInteractiveMs`）／B 设一个新上限（如 30min）＋ 到点转入挂起 ticket | **A**：B 等于把非阻塞偷偷带回来，需人明确裁定 |
| D-3 | 调用方执行预算（run_code 缺省 120s / 上限 600s）短于等待时长时 | A 由调用方自行传 `inline_grace_ms` 兜底（显式）／B 插件侧按调用方能力自适应 | **A**：显式优于隐式；若采用 B 需先拿到宿主能力查询接口 |

## 验收标准

### 可执行判定命令

```bash
# FR-1 / FR-3：缺省阻塞 / 显式宽限才非阻塞
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts
# 预期：passed（缺省分支无 pending 键；显式宽限分支返回 pending+ticket）

# FR-2 / FR-4：挂起期间停手守卫 + 中止可续
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts
# 预期：passed（pending 存在时 submit/move/task_move/decompose 被拒 REQBOARD_CONFIRM_PENDING）

# FR-6：既有确认链路不退化
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
# 预期：passed
```

### 端到端判定（人工可见）

在任一绑定需求的窗口发一次确认门 → 弹框出现后：
1. **不作答**：agent 不再产生新的工具调用/产物（界面上 agent 处于等待）；
2. **作答**：同一调用内返回 `confirmed/advanced`，需求按闸门推进；
3. **取消弹框**：工具返回中性未作答结论，节点未推进，且没有任何下游产物被写。

## 参考

- 弹框通道（原生）：`@deepseek-ai/dsh-user-questions/lib/index.js`、`@deepseek-ai/dsh-tool-ask-user/lib/index.js`
- pm 侧等待策略：`packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts`、
  `src/application/internal/pending-confirm.ts`、`src/domain/limits.ts`
- 停手守卫：`src/application/internal/support.ts`（REQ-260927100007-b8ba FR-9）
- 非阻塞投递的原始设计：`docs/requirements/REQ-260924213231-b1c4/`（FR-3 非阻塞投递 + 回执）
- 流水线流程：`docs/architecture/reqboard-pipeline-flow.md`（"非阻塞投递：30s 宽限内作答 = 同步落章"）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t2、t5 |
| FR-2 | ✅ 已接收 | t5、t1、t3 |
| FR-3 | ✅ 已接收 | t2、t5 |
| FR-4 | ✅ 已接收 | t2、t5、t1、t3 |
| FR-5 | ✅ 已接收 | t5、t4 |
| FR-6 | ✅ 已接收 | t5、t6 |

> 无未接收条款（6 条全部有落点）。

<!-- reqboard:marks:end -->
