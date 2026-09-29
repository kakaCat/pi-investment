# 拆分计划（REQ-260927123256-196b）

> 目标：确认门弹框一旦出现，**人不作答，agent 就不得再往下走一步**——与原生 `ask_user_question` 的等待语义一致。
> 做法：`AskConfirm` 缺省 `await` 阻塞（删除 30s 自动放行），显式 `inline_grace_ms` 才走非阻塞逃生舱；
> 阻塞前先登记挂起 ticket，让「阻塞期停手守卫」与「中止后仍可查/可续」成为代码级事实。
> 设计依据：`design/architecture.md`、`design/interfaces.md`、`design/data-model.md`、`design/test-cases.md`、`design/use-cases.md`。

## §1 改动盘点

### 新增

| 文件 | 用途 | serves |
|---|---|---|
| `src/application/internal/pending-guard.ts` | 共享谓词 `targetConfirmedInLedger` / `livePendingConfirm` + 被拦写路径常量 + 恢复文案 | FR-2, FR-4 |
| `tests/ask-confirm-blocking.test.ts` | 缺省阻塞、作答释放、中止留痕、取消中性、重新发起覆盖 | FR-1, FR-4 |
| `tests/status-pending-confirm.test.ts` | `reqboard_status.pending_confirms` 投影与陈旧记录过滤 | FR-4 |
| `tests/ask-confirm-prompt.test.ts` | 工具描述/参数说明的「缺省阻塞」文案契约 | FR-5 |
| `tests/pending-guard.test.ts` | `targetConfirmedInLedger` / `livePendingConfirm` / `markInterrupted` 单测 | FR-2, FR-4 |

### 修改

| 文件 | 改动 | serves |
|---|---|---|
| `src/application/use-cases/AskConfirm.ts` | 编排重写：缺省阻塞分支、显式宽限分支、中止分支；进入等待前 supersede + register | FR-1, FR-3, FR-4 |
| `src/application/internal/pending-confirm.ts` | `suspendConfirm` 接收已登记 ticket（不二次 register）；导出 `outcomeOf` | FR-3 |
| `src/application/internal/support.ts` | `assertNoPendingConfirm` 改用 `livePendingConfirm`；拒绝文案补第三条恢复路径 | FR-2 |
| `src/application/use-cases/ConfirmReceipt.ts` | 复用共享谓词；`interruptedAt` 存在时回执文案区分「被中止」 | FR-4, FR-6 |
| `src/application/query/QueryState.ts` | 返回体增 `pending_confirms` 投影 | FR-4 |
| `src/tools/StatusTool/StatusTool.ts` | `output.schema` 声明 `pending_confirms` | FR-4 |
| `src/tools/AskConfirmTool/AskConfirmTool.ts` | 声明 `interrupted` 键；改 `inline_grace_ms` 参数说明 | FR-4, FR-5 |
| `src/tools/AskConfirmTool/prompt.ts` | 工具描述写明「缺省阻塞；显式宽限 = 主动放弃阻塞」 | FR-5 |
| `src/tools/ConfirmReceiptTool/prompt.ts` | 补「被中止的挂起记录同样可凭 ticket 查询」 | FR-5 |
| `src/domain/limits.ts` | 删除 `confirmInlineGraceMs` | FR-1 |
| `src/adapters/PendingConfirmRegistry.ts` | 实现 `markInterrupted`；过期基准改 `(interruptedAt ?? createdAt) + ttlMs` | FR-4 |
| `src/application/ports.ts` | `PendingConfirmPort` 增 `markInterrupted` | FR-4 |
| `src/shared/protocol.ts` | `PendingConfirmation` 增可选 `interruptedAt` | FR-4 |
| `tests/ask-confirm-pending.test.ts` | 删除「不传宽限 = 旧阻塞」用例；新增「能力未装配 + 正数宽限 → 拒绝」 | FR-3 |
| `tests/confirm-pending-guard.test.ts` | 补「阻塞登记的未作答记录拦写」与「台账已落章即解除」 | FR-2, FR-4 |
| `tests/contract-shapes.test.ts` | `PendingConfirmPort` 形状断言更新为 5 方法（`PendingConfirmationOutcome` 保持 4 键） | FR-6 |
| `tests/tools-schema.test.ts` | 补 `defineAskConfirmTool` 构造断言（新键编译通过） | FR-6 |
| `agent-dh/docs/architecture/reqboard-pipeline-flow.md` | G1/G2「非阻塞投递：30s 宽限」改写为「缺省阻塞；仅显式宽限走逃生舱」 | FR-5 |

### 删除

| 符号 | 原用途 | 替代 |
|---|---|---|
| `LIMITS.confirmInlineGraceMs`（30_000） | 缺省宽限窗口（「到点自动放行」的唯一来源） | 无缺省；显式 `inline_grace_ms` 才启用非阻塞 |
| `ConfirmReceipt.ts` 私有 `confirmedInLedger` | 回执的台账落章判定 | 提取为 `pending-guard.targetConfirmedInLedger`（守卫与回执共用同一谓词） |

### 不改动（边界）

- `reqboard_capture` / `reqboard_accept_sheet` 的阻塞语义不动。
- DSH 宿主与客户端弹框通道、原生 `ask_user_question` 语义不动。
- Dive 投递路径不动。
- 持久化台账 schema 零变更（挂起记录为内存态）。

## §2 任务表

> 依赖按表内顺序解析；被依赖任务必须排在其之前（禁止前向引用）。

| key | 标题 | phase | side | 依赖 | 实施方案（implementation） | 验收标准（acceptance） |
|---|---|---|---|---|---|---|
| t1 | 先定契约：挂起确认能标出「被中止」，判定口径只留一处 | implement | backend | - | ① `src/shared/protocol.ts`：`PendingConfirmation` 增可选 `interruptedAt?: number`。② `src/application/ports.ts`：`PendingConfirmPort` 增 `markInterrupted(ticket): PendingConfirmation \| undefined`（不抛）。③ `src/adapters/PendingConfirmRegistry.ts`：实现 `markInterrupted`（幂等，只写首次）；`get`/`pendingForWindow` 过期基准改 `(interruptedAt ?? createdAt) + ttlMs`。④ 新增 `src/application/internal/pending-guard.ts`：从 `ConfirmReceipt.ts:76-80` 逐字提取 `targetConfirmedInLedger`，并实现 `livePendingConfirm(deps, windowKey)`（过滤已 settle / 已过期 / 台账已落章）+ `PENDING_CONFIRM_BLOCKED_TOOLS` + 恢复文案常量。⑤ `src/application/use-cases/ConfirmReceipt.ts`：删私有谓词、改用共享谓词，`interruptedAt` 且未作答时改文案。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts` 全绿：`targetConfirmedInLedger` 对 plan（`approvedAt` 已写）与 artifact（该 kind 成组 `confirmedAt` 已写）分别返回 true、未落章返回 false；`markInterrupted` 二次调用后 `interruptedAt` 不变；`createdAt` 早于中止时间时记录不提前过期。 |
| t2 | 确认弹框改为阻塞等待：人不作答，agent 就停在这一步 | implement | backend | t1 | ① `src/application/use-cases/AskConfirm.ts`：`graceRaw === undefined` → 先 settle 本窗口旧未作答记录、`register` ticket、`await ask`（try/catch）；resolve → `settleAnswers` + `settle(ticket)`；`ASK_CANCELLED` → `settle` + `degradedAnswer`；`ASK_ABORTED`/`exec.signal.aborted` → `markInterrupted` + 返回 `{success:false, confirmed:false, advanced:false, pending:true, ticket, requirement_id, interrupted:true, note}`。② `graceRaw` 正数 → 未装配 `pendingConfirms` 时 `reject('...','REQBOARD_NONBLOCK_UNAVAILABLE')`；`raceAsk` 三分支（timeout 走 `suspendConfirm`）。③ `src/application/internal/pending-confirm.ts`：`suspendConfirm` 改为接收已登记 ticket；导出 `outcomeOf`。④ `src/domain/limits.ts`：删除 `confirmInlineGraceMs`。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm.test.ts` 全绿：不传宽限 + `ask` 永不 resolve 时工具 200ms 仍未返回，resolve(`确认推进`) 后返回 `confirmed=true, advanced=true` 且返回体无 `pending`/`ticket` 键；显式 `inline_grace_ms: 20` 返回 `pending=true` 与 `pc-` 前缀 ticket。 |
| t3 | 等待期间不许偷偷往下走，状态页能看出在等谁 | implement | backend | t1 | ① `src/application/internal/support.ts`：`assertNoPendingConfirm` 改用 `livePendingConfirm`，拒绝消息含 ticket、「收到作答前不得产出下游产物」与三条恢复路径（取回执 / 看板确认 / 重新发起）。② `src/application/query/QueryState.ts`：返回体增 `pending_confirms`（字段见 `design/interfaces.md` I-2）。③ `src/tools/StatusTool/StatusTool.ts`：`output.schema` 声明 `pending_confirms`。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts` 全绿：阻塞登记的未作答记录使 `reqboard_submit/move/task_move/decompose` 抛 `REQBOARD_CONFIRM_PENDING` 且台账零写入；`reqboard_status` 返回 `pending_confirms[0].ticket`；台账落章后该数组为空。 |
| t4 | 工具说明写清「默认会等你」：显式宽限等于主动放弃等待 | doc | doc | t2 | ① `src/tools/AskConfirmTool/prompt.ts`：`ASK_CONFIRM_PROMPT` 写明弹框路径缺省阻塞、`inline_grace_ms` = 主动放弃阻塞且须自担超时后 loop 继续的后果。② `src/tools/AskConfirmTool/AskConfirmTool.ts`：`inline_grace_ms` 参数 description 同步。③ `src/tools/ConfirmReceiptTool/prompt.ts`：补被中止记录可凭 ticket 查询。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts` 全绿：`ASK_CONFIRM_PROMPT` 文本含「缺省阻塞」，参数 description 含「缺省」与「阻塞」；`defineAskConfirmTool` 构造（含新 `interrupted` 键）不抛 schema 编译错误。 |
| t5 | 把等待语义的每条分支都钉成测试 | test | backend | t2, t3, t4 | 新增 `tests/ask-confirm-blocking.test.ts`（TC-1/2/7/8/10）、`tests/pending-guard.test.ts`（TC-15）、`tests/status-pending-confirm.test.ts`（TC-7 投影）、`tests/ask-confirm-prompt.test.ts`（TC-11）；更新 `tests/ask-confirm-pending.test.ts`（TC-3/4/5）、`tests/confirm-pending-guard.test.ts`（TC-6/9/13）、`tests/contract-shapes.test.ts`（TC-14）、`tests/tools-schema.test.ts`（TC-12）。每个新文件头部 20 行内写 `// serves: FR-x`。用例口径逐条对齐 `design/test-cases.md`。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm-blocking.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts packages/web/dsh-pmboard/tests/status-pending-confirm.test.ts packages/web/dsh-pmboard/tests/ask-confirm-prompt.test.ts packages/web/dsh-pmboard/tests/contract-shapes.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts` 全绿（0 failed）。 |
| t6 | 老调用方与既有确认链路不回退，流程文档同步 | test | fullstack | t5 | ① 跑完整既有回归集（`ask-confirm.test.ts` / `ask-confirm-pending.test.ts` / `confirm-receipt.test.ts` / `confirm-pending-guard.test.ts` / `output-contract.test.ts` / `contract-shapes.test.ts` / `tools-schema.test.ts`），确认「已确认早返回、`fallback=board`、evidence 路径、`PendingConfirmationOutcome` 4 键」逐字不变。② 更新 `agent-dh/docs/architecture/reqboard-pipeline-flow.md` 的 G1/G2 步骤描述。③ 核对持久化零变更与回滚路径（回退插件构建即可，无数据迁移）。 | `cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/ask-confirm.test.ts packages/web/dsh-pmboard/tests/confirm-receipt.test.ts packages/web/dsh-pmboard/tests/output-contract.test.ts` 全绿；`grep -rn "非阻塞投递：30s" agent-dh/docs/architecture/reqboard-pipeline-flow.md` 无输出（旧表述已删）；`git diff -- agent-dh/.dsh-data/dsh-reqboard.json` 无 schema 字段新增。 |

### §2.1 需求条款 → 任务卡覆盖对照（FR ↔ 计划 key）

> 门禁读取表头含「需求条款」「接收任务」两列的对照表：每条 FR 必须被至少一张计划卡接收。

| 需求条款 | 覆盖内容 | 接收任务 |
|---|---|---|
| FR-1 | 确认弹框缺省阻塞到作答（删 30s 自动放行） | t2, t5 |
| FR-2 | 阻塞期间 loop 不得产出下游产物（停手守卫） | t1, t3, t5 |
| FR-3 | 非阻塞投递仅由显式宽限启用（逃生舱保留） | t2, t5 |
| FR-4 | 中止路径响亮且可续（ticket 可查） | t1, t2, t3, t5 |
| FR-5 | 提示词与工具描述与新语义一致 | t4, t5 |
| FR-6 | 兼容性不退化（旧链路逐字不变） | t5, t6 |

## §3 验收总口径（人工可见）

1. **不作答**：确认门弹出后，agent 不再产生新的工具调用/产物（界面停在等待）。
2. **作答**：同一调用内返回 `confirmed/advanced`，需求按闸门推进。
3. **取消弹框**：工具返回中性未作答结论，节点未推进，无任何下游产物被写。
4. **中止**：`reqboard_status` 能查到挂起记录，写路径仍被 `REQBOARD_CONFIRM_PENDING` 拦住，人作答后自动放行。

命令与预期见 `design/test-cases.md`；证据在实施节点写入 `test-evidence.md`。
