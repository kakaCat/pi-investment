# 复核报告 · REQ-260927123256-196b

> 复核对象：pm 确认弹框等待语义反转（缺省阻塞）整条交付面（t1 契约 + t2 阻塞 + t3 停手/投影 + t4 文案 + t5 测试 + t6 回归）。
> 复核方式：**只读复核 + 独立复跑 + 逐字比对**（不采信上游自述）。
> 复核窗口：session-b71bb246-6f5c-417b-89d6-e48e4b697dcf；时间：2026-09-27。
> 基线：`design/architecture.md`、`design/interfaces.md`（I-1～I-6）、`design/data-model.md`、`design/test-cases.md`（TC-1～TC-15）、`decomposition.md`。

## 0. 结论摘要

| 交付面 | 判定 | 依据 |
|---|---|---|
| t1 契约（interruptedAt / markInterrupted / pending-guard） | **无功能偏离**（R1–R12 全过） | `evidence/t-738238-review.md` 全量逐条 |
| t2 缺省阻塞 / 显式宽限逃生舱 / 中止留痕 | **无偏离** | I-1 行为矩阵逐行对齐，见 §1 |
| t3 停手守卫升级 + status 投影 | **无偏离** | I-2 / I-3 字段表与文案契约对齐，见 §2 |
| t4 文案与 tool schema | **无偏离** | I-5 锚点齐全，见 §3 |
| t5 测试固化 | **无偏离** | 8 文件 49 用例全绿，见 `tests/test-evidence.md` |
| t6 回归与文档同步 | **无偏离（1 处需人工留意：并发红项）** | 见 §4 / §5 |

## 1. t2 等待语义（I-1 行为矩阵逐行）

| I-1 行 | 设计 | 实现（`use-cases/AskConfirm.ts`） | 判定 |
|---|---|---|---|
| 缺省 × 任意 | 阻塞 `await ask`；resolve → 既有键（无 pending/ticket）；中止 → pending+ticket+interrupted | 缺省分支直接 `await ask`；resolve → `settleAnswers`；失败交 `handleAskFailure` | 无偏离 |
| 正数 × 已装配 | `raceAsk`；超时 pending+ticket（后台落章+唤醒） | `raceAsk(ask, graceRaw)` + `suspendConfirm`（消费已登记 ticket） | 无偏离 |
| 正数 × undefined | 拒绝 `REQBOARD_NONBLOCK_UNAVAILABLE` | 进入等待前显式 `reject` | 无偏离 |
| ≤0 / 非数 | 拒绝 `REQBOARD_INVALID_INPUT` | 0/-1 由用例 `reject`；非数由参数 schema 在绑定层拒绝（仍显式，不静默） | 无偏离（口径已写进测试注释） |
| 进入等待前 register | 阻塞/非阻塞共用；先 settle 旧记录 | `for(...pendingForWindow...)` settle 后 `register` | 无偏离（TC-10） |
| 中止 note 三要素 | 取回执命令 + 看板 + 不得产出下游产物 | `interruptedBody` note 三要素齐全（TC-7 断言） | 无偏离 |

## 2. t3 守卫与投影（I-2 / I-3）

- `assertNoPendingConfirm` 改用 `livePendingConfirm`（判定单点）；拒绝文案由 `pendingConfirmRejectMessage` 单点提供，含 ticket + 「收到作答前不得产出下游产物」+ 三条恢复路径（取回执 / 看板 / 重新发起）。TC-13 断言。
- `reqboard_status.pending_confirms` 逐字段与 I-2 一致（ticket / requirement_id / target / kind / created_at / interrupted / blocked_tools / recovery）；陈旧记录（台账已落章）被过滤 → 守卫不死锁（TC-9）。

## 3. t4 文案（I-5）

`ASK_CONFIRM_PROMPT` 含「缺省阻塞」「主动放弃阻塞」「REQBOARD_CONFIRM_PENDING」；
`inline_grace_ms` 参数 description 含「缺省」「阻塞」；`ConfirmReceiptTool` 提示词点名 `reqboard_confirm_receipt` 并补「被中止的挂起记录同样可凭 ticket 查询」。
工具 `output.schema` 声明 `interrupted`（output-contract 静态扫描对 defineAskConfirmTool 已通过）。

## 4. 兼容性（FR-6）

- `PendingConfirmationOutcome` 仍 4 键；`contract-shapes.test.ts` 通过。
- 已确认早返回、`fallback=board`、evidence 路径在 `ask-confirm.test.ts` / `output-contract.test.ts` 中运行通过（除下述并发红项）。
- 持久化零变更：挂起记录为内存态；`.dsh-data/dsh-reqboard.json` 为 gitignore 运行时台账，无 schema 字段新增。

## 5. 观察项（不阻断验收）

- **O-1 并发红项**：本工作区同时存在其它窗口未提交改动，导致 `ask-confirm.test.ts`「闸门问题卡」1 条、`output-contract.test.ts` 4 条（Advance/ClearPause/RunStatus/TaskMove）、`message-hygiene.test.ts` 1 条在**本节点动手前**即已红；目标文件均不在本需求交付面。以 2026-09-27 14:16 基线复跑为证。
- **D-1（t1 复核遗留）**：回执文案在「已落章 + interruptedAt」组合态下按「台账优先」，设计 I-6/T-1 未显式裁定；不阻断，建议设计补一句。详见 `evidence/t-738238-review.md` §2。
- **D-2（t1 复核遗留，已随 t5 关闭）**：`contract-shapes.test.ts` 的 `PendingConfirmation` 精确形状断言与端口 5 方法断言已由 t5 更新（新增 `interruptedAt?: number` 与 `markInterrupted`），本复核复跑 8/8 通过。
- **O-1（t1 复核遗留）**：端口注释泛化（markInterrupted 不做过期判定）——与设计 I-4 不冲突，不阻断。

## 6. 复核证据（命令与输出）

```
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/{ask-confirm-blocking,ask-confirm-pending,pending-guard,confirm-pending-guard,status-pending-confirm,ask-confirm-prompt,contract-shapes,tools-schema}.test.ts
 Test Files  8 passed (8)
      Tests  49 passed (49)

$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard-integration.test.ts
 Test Files  1 passed (1)
      Tests  7 passed (7)
```

复核人：实施窗口 agent（session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）；时间：2026-09-27
