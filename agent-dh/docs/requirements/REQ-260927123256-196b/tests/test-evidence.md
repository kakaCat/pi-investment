# 测试证据 · REQ-260927123256-196b

> 采集时点：2026-09-27（implementing / accepting 节点，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）。
> 口径对齐 `design/test-cases.md` 的测试文件落点表与 requirement.md 的「可执行判定命令」。

## 1. 本需求验收命令

| 判定 | 命令 | 结果 |
|---|---|---|
| FR-1 / FR-3 | `vitest run packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts` | ✅ 1 file / 11 tests |
| FR-2 / FR-4 | `vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts` | ✅ 1 file / 5 tests |
| t5 全分支 | `vitest run`（8 文件：ask-confirm-blocking / ask-confirm-pending / pending-guard / confirm-pending-guard / status-pending-confirm / ask-confirm-prompt / contract-shapes / tools-schema） | ✅ 8 files / **49 tests passed（0 failed）** |
| FR-5 | `vitest run tests/ask-confirm-prompt.test.ts tests/tools-schema.test.ts` | ✅ 2 files / 7 tests |
| 联调 | `vitest run tests/pending-guard-integration.test.ts` | ✅ 1 file / 7 tests |

## 2. 用例 → 文件落点（对齐 design/test-cases.md）

| 用例 | 文件 | 结果 |
|---|---|---|
| TC-1 / TC-2 / TC-7 / TC-8 / TC-10 | `tests/ask-confirm-blocking.test.ts`（新增，`// serves: FR-1, FR-4`） | 5 passed |
| TC-3 / TC-4 / TC-5 | `tests/ask-confirm-pending.test.ts`（更新） | 11 passed |
| TC-6 / TC-9 / TC-13 | `tests/confirm-pending-guard.test.ts`（扩展） | 5 passed |
| TC-7 投影 | `tests/status-pending-confirm.test.ts`（新增，`// serves: FR-4`） | 4 passed |
| TC-11 | `tests/ask-confirm-prompt.test.ts`（新增，`// serves: FR-5`） | 3 passed |
| TC-12 / TC-14 | `tests/tools-schema.test.ts` / `tests/contract-shapes.test.ts`（更新） | 4 + 8 passed |
| TC-15 | `tests/pending-guard.test.ts` | 9 passed |

## 3. 故障注入回填（design/test-cases.md「故障注入」表）

| 注入点 | 注入方式 | 预期 | 实测 |
|---|---|---|---|
| 缺省阻塞 | `ask` 永不 resolve、不传宽限 | 观测窗内不返回；resolve 后同步体 | ✅ TC-1（200ms 未返回） |
| 显式宽限 | 永不 resolve + `inline_grace_ms: 20` | pending + ticket，不抛 | ✅ TC-4 |
| 能力未装配 | 正数宽限 + 无注册表 | `REQBOARD_NONBLOCK_UNAVAILABLE` | ✅ TC-5 |
| 中止 | `ASK_ABORTED` + `signal.aborted` | interrupted + 记录保留 | ✅ TC-7 |
| 取消 | `ASK_CANCELLED` | 中性返回、记录 settle、守卫放行 | ✅ TC-8 |
| status 投影 | 有 / 无挂起记录 | 有→列；无→空数组 | ✅ status-pending-confirm |
| 守卫 | 未作答 + 台账未落章 | 写路径被拒且不写盘 | ✅ TC-6 |
| 守卫解除 | 未作答 + 台账已落章 | 放行（不死锁） | ✅ TC-9 |
| 注册表异常 | 未知 ticket 调 `markInterrupted` | undefined、不抛 | ✅ pending-guard.test.ts |

## 4. 预存在失败（非本需求）

2026-09-27 14:16（动手前）复跑即红的项，来自同工作区其他窗口未提交改动：
- `tests/ask-confirm.test.ts`「闸门问题卡（t08）」1 条 —— 另一改动把 move 门禁文案从「问题卡」换成 `artifact_not_confirmed` 文案。
- `tests/output-contract.test.ts` 4 条 —— Advance / ClearPause / RunStatus / TaskMove 未补 `RESPONSE_SOURCES` 与 schema 声明。
- `tests/message-hygiene.test.ts` 1 条 —— application/http 拼接数被其他改动推高超过基线。

目标文件均不在本需求交付面（本需求改动模块：AskConfirm / pending-confirm / pending-guard / support /
QueryState / StatusTool / AskConfirmTool / ConfirmReceiptTool / domain/limits / 上述测试文件）。

## 5. 类型面

`tsc --noEmit -p packages/web/dsh-pmboard/tsconfig.json` 在本需求改动的文件上 **0 报错**
（`StatusTool.ts` 的未使用 `STATUS_PROMPT` import 在 HEAD 即存在，非本次引入）。
