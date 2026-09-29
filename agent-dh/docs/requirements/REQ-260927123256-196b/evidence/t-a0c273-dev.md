---
requirement: REQ-260927123256-196b
subtask: t-a0c273
stage: dev
at: 2026-09-27T13:35:00+08:00
---

# t-a0c273 · 研发（dev）证据

> 父卡：t-f8ed18《先定契约：挂起确认能标出「被中止」，判定口径只留一处》
> 阶段：研发 —— 改动已落盘、相关命令跑通并附输出摘要。

## 本阶段做了什么（改动清单）

| 文件（仓库根相对） | 改动 |
|---|---|
| `packages/web/dsh-pmboard/src/shared/protocol.ts` | `PendingConfirmation` 增可选 `interruptedAt?: number`（共享协议契约） |
| `packages/web/dsh-pmboard/src/application/ports.ts` | `PendingConfirmPort` 增 `markInterrupted(ticket)`（不抛，未知 ticket → undefined） |
| `packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts` | 实现 `markInterrupted`（幂等，只写首次）；`get`/`pendingForWindow` 过期基准改 `(interruptedAt ?? createdAt) + ttlMs` |
| `packages/web/dsh-pmboard/src/application/internal/pending-guard.ts` | 新增：`targetConfirmedInLedger` 单点谓词、`livePendingConfirm`、`PENDING_CONFIRM_BLOCKED_TOOLS`、恢复/拒绝文案 |
| `packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts` | 删私有 `confirmedInLedger`，改用共享谓词；`interruptedAt` 且未作答时回执文案改「等待已被中止」 |
| `packages/web/dsh-pmboard/tests/pending-guard.test.ts` | 新增 9 项单测（三项验收 + 文案/过滤） |

## 可复核证据（命令与输出摘要）

```
$ cd /Users/yunpeng/pi-investment/agent-dh
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts
 ✓ packages/web/dsh-pmboard/tests/pending-guard.test.ts  (9 tests) 2ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```

回归（相关确认链路不退化）：

```
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts
 ✓ packages/web/dsh-pmboard/tests/pending-guard.test.ts  (9 tests)
 ✓ packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts  (11 tests)
 Test Files  2 passed (2) / Tests  20 passed (20)
```

## 结论

验收命令全绿，改动已落盘。三项验收断言均有覆盖：
1. `targetConfirmedInLedger` 对 plan（`approvedAt` 已写）/ artifact（该 kind 成组 `confirmedAt` 已写）返回 true，未落章 false；
2. `markInterrupted` 二次调用 `interruptedAt` 不变；
3. `createdAt` 早于中止时间时记录不提前过期。
