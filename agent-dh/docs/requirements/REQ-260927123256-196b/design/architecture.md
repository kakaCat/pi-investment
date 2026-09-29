---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
---

# 架构设计（REQ-260927123256-196b · 确认弹框缺省阻塞）

> 读者：工程 / agent。根因、边界与可证伪验收见 requirement.md「现状与根因」；本文只讲「怎么改」。
> 代码坐标相对 `packages/web/dsh-pmboard/`。

## TL;DR <!-- serves: FR-1, FR-3, FR-4 -->

三条主线：

1. **缺省阻塞（FR-1）**：`AskConfirm` 不传 `inline_grace_ms` 时走 `await deps.questions.ask(...)`——
   工具的返回时刻 =「人作答 / 取消 / 中止」的时刻。删除「30s 到点自动放行 loop」这一缺省行为。
2. **非阻塞只由显式宽限启用（FR-3）**：只有 `inline_grace_ms` 是**正数**时才走
   `raceAsk → 挂起 ticket → 后台落章` 的逃生舱；非法值显式拒绝；能力未装配
   （`deps.pendingConfirms === undefined`）时也**拒绝而非静默回落为阻塞**。
3. **登记即守卫（FR-2 / FR-4）**：进入等待前先 `register` 一个 ticket（阻塞与非阻塞**共用同一注册表**）：
   - 正常作答 / 用户取消弹框 → `settle` → 守卫放行；
   - 被 deadline / 调用方取消**中止** → 不 settle、打 `interruptedAt` 标记 →
     `reqboard_status.pending_confirms` 可查、写路径继续被 `REQBOARD_CONFIRM_PENDING` 拦住，
     直到人作答（任何确认通道写台账 `confirmedAt`/`approvedAt`）或重新发起确认。

## 目标与总体方案 <!-- serves: FR-1 -->

**问题**：现状 =「超 30s 不判失败的放行」——弹框留在界面上、工具已经返回、loop 继续往下跑。

**当前状况**：`AskConfirm.ts:154-159` 用 `raceAsk(ask, LIMITS.confirmInlineGraceMs)`（缺省 30s）；
超宽限调 `internal/pending-confirm.ts` 的 `suspendConfirm`（`pending-confirm.ts:81-119`），
登记内存 ticket 后**立即返回** `{success:true, confirmed:false, pending:true, ticket}`，
而 `ask` 的 promise 继续挂着（`void ask.then(...)`）。`deps.pendingConfirms === undefined` 时走旧的
`await ask` 分支（`AskConfirm.ts:144-152`）。

**设计方案**：等待策略由「调用方是否显式声明宽限」决定，而不是由固定宽限决定。
把 `AskConfirm` 的编排收敛成两条互斥分支 + 一个共享的「先登记、后等待、再 settle」骨架（见下节状态机）。

**不这么做的后果**：只把「停手纪律」写进提示词（需求 D-1 选项 B）治不了「界面上看不出 agent 在等」，
也治不了守卫拒绝前的空转与 token 燃烧——根因在**调用方等不等**，不在提示词。

## 等待语义状态机 <!-- serves: FR-1, FR-3, FR-4 -->

```
                  ┌─ graceRaw === undefined ──────────────────────────────┐
                  │  缺省 = 阻塞（FR-1）                                   │
                  │  ticket = port?.register(...)   ← 登记即守卫（FR-2）   │
                  │  try { answers = await ask }                          │
                  │   ├─ resolve ──────────► body = settleAnswers(...)     │
                  │   │                      port?.settle(ticket, outcome) │
                  │   │                      return body（无 pending/ticket）│
                  │   ├─ reject + ASK_CANCELLED（用户关掉弹框）             │
                  │   │                      port?.settle(ticket, 未确认)   │
                  │   │                      return degradedAnswer(err)     │
                  │   └─ reject + ASK_ABORTED / signal.aborted（中止）      │
                  │                          port?.markInterrupted(ticket)  │
                  │                          return {pending:true, ticket,  │
                  │                                  interrupted:true, ...}│
                  └───────────────────────────────────────────────────────┘
                  ┌─ graceRaw 是正数 ─────────────────────────────────────┐
                  │  显式 = 非阻塞（FR-3，逃生舱）                          │
                  │  port 未装配 → reject REQBOARD_NONBLOCK_UNAVAILABLE    │
                  │  ticket = port.register(...)                          │
                  │  raced = await raceAsk(ask, graceRaw)                 │
                  │   ├─ answered ──► settleAnswers + settle(ticket)      │
                  │   ├─ rejected ──► settle(ticket) + degradedAnswer     │
                  │   └─ timeout ───► suspendConfirm(..., ticket)          │
                  │                   （后台作答 → settle + 唤醒窗口）       │
                  └───────────────────────────────────────────────────────┘
```

**为什么阻塞也登记 ticket**：阻塞只是让**本工具的调用**停住；同一回合的**并行工具调用**仍然可能落盘。
只有「登记一个未作答记录 + 写路径入口统一守卫」才能把 FR-2 的「阻塞期间 loop 不得产出下游产物」变成
代码级事实，而不是靠模型自觉。登记与守卫复用既有 `PendingConfirmPort`，不新建机制。

**重新发起 = 显式解除**：一次新的 `reqboard_ask_confirm` 开始前，先把本窗口既有的未作答记录
`settle({confirmed:false, advanced:false})` 作废，再登记新 ticket——保证「本窗口同一时刻只有一条权威挂起」，
也给「中止后续跑」提供了重试路径。

## 停手守卫与解除路径 <!-- serves: FR-2, FR-4 -->

守卫判定从「注册表里有没有未作答记录」升级为「有没有**仍然有意义**的未作答记录」：

| 记录状态 | 守卫行为 | 理由 |
|---|---|---|
| 无记录 | 放行 | 无挂起 |
| 未作答 + 台账未见目标落章 | 拒绝 `REQBOARD_CONFIRM_PENDING` | 人还没答，不得产出下游产物 |
| 未作答 + 台账已有落章（`confirmedAt` / `plan.approvedAt`） | 放行（判定为陈旧记录，不再拦截） | 人已通过看板/文字证据通道作答——**不让窗口死锁** |
| 已 settle / 已过期 | 放行 | 正常解除 |

台账判定与 `reqboard_confirm_receipt` 的「以台账为准」共用同一谓词（`targetConfirmedInLedger`），
避免两处口径漂移。实现落在新增的 `application/internal/pending-guard.ts`，被
`support.ts:assertNoPendingConfirm` 与 `QueryState`（status 投影）共用。

## 模块改动地图 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5 -->

```
  调用方(agent loop)        AskConfirm 用例              PendingConfirmRegistry     台账
   │ ask_confirm(无 grace) ─►│ register(ticket) ─────────►│                          │
   │  （阻塞，loop 停住）    │ await ask ─────►（宿主弹框） │                          │
   │                        │                              │                          │
   │  同回合并行写工具 ──────┼─► assertNoPendingConfirm ───►│ pendingForWindow         │
   │  ◄ REQBOARD_CONFIRM_PENDING（含 ticket + 两条取回路径）│ + 台账落章判定 → 放行/拒  │
   │                        │                              │                          │
   │                        │ 中止 → markInterrupted ──────►│ interruptedAt            │
   │                        │ reqboard_status ─────────────►│ pending_confirms 投影    │
   │  人作答/看板确认 ────────────────────────────────────────────────────────────────►│ confirmedAt
   │                        │ 守卫下次判定：台账已落章 → 放行                        │
```

| 文件 | 类型 | 改动 | serves |
|---|---|---|---|
| `src/application/use-cases/AskConfirm.ts` | 改 | 编排重写：缺省阻塞 / 显式宽限 / 中止分支；登记先于等待；返回体组装 | FR-1, FR-3, FR-4 |
| `src/application/internal/pending-confirm.ts` | 改 | `suspendConfirm` 接收**已登记**的 ticket（不再二次 register）；导出 `outcomeOf`；新增 `registerConfirm` | FR-3 |
| `src/application/internal/pending-guard.ts` | 新增 | `targetConfirmedInLedger` / `livePendingConfirm` / 拒绝文案常量 | FR-2, FR-4 |
| `src/application/internal/support.ts` | 改 | `assertNoPendingConfirm` 改用 `livePendingConfirm`；文案补「重新发起确认」路径 | FR-2 |
| `src/application/use-cases/ConfirmReceipt.ts` | 改 | 复用共享谓词；`interruptedAt` 存在时回执文案区分「被中止」 | FR-4, FR-6 |
| `src/application/query/QueryState.ts` | 改 | 新增 `pending_confirms` 投影 | FR-4 |
| `src/tools/StatusTool/StatusTool.ts` | 改 | `output.schema` 声明 `pending_confirms` | FR-4 |
| `src/tools/AskConfirmTool/AskConfirmTool.ts` | 改 | 声明 `interrupted` 键；改 `inline_grace_ms` 参数说明（缺省阻塞） | FR-4, FR-5 |
| `src/tools/AskConfirmTool/prompt.ts` | 改 | 工具描述写明「缺省阻塞；显式宽限 = 主动放弃阻塞」 | FR-5 |
| `src/domain/limits.ts` | 改 | 删除 `confirmInlineGraceMs`（缺省值语义已不存在） | FR-1 |
| `src/adapters/PendingConfirmRegistry.ts` | 改 | 新增 `markInterrupted`；过期基准改为 `interruptedAt ?? createdAt` | FR-4 |
| `src/application/ports.ts` | 改 | `PendingConfirmPort` 增 `markInterrupted` | FR-4 |
| `src/shared/protocol.ts` | 改 | `PendingConfirmation` 增可选 `interruptedAt` | FR-4 |

## 错误处理 <!-- serves: FR-4, FR-5 -->

| 情形 | 错误码 / 返回 | 响亮程度 |
|---|---|---|
| `inline_grace_ms` 为 0 / 负数 / 非数 | 拒绝 `REQBOARD_INVALID_INPUT`（沿用既有校验） | 响亮（既有） |
| 显式正数宽限但非阻塞能力未装配 | 拒绝 `REQBOARD_NONBLOCK_UNAVAILABLE` | 响亮（新增；不静默变阻塞） |
| 弹框通道不可用 | 返回 `fallback=board`（语义不变） | 响亮（既有） |
| 用户取消弹框（`ASK_CANCELLED`） | 中性返回「未作答、未推进」+ settle 记录 | 中性（既有） |
| 阻塞期间被中止（`ASK_ABORTED` / `signal.aborted`） | 返回 `pending:true + ticket + interrupted:true`；`markInterrupted` 留痕 | 响亮（新增） |

## 配置项与删除项 <!-- serves: FR-1, FR-5 -->

| 项 | 改动 | 说明 |
|---|---|---|
| `LIMITS.confirmInlineGraceMs`（30s） | **删除** | 它是「缺省放行」的唯一来源；留着会造成「两份真相」 |
| `LIMITS.timeoutInteractiveMs`（1h） | 不变 | 阻塞等待的上限（需求 D-2 裁定 A：沿用工具超时） |
| 新增开关 | **无** | 行为差异完全由 `inline_grace_ms` 显式声明，不引入灰度开关 |

## 兼容性与回滚 <!-- serves: FR-6 -->

| 消费方 | 旧行为 | 新行为 | 兼容判据 |
|---|---|---|---|
| `reqboard_ask_confirm`（不传宽限） | 等宽限 30s → pending | 一直等到作答 / 取消 / 中止 | 返回键仍在既有集合内（无 pending/ticket），`confirmed/advanced/note` 同义 |
| `reqboard_ask_confirm`（显式宽限） | 宽限赛跑 | 宽限赛跑（逐字不变） | TC-5 原断言继续成立 |
| 已确认产物早返回 / `fallback=board` / `evidence` 路径 | 各自语义 | **逐字不变** | FR-6 回归集全绿 |
| `PendingConfirmationOutcome` | 4 键 | **逐字不变** | `contract-shapes.test.ts` 的 `expectTypeOf` 断言保留 |
| `PendingConfirmPort` 形状 | 4 方法 | +1 方法（`markInterrupted`） | 形状断言需同步（内部接缝，非工具契约） |
| `reqboard_status` | 无 pending 字段 | +可选 `pending_confirms` | 未知键忽略即兼容 |

**回滚路径**：无数据迁移、无台账 schema 变更——回退到上一版插件构建即恢复旧语义；
中止留下的 `interruptedAt` 只存在于内存注册表，进程重启即消失（不污染台账）。
**灰度**：单进程插件，重启即全量；无服务端灰度需求。

## 安全 / 性能考虑 <!-- serves: FR-1, FR-2 -->

| 风险 | 影响 | 缓解 |
|---|---|---|
| 缺省阻塞把调用方回合吊死 | 人长时间不在 → 工具 1h 超时后中止 | 工具 `timeoutMs = timeoutInteractiveMs`（1h）兜底；中止走 FR-4 响亮路径而非静默 |
| 挂起记录让窗口永久无法写 | 人始终不答 | 台账落章即放行（看板/证据通道）；记录 TTL 到期自动失效；重新发起可作废旧记录 |
| 登记写内存注册表的开销 | 忽略不计 | 单条 Map 记录，无 I/O |

## 文档更新清单 <!-- serves: FR-5 -->

| 文档 | 更新内容 |
|---|---|
| `agent-dh/docs/architecture/reqboard-pipeline-flow.md` | G1/G2 步骤里「非阻塞投递：30s 宽限内作答…agent loop 不被拦」改写为「缺省阻塞；仅显式 `inline_grace_ms` 才走非阻塞逃生舱」 |

## 关键决策点（对齐需求 D-1/D-2/D-3） <!-- serves: FR-1, FR-3, FR-4 -->

| 决策 | 采用 | 依据 |
|---|---|---|
| D-1 缺省阻塞 vs 只写提示词纪律 | **缺省阻塞** | 提示词治不了「界面看不出在等」与空转 |
| D-2 阻塞上限 | **沿用工具超时 1h** | 不设新上限（设新上限等于偷偷带回非阻塞） |
| D-3 调用方预算短于等待 | **调用方显式传 `inline_grace_ms`** | 显式优于隐式；插件不猜调用方能力 |
| 阻塞期是否登记 ticket | **登记** | 用代码兑现 FR-2 的停手守卫与 FR-4 的可查记录 |
| 用户取消弹框是否留挂起 | **不留（settle）** | E2E 口径：取消 = 中性未作答、节点未推进、不阻塞后续 |

## 测试策略 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->

| 场景 | 输入 | 预期 | 用例 |
|---|---|---|---|
| 缺省阻塞 | `ask` 永不 resolve、不传宽限 | 工具在观测窗内**未返回**；resolve 后返回同步体（无 pending） | TC-1 |
| 阻塞期停手 | 缺省阻塞进行中 | `submit/move/task_move/decompose` 被拒 `REQBOARD_CONFIRM_PENDING`，不写盘 | TC-6 |
| 显式宽限 | 永不 resolve + `inline_grace_ms: 20` | 返回 `pending:true` + `ticket` 非空 | TC-4 |
| 非法宽限 | `0` / `-1` / `"x"` | 拒绝 `REQBOARD_INVALID_INPUT` | TC-3 |
| 能力未装配 + 显式宽限 | `pendingConfirms` 缺省 + 正数宽限 | 拒绝 `REQBOARD_NONBLOCK_UNAVAILABLE` | TC-5 |
| 中止 | `ask` 拒绝 `ASK_ABORTED` | 返回 `interrupted:true + ticket`；status 可查；守卫仍拦 | TC-7 |
| 取消弹框 | `ask` 拒绝 `ASK_CANCELLED` | 中性返回、无 pending 键、守卫放行 | TC-8 |
| 台账已落章解除 | 中止留下记录后写入 `confirmedAt` | 守卫放行；status 不再列该记录 | TC-9 |
| 提示词 | 工具描述 + 参数说明 | 含「缺省阻塞」与「显式宽限 = 放弃阻塞」 | TC-11 |
| 回归 | 既有 4 个测试文件 | 全绿（除按新语义更新的用例） | TC-12, TC-13 |

细化为可执行用例见 [test-cases.md](./test-cases.md)。
