# 实施证据 · REQ-260927123256-196b（implementing）

> 采集时点：2026-09-27（implementing 节点，w-b71bb246）。
> 口径对齐 requirement.md「可执行判定命令」与 design/test-cases.md。

## 1. 验收命令结果（本需求相关）

| # | 命令（agents-dh 根） | 结果 |
|---|---|---|
| FR-1/FR-3 | `vitest run packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts` | ✅ 1 passed / 11 tests |
| FR-2/FR-4 | `vitest run packages/web/dsh-pmboard/tests/confirm-pending-guard.test.ts` | ✅ 1 passed / 5 tests |
| t5 全套 | `vitest run`（ask-confirm-blocking / ask-confirm-pending / pending-guard / confirm-pending-guard / status-pending-confirm / ask-confirm-prompt / contract-shapes / tools-schema） | ✅ 8 files passed / 49 tests |
| FR-5 | `vitest run tests/ask-confirm-prompt.test.ts tests/tools-schema.test.ts` | ✅ 2 files passed / 7 tests |
| FR-6 | `vitest run tests/ask-confirm.test.ts tests/tools-schema.test.ts` | ⚠️ 1 预存在失败（见 §2），其余 14 passed |

新增测试文件（均头部 `// serves: FR-x`）：
- `tests/ask-confirm-blocking.test.ts`（TC-1/2/7/8/10，FR-1/FR-4）
- `tests/status-pending-confirm.test.ts`（TC-9 投影，FR-4）
- `tests/ask-confirm-prompt.test.ts`（TC-11，FR-5）

更新测试文件：`ask-confirm-pending.test.ts`（TC-3/5）、`confirm-pending-guard.test.ts`（TC-6/9/13）、
`contract-shapes.test.ts`（TC-14）、`tools-schema.test.ts`（TC-12）。

## 2. 与本次改动无关的**预存在失败**（须与返工区分）

以下失败在本节点动手**之前**（2026-09-27 14:16 基线复跑）即已存在，来自同工作区其他窗口的未提交改动：

| 文件 | 失败用例 | 根因（不在本需求范围） |
|---|---|---|
| `tests/ask-confirm.test.ts` | 「闸门问题卡（t08）」 | `reqboard_move` 的门禁文案被别的改动换成 `artifact_not_confirmed` 文案，不再是「问题卡」 |
| `tests/output-contract.test.ts` | defineAdvance/ClearPause/RunStatus/TaskMove | 其他窗口新增/改动的工具未补 `RESPONSE_SOURCES` 映射与 schema 声明 |
| `tests/message-hygiene.test.ts` | 拼接式消息棘轮 | application 140→188、http 21→22，由其他窗口改动累积超过基线 |

另：全量 `packages/web/dsh-pmboard` 套件当前有 131 条失败（acceptance-criteria/artifact-gates/task-report/
handoff 等），均为同工作区其他未提交改动所致（本节点未触碰这些模块）。本节点改动涉及的模块
（AskConfirm / pending-confirm / pending-guard / support / QueryState / StatusTool / 提示词 / limits）
经复跑 0 新增失败；`tsc --noEmit` 在本节点改动的文件上 0 类型错误（`StatusTool.ts` 的
`STATUS_PROMPT` 未使用 import 在 HEAD 即存在，非本次引入）。

## 3. 故障注入核对（design/test-cases.md「故障注入」表回填）

| 注入点 | 注入方式 | 预期 | 实测 |
|---|---|---|---|
| I-1 缺省阻塞 | `ask` 永不 resolve、不传宽限 | 观测窗内不返回；resolve 后返回同步体 | ✅ TC-1（200ms 未返回；resolve 后 confirmed/advanced，无 pending/ticket） |
| I-1 显式宽限 | `ask` 永不 resolve + `inline_grace_ms: 20` | 返回 pending+ticket，不抛 | ✅ TC-4（ask-confirm-pending） |
| I-1 能力未装配 | 正数宽限 + `pendingConfirms` 缺省 | 抛 `REQBOARD_NONBLOCK_UNAVAILABLE` | ✅ TC-5 |
| I-1 中止 | `ask` 拒绝 `ASK_ABORTED` + signal.aborted | interrupted:true + 记录保留 | ✅ TC-7 |
| I-1 取消 | `ask` 拒绝 `ASK_CANCELLED` | 中性返回、记录 settle、守卫放行 | ✅ TC-8 |
| I-2 status | 有 / 无挂起记录 | 有→列 pending_confirms；无→空数组 | ✅ status-pending-confirm.test.ts |
| I-3 守卫 | 未作答 + 台账未落章 | 写路径被拒且不写盘 | ✅ TC-6（confirm-pending-guard） |
| I-3 守卫解除 | 未作答 + 台账已落章 | 放行（不死锁） | ✅ TC-9 |
| I-4 注册表 | 未知 ticket 调 markInterrupted | 返回 undefined，不抛 | ✅ pending-guard.test.ts |

## 4. 文档同步（FR-5）

`agent-dh/docs/architecture/reqboard-pipeline-flow.md` G1/G2 步骤描述已由「非阻塞投递：30s 宽限」
改写为「缺省阻塞；仅显式正数 inline_grace_ms 走逃生舱」；
`grep -rn "非阻塞投递：30s" docs/architecture/reqboard-pipeline-flow.md` → 无输出。
