---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8]
---

# 测试用例（REQ-260924213231-b1c4）

> 读者：工程 / agent。本文只写「要测什么」；执行证据（命令 + 输出）在实施节点写 test-evidence.md。
> 「被测对象」引用设计编号：interfaces（I-x）/ data-model（T-x）/ use-cases（UC-x）。
> **测试文件落点**表列出的每个文件，头部 20 行内必须带 `// serves: FR-x`（否则验收时计入孤儿用例）。

## 覆盖矩阵 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| 功能点 | 单元 | 集成 | 故障注入 | 回归 |
|---|---|---|---|---|
| FR-1 登记入口 + 逐份态 | ✅ | ✅ | ✅ | ✅ |
| FR-2 闸门文案分化 | ✅ | ✅ | ✅ | ✅ |
| FR-3 弹框非阻塞 + 回执 | ✅ | ✅ | ✅ | ✅ |
| FR-4 零参绑定 | ✅ | ✅ | ✅ | — |
| FR-5 提示词登记说明 | ✅（基线） | — | — | ✅ |
| FR-6 断点留痕 | ✅ | ✅ | ✅ | ✅ |
| FR-7 文档位置不丢 | ✅ | ✅ | — | ✅ |
| FR-8 pm 弹框来源标志 | ✅ | ✅ | — | ✅ |

## 用例表 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| 用例 | 类型 | 被测对象 | 前置条件 | 步骤 | 预期结果 | serves |
|---|---|---|---|---|---|---|
| TC-1 | 正向 | I-1 / T-2 | 5 份 design/*.md 已落盘、artifacts 为空 | 调 `reqboard_submit(kind=design)` 两次 | 首次 `registered_count=5` 且 5 条 kind=design 入簿；二次 `registered_count=0`（幂等） | FR-1 |
| TC-2 | 反向 | I-9 | 文档落盘但未登记 | 调 `reqboard_move(to=decomposing)` | 抛错消息含「未登记」与 `reqboard_submit(kind=design)` | FR-2 |
| TC-3 | 正向 | I-9 | 已登记、无 confirmedAt | 同上 | 抛错消息含「待确认」与 `reqboard_ask_confirm` | FR-2 |
| TC-4 | 反向 | I-3 | 全部 design 产物已落章，磁盘多出一份未登记 | 调 `reqboard_ask_confirm(kind=design)` | 返回 `confirmed=true, advanced=false` 且 `gate_failure.gaps` 点名未登记件 | FR-2 |
| TC-5 | 边界 | I-3 / T-4 | 弹框通道可用、作答永不返回 | 调 `reqboard_ask_confirm`，等待超过宽限 | 返回 `pending=true, ticket`，**不抛、不判失败** | FR-3 |
| TC-6 | 正向 | I-3 | 弹框立即作答肯定项 | 调 `reqboard_ask_confirm` | `confirmed=true, advanced=true`（旧语义逐字回归） | FR-3 |
| TC-7 | 正向 | I-4 | TC-5 产生 ticket，随后作答 | 调 `reqboard_confirm_receipt(ticket)` | `confirmed=true, advanced=true`，台账 confirmedAt 已写 | FR-3 |
| TC-8 | 反向 | I-4 | 无对应 ticket | 调 `reqboard_confirm_receipt('pc-无')` | 抛 `REQBOARD_UNKNOWN_TICKET` | FR-3 |
| TC-9 | 正向 | I-5 | ptc runtime 绑定已打 patch | 运行只调 `tools.reqboard_status()`（零参）的 run_code 脚本 | 正常返回值，无 `binding arguments must be lossless JSON` | FR-4 |
| TC-10 | 回归 | I-7 | 分片内联与 P1 基线已更新 | 解析 design/light + design/heavy 提示词 | 文本含 `reqboard_submit(kind=design)` 且不含「落盘即产物」旧断言 | FR-5 |
| TC-11 | 正向 | I-6 / T-5 | 本窗口未绑定需求 | 调 `reqboard_create` 不传 `doc_location` | 返回含 `doc_location=docs/requirements/<REQ>/`、`defaults_used` 含 doc_location | FR-7 |
| TC-12 | 正向 | I-6 / T-5 | 同上 | 调 `reqboard_create(doc_location='docs/rfcs/')` | 台账 `docBasePath='docs/rfcs/'`；后续文档路径按它生成 | FR-7 |
| TC-13 | 正向 | I-6 | 同上 | 调 `reqboard_create` | 返回 `status='brainstorming'`（或如实 draft + 未推进说明），与台账一致 | FR-7 |
| TC-14 | 边界 | I-7 | 弹框通道可用 | 触发 ask_confirm / accept_sheet / capture 三处弹框 | 三者 `header` 均以 `📋 PM · ` 开头；宿主 ask_user_question 不带该前缀 | FR-8 |
| TC-15 | 正向 | T-1 / UC-6 | 需求处于 design、已写断点 | 调 `reqboard_note_interruption('upstream stream idle')` 后重建节点输入包 | 返回含 interruption；输入包出现「## 断点」节与 pendingAction | FR-6 |
| TC-16 | 边界 | T-1 | 老需求无 interruption 字段 | 重建节点输入包 | 不出现断点节，其余节逐字不变 | FR-6 |
| TC-17 | 故障注入 | I-9 | design/*.md 含 `depends_on` 表头 | 调 `reqboard_ask_confirm(kind=design)` | 仍被 `design_contains_decomposition` 拒（护栏未因本次改动放松） | FR-5 |
| TC-18 | 故障注入 | I-3 | 伪造 evidence 的文字确认路径 | 调 `reqboard_ask_confirm(evidence='用户确认')` | 仍被 `REQBOARD_EVIDENCE_FAKE` 拒 | FR-2 |
| TC-19 | E2E | UC-1 / UC-2 / UC-3 | 新建 feature 测试需求，agent 只调工具 | 落盘 5 份 design → `reqboard_submit(kind=design)` → `reqboard_ask_confirm(kind=design)` → `reqboard_move(to=decomposing)` | 一次通过，全程不出现 `REQBOARD_MISSING_ARTIFACT`（A1） | FR-1 |
| TC-20 | 反向 | I-3 | design 产物已全部落章 | 再次调 `reqboard_ask_confirm(kind=design)` | 返回「已确认，未重复弹框」且不再抛错（既有语义不回归） | FR-3 |
| TC-21 | 单元 | I-9 | 全部 `GateFailure` 构造点 | 逐 `code` 构造拒绝并读 `message` | 每条 message 含 `——`（why）与 `补齐：`（how）；how 段命中 `reqboard_*` / `templates/` / `design_exempt` 锚点 | FR-2 |
| TC-22 | 集成 | I-9 | 构造 `design_orphan`（章节缺 serves）与 `REQBOARD_MISSING_REQUIRED_DOC` | 分别调 `reqboard_submit(kind=plan)` | 两条消息各自给出「补 serves：FR-#」与「按 templates/design 生成或 design_exempt」的可复制补齐指引 | FR-2 |

## 用例明细 <!-- serves: FR-1, FR-3, FR-6 -->

**TC-1 登记幂等（示例展开）**

- 测试数据：临时目录 + 5 个文件 `architecture.md / data-model.md / interfaces.md / test-cases.md / use-cases.md`，台账 `artifacts: []`
- 步骤：1. 调工具；2. 读台账 artifacts；3. 再调一次
- 断言点：① 首次返回 `registered_count === 5`；② 台账中 `kind==='design'` 条目数为 5；③ 二次返回 `registered_count === 0` 且条目数仍为 5
- 清理：删除临时目录

**TC-5 超宽限挂起（示例展开）**

- 测试数据：`questions.ask = () => new Promise(() => {})`（永不 resolve），宽限注入为 20ms
- 步骤：1. 调 `reqboard_ask_confirm`；2. 断言返回；3. resolve 一次作答后读台账
- 断言点：① 返回体 `pending === true` 且 `ticket` 非空；② 调用**未抛错**；③ 作答后台账对应产物 `confirmedAt` 已写
- 清理：清空挂起注册表

**TC-15 断点续跑（示例展开）**

- 测试数据：需求 `status='design'`，`artifacts` 有 1 条未确认 design 产物
- 步骤：1. 交棒一次（触发写入器 A 的 `stampCheckpoint`）；2. 喂一条 `turn/end` 事件给 `CaptureHook`，「事件数据」= `{ turn: 1, reason: { kind: 'error', error: { code: 'UPSTREAM_STREAM_IDLE', message: 'upstream stream idle 3m' } } }`；3. 驱动组合根注册的异步边界回调；4. `buildNodeInputPackage`
- 断言点：① 断言 A：交棒后台账 `req.interruption.reason === "checkpoint"` 且 `pendingAction` 非空；② 断言 B：事件驱动后台账 `reason` 变为 `"error:UPSTREAM_STREAM_IDLE:upstream stream idle 3m"`；③ 输入包含 `## 断点`；④ 输入包含 `upstream stream idle`；⑤ 输入包含 `pendingAction` 文本
- 清理：无（临时目录另有 TC-1 覆盖）

**TC-15b `turnEndOutcome` 值域（示例展开，纯函数单测）**

- 测试数据：六组 `turn/end.data`：`completed` / `max-tokens` / `blocked` / `aborted` / `interrupted` / `error`；另加 `{}`、`{reason:{}}` 两个畸形
- 步骤：逐组调 `turnEndOutcome(data)`
- 断言点：① 前三组 `abnormal === false`；② `aborted`/`interrupted`/`error` 三组 `abnormal === true` 且 `reason` 前缀分别为 `aborted:` / `interrupted` / `error:`；③ 畸形两组返回 `undefined`（不猜、不抛）
- 清理：无

**TC-21 拒绝信封三要素（示例展开）**

- 测试数据：`design_doc_incomplete`（未登记/待确认两态）、`design_orphan`、`dangling_reference`、`REQBOARD_MISSING_REQUIRED_DOC`、`design_contains_decomposition` 各一组 fixture
- 步骤：逐个构造 `GateFailure` → 读 `message`
- 断言点：① 每条 `message` 同时含 `——` 与 `补齐：`；② `补齐：` 之后命中 `/reqboard_[a-z_]+/` 或 `templates/` 或 `design_exempt`；③ `code` 与 `gaps` 未因本改动变化（护栏强度不降）
- 清理：无
## 故障注入 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-6 -->

| 注入点（挂 I-x/T-x 编号） | 注入方式 | 预期行为 | 实测结果（实施时回填） |
|---|---|---|---|
| I-5 绑定层 | 只传零参调用 `tools.reqboard_status()` | 正常返回（缺省 `{}`） | 待回填 |
| I-3 弹框 | `questions.ask` 永不 resolve | 返回 pending+ticket，不抛 | 待回填 |
| I-3 弹框 | `questions.ask` 抛 `ASK_ABORTED` | 中性返回（节点未推进），语义同现状 | 待回填 |
| I-9 G2 闸门 | 产物簿缺条目 / 缺 confirmedAt | 两种文案、两个命令 | 待回填 |
| T-1 断点（A） | 只交棒不喂事件 | 台账已有 `reason="checkpoint"` + `pendingAction` | 待回填 |
| T-1 断点（B） | 喂 `turn/end` 且 `reason.kind='error'`（含 `LlmFailure`） | 台账 `reason` 变为 `error:<code>:<message>` | 待回填 |
| T-1 断点（B-反例） | 喂 `turn/end` 且 `reason.kind='completed'` | 不覆盖 `checkpoint`（无副作用） | 待回填 |
| T-1 断点（B-畸形态） | 喂 `{}` / `{reason:{}}` | 不写、不抛（`turnEndOutcome` 返回 undefined） | 待回填 |
| T-1 输入包 | 有 / 无 `interruption` 两种需求 | 有→追加「## 断点」；无→输出逐字节不变 | 待回填 |
| I-1 登记 | 设计目录不存在 / 无 .md | `registered_count=0` + 如实说明，不谎报 | 待回填 |

## 测试文件落点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

| 用例 | 实际文件 | serves |
|---|---|---|
| TC-1, TC-19 | packages/web/dsh-pmboard/tests/design-registration.test.ts | FR-1 |
| TC-2, TC-3, TC-4 | packages/web/dsh-pmboard/tests/design-gate-messages.test.ts | FR-2 |
| TC-5, TC-6, TC-7, TC-8, TC-20 | packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts | FR-3 |
| TC-9 | packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts | FR-4 |
| TC-10, TC-17 | packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts | FR-5 |
| TC-15, TC-16 | packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts | FR-6 |
| TC-11, TC-12, TC-13 | packages/web/dsh-pmboard/tests/create-doc-location.test.ts | FR-7 |
| TC-14 | packages/web/dsh-pmboard/tests/pm-question-badge.test.ts | FR-8 |
| TC-18 | packages/web/dsh-pmboard/tests/confirm-evidence.test.ts | FR-2 |
| TC-21, TC-22 | packages/web/dsh-pmboard/tests/gate-feedback-envelope.test.ts | FR-2 |
| TC-19 | packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts | FR-1 |