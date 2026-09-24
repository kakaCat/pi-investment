---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8]
---

# 接口设计（REQ-260924213231-b1c4）

> 读者：工程 / agent。本文是**可执行契约**：字段名、类型、默认值、错误码以本文为准，
> 实施与测试不得另立口径。既有返回键一律**只增不改**（消费者忽略未知键即兼容）。

## 接口清单 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| 编号 | 接口 | 输入 | 输出 | 兼容性 | 错误语义 | serves |
|---|---|---|---|---|---|---|
| I-1 | `reqboard_submit(kind=design)`（工具） | `kind` 必填、`requirement_id?`、`path?`（单份登记，缺省=扫 `design/` 全目录） | `success`、`requirement_id`、`design_docs[]`、`registered_count`、`note` | 纯新增 kind；既有 4 值语义不变 | 见 §错误语义 E-1/E-2 | FR-1 |
| I-2 | `reqboard_status()`（工具） | 无（零参；`{}` 等价） | 既有键 + `design_docs[]`、`interruption?`、`next_actions`（终态一致） | 新增字段，旧消费方忽略即兼容 | 不新增拒绝 | FR-1, FR-6 |
| I-3 | `reqboard_ask_confirm`（工具，弹框路径） | 既有 + `inline_grace_ms?`（缺省取配置） | 既有键 + `pending?`、`ticket?`；已确认早返回补 `gate_failure?` | 只增键；宽限内作答与原语义**逐字一致** | 见 E-3/E-4 | FR-2, FR-3 |
| I-4 | `reqboard_confirm_receipt(ticket)`（新工具） | `ticket` 必填 | `success`、`confirmed`、`advanced`、`from`、`to`、`requirement_id`、`note` | 新工具，零影响 | `REQBOARD_UNKNOWN_TICKET`（E-5） | FR-3 |
| I-5 | 工具绑定层（`run_code` 的 `tools.*`） | 任意工具的调用参数（可省） | 与显式传 `{}` 完全一致 | 放宽：零参由「拒绝」变「接受」 | 不再产生 `binding arguments must be lossless JSON` | FR-4 |
| I-6 | `reqboard_create`（工具） | 既有 + `doc_location?`（工作区相对目录或 `docs/requirements/<REQ>/` 形式） | 既有键 + `doc_location`、`defaults_used[]`；`status` 为推进后**终态** | 只增键；缺省与旧行为逐字一致 | 见 E-6 | FR-7 |
| I-7 | pm 弹框来源标志（`AskQuestion.header` 契约） | pm 侧构造的每个问题 | `header` 以固定前缀 `📋 PM · ` 开头 | 只改 header 文本，不改宿主 schema | 无 | FR-8 |
| I-8 | `reqboard_note_interruption(reason)`（新工具） | `reason` 必填、`requirement_id?` | `success`、`requirement_id`、`interruption`、`note` | 新工具，零影响 | `REQBOARD_INVALID_INPUT`（reason 空） | FR-6 |
| I-9 | **闸门拒绝信封**（`reqboard_move` / `reqboard_submit` / `reqboard_decompose` 等全部内容闸门） | 触发的闸门（文档/编号/内容） | 抛错消息 = `<tool> 未执行：<what> —— <why>。补齐：<how>` | 仅文案分化，错误 `code` 与判定逻辑不变 | 见 E-7/E-8/E-10 | FR-2 |

### I-1 字段明细 <!-- serves: FR-1 -->

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `kind` | `"requirement"\|"plan"\|"verification"\|"archive"\|"design"` | 是 | — | 新增 `design` 值 |
| `requirement_id` | string | 否 | 本窗口绑定需求 | 必须属于本窗口 |
| `path` | string | 否 | 扫 `docs/requirements/<REQ>/design/*.md` | 给了则只登记该份（仍走可打开性校验） |
| `design_docs[].name` | string | 是 | — | 文件名，如 `architecture.md` |
| `design_docs[].path` | string | 是 | — | 工作区相对路径 |
| `design_docs[].on_disk` | boolean | 是 | — | 目录里是否真实存在 |
| `design_docs[].registered` | boolean | 是 | — | 产物簿是否有该条（`kind=design`） |
| `design_docs[].confirmed` | boolean | 是 | — | 是否已落章（`confirmedAt !== undefined`） |
| `design_docs[].exempted` | string | 否 | — | 有效豁免理由（front-matter `design_exempt`） |
| `design_docs[].conditional` | `"frontend"\|"backend"` | 否 | — | 条件必交标记 |
| `registered_count` | number | 是 | 0 | 本次**新登记**条数（幂等命中不计数） |

### I-4 字段明细 <!-- serves: FR-3 -->

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ticket` | string | 是 | I-3 在超宽限时返回的挂起确认标识 |
| `confirmed` | boolean | 是 | 以台账为准：目标产物 `confirmedAt` 已写 → true |
| `advanced` | boolean | 是 | 是否已推进（同 `ask_confirm` 语义） |
| `from` / `to` | string | 是 | 推进前后状态 |

### I-8 字段明细 <!-- serves: FR-6 -->

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `reason` | string | 是 | 中断原因原文（如 `upstream stream idle 3m ×5`） |
| `interruption` | object | 是 | `{ at:number, reason:string, stage:string, pendingAction:string, tool?:string }` |

**I-8 写入契约（两个写入源，台账单对象后写覆盖前写）**

| 写入源 | 触发 | 写什么 | 证据 |
|---|---|---|---|
| A 自动 checkpoint | 每次交棒用例 mutate 尾部（`submit`/`ask_confirm`/`move`/`decompose`/`task_move`/`accept_sheet`） | `reason="checkpoint"`，`stage`/`pendingAction` = 当前态与下一步命令；两字段未变则**不写** | 交棒返回体 `note` 与 `nextActionFor` 同源 |
| B 事件补写 | `session/event` 的 `turn/end`，`data.reason.kind ∈ {aborted, error, interrupted}` | `reason = "error:<code>:<message>"` / `"aborted:<cause>"` / `"interrupted"`，保留 `pendingAction` | `CaptureHook` 已订阅该事件（`adapters/CaptureHook.ts:225-251`）；值域见 `@deepseek-ai/dsh-session` 的 `TurnEndReasonMap` |
| B′ 工具补写 | `reqboard_note_interruption(reason)` | 同 B，原因由调用方给定 | 用例 `NoteInterruption` 写 comment |

**新增内部接缝（不是工具契约，供实施与测试对账）**

| 签名 | 位置 | 语义 |
|---|---|---|
| `onTurnFinished?(windowKey: string, outcome: {abnormal:boolean; reason:string}, session: unknown): void` | `CaptureHookDeps` | 只在 `turn/end` 发信号；**不得**在监听器内写会话（D-17），写台账经组合根的异步边界 |
| `turnEndOutcome(data: unknown): {abnormal:boolean; reason:string} \| undefined` | `application/internal/interruption.ts` | 纯函数；形态不认识返回 `undefined`（不猜） |
| `nextActionFor(req: RequirementRecord): string` | 同上 | 弹框/输入包/断点**共用**的下一步命令唯一事实源 |

### I-9 拒绝信封（文案契约） <!-- serves: FR-2 -->

每条闸门拒绝的消息必须**同时**包含三要素（缺一即视为契约破坏，有测试锁死）：

| 要素 | 内容 | 锚点要求 |
|---|---|---|
| what | 哪份文档 / 哪一条编号 | 工作区相对路径或 `FR-n` |
| why | 报错原因（病因），用 `——` 与 what 分隔 | 不得只写「未确认」「未交」 |
| how | 可复制的一步补齐动作，用 `补齐：` 引导 | 命中 `/reqboard_[a-z_]+/`、`templates/` 或 `design_exempt` 之一 |

覆盖的 `code`（与 architecture.md「闸门拒绝信封」表一一对应）：`design_doc_incomplete`、`design_orphan`、
`dangling_reference`、`requirement_uncovered`、`requirement_missing_clauses`、`requirement_clause_sequence_gap`、
`requirement_clause_duplicates`、`REQBOARD_MISSING_REQUIRED_DOC`、`REQBOARD_ARTIFACT_NOT_OPENABLE`、
`REQBOARD_FILE_MISSING`、`design_contains_decomposition`、`REQBOARD_EVIDENCE_FAKE`。

兼容性：`GateFailure.gaps`（结构化明细）与 `code` 均不变，只改 `message` 文本；已有消费方读 `code`/`gaps` 不受影响。
## 调用时序 <!-- serves: FR-1, FR-2, FR-3, FR-6 -->

```
FR-1 登记（幂等）：
  agent ──reqboard_submit(kind=design)──► SubmitTool ──► submitDesignArtifacts
        ◄── {design_docs:[...], registered_count:5} ──   （二次调用 registered_count=0）

FR-2 闸门（两种病因两种话）：
  agent ──reqboard_move(to=decomposing)──► checkDesignCompletenessGate
        ◄── 未登记：design/use-cases.md 未登记（…先登记：reqboard_submit(kind=design)）
        ◄── 待确认：design/use-cases.md 待确认（…先确认：reqboard_ask_confirm(target=artifact, kind=design)）

FR-3 弹框（非阻塞）：
  agent ──reqboard_ask_confirm(target=artifact, kind=design)──► 投递问题（questions.ask 不 await 到超时）
        ├─ 宽限内作答 ──► 落章+推进 ──► {confirmed:true, advanced:true}
        └─ 超宽限 ──────► {success:true, confirmed:false, pending:true, ticket:"pc-…"}   ← 不判失败
  人作答 ──►（后台）落章+推进 + AgentDeliverer 唤醒窗口
  agent ──reqboard_confirm_receipt(ticket)──► {confirmed:true, advanced:true}

FR-6 断点（两层写入）：
  交棒工具成功 ──► stampCheckpoint ──► 台账 req.interruption = {reason:"checkpoint", stage, pendingAction}
  回合结束       ──► CaptureHook 读 turn/end.data.reason
         ├─ completed / max-tokens / blocked ──► 不补写
         └─ aborted / error / interrupted ─────► 异步边界 → noteInterruption（覆盖 reason）
  续跑           ──► buildNodeInputPackage ──► 追加「## 断点」节（仅当字段存在）
```

## 错误语义 <!-- serves: FR-2, FR-3, FR-4, FR-7 -->

| 编号 | 错误码 / 情形 | 含义 | 调用方处置建议 |
|---|---|---|---|
| E-1 | `REQBOARD_ARTIFACT_NOT_OPENABLE` | `path` 是伪路径（brace/通配/空/越界） | 改用设计目录内的真实文件路径 |
| E-2 | `REQBOARD_FILE_MISSING` | `path` 文件不存在 | 先落盘再登记 |
| E-3 | `REQBOARD_MISSING_ARTIFACT` | 没有任何 `kind=design` 产物（登记 0 条） | 先 `reqboard_submit(kind=design)` |
| E-4 | `fallback=board` | 弹框通道不可用（subagent/无 UI） | 请用户到看板确认（语义不变） |
| E-5 | `REQBOARD_UNKNOWN_TICKET` | 回执 ticket 未知或已过期 | 改调 `reqboard_status` 查 `design_docs[].confirmed` |
| E-6 | `REQBOARD_WINDOW_BOUND` / `REQBOARD_INVALID_INPUT` | 重复立项 / `doc_location` 形态非法 | 见既有语义；`doc_location` 必须是工作区相对目录 |
| E-7 | `design_doc_incomplete`（未登记） | 磁盘上的设计文档在产物簿无此条 | 调 `reqboard_submit(kind=design)` |
| E-8 | `design_doc_incomplete`（待确认） | 已登记但无确认章 | 调 `reqboard_ask_confirm(target=artifact, kind=design)` |
| E-9 | 绑定层旧错误（应消失） | `binding arguments must be lossless JSON` | 修复后退化为正常返回；若复现=patch 未生效 |
| E-10 | 任意内容闸门 code（见 I-9） | 消息缺 `why` 或 `how` | 视为契约破坏：读 `gaps` 定位，并补测；`envelope()` 是唯一拼接入口 |

## 兼容性矩阵 <!-- serves: FR-1, FR-3, FR-4, FR-6, FR-7 -->

| 消费方 | 旧行为 | 新行为 | 兼容判据 |
|---|---|---|---|
| 既有 4 类 submit 调用方 | 4 个 kind | 5 个 kind（多 design） | 旧 kind 分支代码路径不变 |
| 旧客户端读 `reqboard_status` | 无 `design_docs` | 多一个可选字段 | 忽略即兼容（JSON 未知键） |
| 旧调用方等 `ask_confirm` | 阻塞到作答 | 宽限内阻塞、超宽限返回 pending | 作答快于宽限时返回体逐字一致 |
| 存量需求记录 | 无 `interruption` | 可选字段缺省即无断点节 | `isLegacy` 分支放行不变 |
| `reqboard_create` 调用方 | 无 `doc_location` | 缺省回落并留痕 | 不传时 `docBasePath` = 既有缺省值 |
