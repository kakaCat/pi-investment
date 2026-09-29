---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
---

# 接口设计（REQ-260927123256-196b）

> 读者：工程 / agent。本文是**可执行契约**：字段名、类型、默认值、错误码以本文为准，
> 实施与测试不得另立口径。既有返回键**只增不改**（消费者忽略未知键即兼容）。

## 接口清单 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->

| 编号 | 接口 | 输入 | 输出 | 兼容性 | serves |
|---|---|---|---|---|---|
| I-1 | `reqboard_ask_confirm`（工具，弹框路径） | 既有 + `inline_grace_ms?` | 既有键 + `interrupted?`；缺省路径**不再出现** `pending`/`ticket` | 等待语义反转：缺省从「宽限放行」变「阻塞到作答」 | FR-1, FR-3, FR-4, FR-5 |
| I-2 | `reqboard_status`（工具） | 无（零参） | 既有键 + `pending_confirms[]` | 只增可选键 | FR-4 |
| I-3 | `assertNoPendingConfirm`（内部接缝） | `(deps, windowKey)` | 无返回值；命中则抛 `REQBOARD_CONFIRM_PENDING` | 判定收紧为「台账未落章的未作答记录」 | FR-2, FR-4 |
| I-4 | `PendingConfirmPort`（内部接缝） | — | 5 方法 | +1 方法；`PendingConfirmationOutcome` 不变 | FR-4, FR-6 |
| I-5 | 工具描述 / 提示词（文案契约） | — | 文本 | 只改文案 | FR-5 |
| I-6 | `reqboard_confirm_receipt`（工具） | `ticket` | 既有键（不变） | 逐字不变；仅 `note` 在被中止记录上更精确 | FR-4, FR-6 |

## I-1 `reqboard_ask_confirm` 等待语义矩阵 <!-- serves: FR-1, FR-3, FR-4 -->

**参数**（在既有参数上只改说明，不增删键）：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `inline_grace_ms` | number | 否 | **不传 = 缺省阻塞**（等到作答/取消/中止）；传正数 = 主动放弃阻塞（超时返回 `pending+ticket`）。非法值（≤0/非数）拒绝 |

**行为矩阵（本条是 FR-1/FR-3 的判定口径）**：

| `inline_grace_ms` | `deps.pendingConfirms` | 行为 | 返回体关键键 |
|---|---|---|---|
| 缺省 | 任意（含 undefined） | **阻塞**：`await ask`，直到 resolve / 取消 / 中止 | resolve → 既有键（无 `pending`/`ticket`）；中止 → `pending:true + ticket + interrupted:true` |
| 正数 | 已装配 | **非阻塞**：`raceAsk(ask, grace)` | 超宽限 → `pending:true + ticket`（后台落章 + 唤醒） |
| 正数 | `undefined` | **拒绝** `REQBOARD_NONBLOCK_UNAVAILABLE` | 不返回正常体（不静默回落为阻塞） |
| ≤0 / 非数 | 任意 | **拒绝** `REQBOARD_INVALID_INPUT` | 不返回正常体 |

**返回键全集**（`output.schema` 必须全部声明；新增键为 `interrupted`）：

```typescript
interface AskConfirmOutput {
  success: boolean
  confirmed: boolean
  advanced: boolean
  from?: string
  to?: string
  requirement_id?: string
  fallback?: 'board'                                        // 弹框通道不可用（语义不变）
  target?: string                                           // evidence 路径
  kind?: string                                             // evidence 路径
  via?: string                                              // evidence 路径
  evidence_verified?: boolean                               // evidence 路径
  user_choice?: string                                      // 非肯定项
  user_feedback?: string                                    // 非肯定项
  pending?: boolean                                         // 仅显式宽限超时 / 阻塞被中止
  ticket?: string                                           // 同上（前缀 pc-）
  interrupted?: boolean                                     // 新增：阻塞等待被中止
  gate_failure?: { code: string; gaps: string[]; message: string }
  note: string
}
```

**分支返回明细**：

| 分支 | 返回 | 副作用 |
|---|---|---|
| 缺省阻塞 + 肯定项 | `{success:true, confirmed:true, advanced, from, to, requirement_id, note}` | 落章 + 推进；registry `settle` |
| 缺省阻塞 + 非肯定项 | `{success:true, confirmed:false, advanced:false, user_choice, user_feedback?, note}` | 只留痕；registry `settle` |
| 缺省阻塞 + `ASK_CANCELLED` | `{success:false, confirmed:false, advanced:false, note:'用户未作答（取消/暂离）…'}` | registry `settle`（守卫放行） |
| 缺省阻塞 + `ASK_ABORTED` / `signal.aborted` | `{success:false, confirmed:false, advanced:false, pending:true, ticket, requirement_id, interrupted:true, note}` | registry `markInterrupted`（守卫继续拦） |
| 显式宽限超时 | `{success:true, confirmed:false, advanced:false, pending:true, ticket, requirement_id, note}` | 后台续跑接管 |

**中止分支的 `note` 必须含恢复命令**（可证伪锚点）：
至少包含 `reqboard_confirm_receipt(ticket="pc-…")` 与「到项目看板点确认按钮」两条路径，
以及「收到作答前不得产出下游产物」。

## I-2 `reqboard_status.pending_confirms` <!-- serves: FR-4 -->

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pending_confirms` | array | 是（可为空数组或省略） | 本窗口**仍然有意义**的未作答确认（已 settle / 已过期 / 台账已落章的陈旧记录不列） |
| `pending_confirms[].ticket` | string | 是 | `pc-…` |
| `pending_confirms[].requirement_id` | string | 是 | 目标需求 |
| `pending_confirms[].target` | `"artifact"|"plan"` | 是 | 与 ask_confirm 同语义 |
| `pending_confirms[].kind` | string | 否 | `target=artifact` 时的产物种类 |
| `pending_confirms[].created_at` | number | 是 | 登记时间戳（ms） |
| `pending_confirms[].interrupted` | boolean | 是 | 是否被中止（`interruptedAt` 已写） |
| `pending_confirms[].blocked_tools` | string[] | 是 | 被守卫拦住的写路径名单（见 I-3） |
| `pending_confirms[].recovery` | string | 是 | 一句话恢复指引（含 `reqboard_confirm_receipt` 与看板两条路径） |

## I-3 停手守卫 `assertNoPendingConfirm` <!-- serves: FR-2, FR-4 -->

**签名**：`assertNoPendingConfirm(deps: UseCaseDeps, windowKey: string): void`

**判定（升级后）**：

```typescript
p = deps.pendingConfirms?.pendingForWindow(windowKey)
if (p === undefined) return                      // 无挂起
if (targetConfirmedInLedger(req, p)) return      // 人已通过看板/证据通道作答 → 陈旧记录，放行
throw REQBOARD_CONFIRM_PENDING                   // 否则拦下
```

**挂载点（不变）**：`reqboard_submit` / `reqboard_decompose` / `reqboard_move` / `reqboard_task_move`
（`MoveTool.ts:42`、`TaskMoveTool.ts:42`、`SubmitTool.ts:208`、`DecomposeTool.ts:59`）。
`reqboard_status` 与 `reqboard_confirm_receipt` **刻意不过守卫**（否则人无法解除挂起）。

**拒绝消息契约**（三要素缺一即契约破坏）：

| 要素 | 内容 |
|---|---|
| what | ticket + 目标需求 id |
| why | 「收到作答前不得产出下游产物」 |
| how | ① `reqboard_confirm_receipt(ticket="pc-…")` 取回执；② 项目看板点确认按钮；③ 重新发起 `reqboard_ask_confirm` 覆盖旧记录 |

## I-4 `PendingConfirmPort` 变更 <!-- serves: FR-4, FR-6 -->

```typescript
interface PendingConfirmPort {
  register(input: { windowKey: string; requirementId: string; target: 'artifact' | 'plan'; kind?: ArtifactKind }): PendingConfirmation
  get(ticket: string, windowKey: string): PendingConfirmation | undefined
  settle(ticket: string, outcome: PendingConfirmationOutcome): PendingConfirmation | undefined
  pendingForWindow(windowKey: string): PendingConfirmation | undefined
  /** 新增（FR-4）：标记「阻塞等待期间被中止」——只写首次；未知 ticket → undefined（不抛）。 */
  markInterrupted(ticket: string): PendingConfirmation | undefined
}
```

| 方法 | 语义变化 |
|---|---|
| `register` | 不只在超宽限时调用；**每次 ask_confirm 进入等待前**都会调用（阻塞/非阻塞共用） |
| `get` / `pendingForWindow` | 过期基准改为 `(interruptedAt ?? createdAt) + ttlMs`（中止记录再获一个完整 TTL） |
| `settle` | 逐字不变（幂等，保留首次 outcome） |
| `markInterrupted` | 新增；幂等（只写首次 `interruptedAt`） |

`PendingConfirmationOutcome`（`confirmed` / `advanced` / `userChoice?` / `userFeedback?`）**逐字不变**。

## I-5 文案契约（工具描述与提示词） <!-- serves: FR-5 -->

| 位置 | 必须出现的语义 | 可证伪锚点 |
|---|---|---|
| `ASK_CONFIRM_PROMPT`（`AskConfirmTool/prompt.ts`） | 弹框路径**缺省阻塞**；`inline_grace_ms` = 主动放弃阻塞、后果自负 | 文本含「缺省阻塞」 |
| `inline_grace_ms` 参数 description | 「不传 = 阻塞等到作答；显式正数 = 超时返回 pending+ticket，loop 继续跑」 | 文本含「缺省」与「阻塞」 |
| `ConfirmReceiptTool/prompt.ts` | 保留取回执指引；补「被中止的挂起记录同样可凭 ticket 查询」 | 含 `reqboard_confirm_receipt` |

## I-6 `reqboard_confirm_receipt` 兼容性 <!-- serves: FR-4, FR-6 -->

- 字段、类型、错误码（`REQBOARD_UNKNOWN_TICKET`）**逐字不变**。
- `confirmed` 仍以台账 `confirmedAt` / `plan.approvedAt` 为准（`ConfirmReceipt.ts:76-80`）。
- 仅当记录带 `interruptedAt` 且尚未作答时，`note` 改为「本次等待已被中止（弹框可能已消失）：请用户走看板确认，
  或重新发起 `reqboard_ask_confirm`」——不新增/不改键。

## 错误语义 <!-- serves: FR-1, FR-3, FR-4, FR-5 -->

| 编号 | 错误码 / 情形 | 触发 | 调用方处置 |
|---|---|---|---|
| E-1 | `REQBOARD_INVALID_INPUT` | `inline_grace_ms` ≤0 / 非数 | 传正数或不传 |
| E-2 | `REQBOARD_NONBLOCK_UNAVAILABLE` | **新增**：显式正数宽限但 `pendingConfirms` 未装配 | 不传宽限（改用缺省阻塞），或修复装配 |
| E-3 | `REQBOARD_CONFIRM_PENDING` | 本窗口存在未作答且台账未落章的挂起 | 取回执 / 看板确认 / 重新发起 |
| E-4 | `fallback=board` | 弹框通道不可用 | 走看板（语义不变） |
| E-5 | `REQBOARD_UNKNOWN_TICKET` | 回执 ticket 未知 / 跨窗口 / 过期 | 改 `reqboard_status` 查台账 |
| E-6 | `REQBOARD_NO_BOUND_REQ` / `REQBOARD_NOT_BOUND_TO_WINDOW` | 既有绑定校验 | 不变 |

## 兼容性矩阵 <!-- serves: FR-6 -->

| 消费方 | 旧行为 | 新行为 | 兼容判据 |
|---|---|---|---|
| 旧调用方（不传宽限） | 30s 后拿 `pending` | 等到作答才返回 | 返回键集不含 `pending`/`ticket`；`confirmed/advanced/from/to/note` 同义 |
| 旧调用方（传宽限） | 宽限赛跑 | 宽限赛跑 | 逐字一致 |
| `reqboard_status` 消费者 | 无 `pending_confirms` | 多一个可选键 | JSON 未知键忽略 |
| `PendingConfirmPort` 实现者 | 4 方法 | 5 方法 | 唯一实现为 `PendingConfirmRegistry`；测试形状断言同步更新 |
| `turn/end` 断点机制等其它系统 | 各自独立 | 不受影响 | 本需求不碰 |
