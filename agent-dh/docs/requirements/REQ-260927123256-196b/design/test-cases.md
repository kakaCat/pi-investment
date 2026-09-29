---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
---

# 测试用例（REQ-260927123256-196b）

> 读者：工程 / agent。本文只写「要测什么」；执行证据（命令 + 输出）在实施节点写 test-evidence.md。
> 「被测对象」引用设计编号：interfaces（I-x）/ data-model（T-x）/ use-cases（UC-x）。
> 测试文件落点表列出的每个文件，头部 20 行内必须带 `// serves: FR-x`（否则验收时计入孤儿用例）。

## 覆盖矩阵 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->

| 功能点 | 单元 | 集成 | 故障注入 | 回归 |
|---|---|---|---|---|
| FR-1 缺省阻塞 | ✅ | ✅ | ✅ | ✅ |
| FR-2 阻塞期停手守卫 | ✅ | ✅ | ✅ | ✅ |
| FR-3 显式宽限逃生舱 | ✅ | ✅ | ✅ | ✅ |
| FR-4 中止响亮可续 | ✅ | ✅ | ✅ | ✅ |
| FR-5 提示词与工具描述 | ✅（文案） | — | — | ✅ |
| FR-6 兼容性不退化 | ✅ | ✅ | — | ✅ |

## 用例表 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->

| 用例 | 类型 | 被测对象 | 前置条件 | 步骤 | 预期结果 | serves |
|---|---|---|---|---|---|---|
| TC-1 | 正向 | I-1 / UC-1 | `questions.ask` 返回永不 resolve 的 promise；**不传** `inline_grace_ms` | 调 `reqboard_ask_confirm`，与 200ms 定时器赛跑 | 200ms 时该 promise **仍未 settle**；随后 resolve(`确认推进`) → 返回 `confirmed:true, advanced:true`，且**无** `pending`/`ticket` 键 | FR-1 |
| TC-2 | 正向 | T-1 / I-3 | 同上；注册表已装配 | 阻塞中 `await` 前先 `pendingForWindow(W)`；作答后再查 | 阻塞中查到未作答记录；作答并返回后 `pendingForWindow(W) === undefined`（守卫释放） | FR-1 |
| TC-3 | 反向 | I-1 | 任意 deps | 传 `inline_grace_ms: 0` / `-1` / `"20"` | 抛 `REQBOARD_INVALID_INPUT`（不静默回落） | FR-3 |
| TC-4 | 边界 | I-1 / UC-2 | `ask` 永不 resolve；`pendingConfirms` 已装配 | 传 `inline_grace_ms: 20` 调工具 | 返回 `success:true, confirmed:false, pending:true` 且 `ticket` 以 `pc-` 开头；调用不抛错 | FR-3 |
| TC-5 | 反向 | I-1 / E-2 | `deps.pendingConfirms === undefined` | 传 `inline_grace_ms: 20` 调工具 | 抛 `REQBOARD_NONBLOCK_UNAVAILABLE`（**不**变成阻塞、也不忽略宽限） | FR-3 |
| TC-6 | 反向 | I-3 / UC-1 | 缺省阻塞进行中（登记了未作答记录） | 在 `ask` 未 resolve 时调 `reqboard_submit` / `reqboard_move` / `reqboard_task_move` / `reqboard_decompose` | 四者均抛 `REQBOARD_CONFIRM_PENDING`；台账**零写入**；`reqboard_status` 仍可用 | FR-2 |
| TC-7 | 故障注入 | I-1 / I-2 / UC-3 | `ask` 以 `ASK_ABORTED`（且 `signal.aborted === true`）拒绝 | 调工具；再调 `reqboard_status`；再调写工具 | 返回体 `pending:true + ticket + interrupted:true`；`status.pending_confirms` 含该 ticket 且 `interrupted===true`；写工具仍被拒 | FR-4 |
| TC-8 | 正向 | I-1 / I-3 / UC-4 | `ask` 以 `ASK_CANCELLED` 拒绝 | 调工具；查询注册表；调写工具 | 返回体 `confirmed:false, advanced:false` 且**无** `pending`/`ticket`；`pendingForWindow(W) === undefined`；写工具放行；台账无 `confirmedAt` | FR-1, FR-6 |
| TC-9 | 正向 | I-2 / I-3 / T-3 | 存在中止留下的未作答记录；台账目标已写 `confirmedAt`（或 `plan.approvedAt`） | 调 `assertNoPendingConfirm(W)`；调 `reqboard_status` | 守卫**放行**（不抛）；`status.pending_confirms` 不再列该陈旧记录 | FR-4 |
| TC-10 | 正向 | UC-5 | 本窗口已有一条未作答记录 | 再次调 `reqboard_ask_confirm`（新 `ask` 立即作答） | 旧记录被 settle 为未确认；`pendingForWindow` 只反映新 ticket；新确认正常落章 | FR-4 |
| TC-11 | 单元 | I-5 | — | 读 `ASK_CONFIRM_PROMPT` 与 `inline_grace_ms` 参数 description | 文本含「缺省阻塞」；说明显式宽限 = 主动放弃阻塞、超时后 loop 继续跑 | FR-5 |
| TC-12 | 回归 | I-1 / I-6 | 既有确认链路（`ask` 立即作答、已确认早返回、`fallback=board`、evidence 路径） | 跑 `tests/ask-confirm.test.ts` + `tests/output-contract.test.ts` | 全绿；`ask_confirm` 所有 return 分支键都在 `output.schema` 声明（含新增 `interrupted`） | FR-6 |
| TC-13 | 回归 | I-3 | 既有守卫用例（手工 register + 跨窗口 + 已作答） | 跑 `tests/confirm-pending-guard.test.ts` | 全绿；拒绝消息含 ticket、`收到作答前不得产出下游产物` 与两条取回路径 | FR-2, FR-6 |
| TC-14 | 回归 | I-4 / I-6 | 端口形状断言与回执契约 | 跑 `tests/contract-shapes.test.ts` + `tests/confirm-receipt.test.ts` | `PendingConfirmationOutcome` 仍为 4 键（`expectTypeOf` 保留）；`PendingConfirmPort` 形状更新为 `register/get/settle/pendingForWindow/markInterrupted`；回执链路全绿 | FR-6 |
| TC-15 | 单元 | I-4 / T-1 | 注册表注入固定 `now` | `markInterrupted(ticket)` 两次；再查 `get` / `pendingForWindow` | 幂等（`interruptedAt` 只写首次）；过期基准 = `interruptedAt + ttl`（`createdAt` 早于中止也不提前失效） | FR-4 |

## 用例明细 <!-- serves: FR-1, FR-3, FR-4 -->

**TC-1 缺省阻塞（示例展开）**

- 测试数据：`ask = () => new Promise(() => {})`；`makeDeps` 装配 `PendingConfirmRegistry`
- 步骤：1. 启动 `tool.execute({ target:'artifact', kind:'requirement', question:'…' }, exec)`，**不传** `inline_grace_ms`；
  2. `await Promise.race([p, sleep(200).then(() => 'still-pending')])`；3. 让 `ask` resolve 一次 `确认推进`
- 断言点：① 第 2 步结果为 `'still-pending'`（旧实现在 30s 后返回 `pending`，本用例在观测窗内即可证伪）；
  ② 第 3 步返回 `confirmed === true`、`advanced === true`；③ 返回体不含 `pending`/`ticket` 键
- 清理：临时目录

**TC-7 中止留痕（示例展开）**

- 测试数据：`ask = () => Promise.reject(Object.assign(new Error('aborted'), { code: 'ASK_ABORTED' }))`；
  `exec.signal = { aborted: true }`
- 步骤：1. 调工具；2. `reqboard_status`；3. `assertNoPendingConfirm(W)`
- 断言点：① 返回 `pending === true`、`interrupted === true`、`ticket` 非空；
  ② `pending_confirms[0].interrupted === true` 且 `recovery` 含 `reqboard_confirm_receipt` 与「看板」；
  ③ 第 3 步抛 `REQBOARD_CONFIRM_PENDING`
- 清理：清空注册表

**TC-9 台账落章即解除（示例展开）**

- 测试数据：注册表内一条未作答记录（`target:'artifact', kind:'requirement'`）；台账需求该产物 `confirmedAt = 1`
- 步骤：1. `livePendingConfirm(deps, W)`；2. `assertNoPendingConfirm(deps, W)`
- 断言点：① 返回 `undefined`（陈旧记录被过滤）；② 不抛错
- 清理：无

## 故障注入 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-6 -->

| 注入点（挂 I-x / T-x 编号） | 注入方式 | 预期行为 | 实测结果（实施时回填） |
|---|---|---|---|
| I-1 缺省阻塞 | `ask` 永不 resolve、不传宽限 | 观测窗内不返回；resolve 后返回同步体 | 待回填 |
| I-1 显式宽限 | `ask` 永不 resolve + `inline_grace_ms: 20` | 返回 `pending + ticket`，不抛 | 待回填 |
| I-1 能力未装配 | 正数宽限 + `pendingConfirms` 缺省 | 抛 `REQBOARD_NONBLOCK_UNAVAILABLE` | 待回填 |
| I-1 中止 | `ask` 拒绝 `ASK_ABORTED` | `interrupted:true` + 记录保留 | 待回填 |
| I-1 取消 | `ask` 拒绝 `ASK_CANCELLED` | 中性返回、记录 settle、守卫放行 | 待回填 |
| I-2 status | 有 / 无挂起记录 | 有→列 `pending_confirms`；无→不出现该键/空数组 | 待回填 |
| I-3 守卫 | 未作答 + 台账未落章 | 写路径被拒且不写盘 | 待回填 |
| I-3 守卫解除 | 未作答 + 台账已落章 | 放行（不死锁） | 待回填 |
| I-4 注册表 | 未知 ticket 调 `markInterrupted` | 返回 undefined，不抛 | 待回填 |

## 测试文件落点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6 -->

| 用例 | 实际文件 | serves |
|---|---|---|
| TC-1, TC-2, TC-7, TC-8, TC-10 | packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts（新增） | FR-1, FR-4 |
| TC-3, TC-4, TC-5, TC-15 | packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts（按新语义更新：删除「不传宽限=旧阻塞」用例，新增 TC-5） | FR-3, FR-4 |
| TC-6, TC-9, TC-13 | packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts（扩展） | FR-2, FR-4 |
| TC-7 status 投影 | packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts（新增） | FR-4 |
| TC-11 | packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts（新增） | FR-5 |
| TC-12 | packages/web/dsh-pmboard/tests/ask-confirm.test.ts、packages/web/dsh-pmboard/tests/output-contract.test.ts | FR-6 |
| TC-14 | packages/web/dsh-pmboard/tests/contract-shapes.test.ts、packages/web/dsh-pmboard/tests/confirm-receipt.test.ts | FR-6 |
| TC-12 schema | packages/web/dsh-pmboard/tests/tools-schema.test.ts（补 `defineAskConfirmTool` 构造断言） | FR-6 |
