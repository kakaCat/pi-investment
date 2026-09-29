---
requirement: REQ-260927123256-196b
subtask: t-db1d48
stage: test
at: 2026-09-27T13:43:38+08:00
---

# t-db1d48 · 测试（test）证据

> 父卡：t-f8ed18《先定契约：挂起确认能标出「被中止」，判定口径只留一处》
> 阶段：测试 —— 目标命令输出全绿（命令与结果摘要见下）。

## 验收命令与结果

```
$ cd /Users/yunpeng/pi-investment/agent-dh
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts

 ✓ packages/web/dsh-pmboard/tests/pending-guard.test.ts  (9 tests) 2ms

 Test Files  1 passed (1)
      Tests  9 passed (9)
   Start at  13:43:38
   Duration  207ms
```

相关回归（确认链路不退化）：

```
$ node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts packages/web/dsh-pmboard/tests/ask-confirm-pending.test.ts
 ✓ pending-guard.test.ts  (9 tests)
 ✓ ask-confirm-pending.test.ts  (11 tests)
 Test Files  2 passed (2) / Tests  20 passed (20)
```

## 三条验收断言逐条对照（pending-guard.test.ts）

| # | 断言 | 用例 |
|---|---|---|
| 1 | `targetConfirmedInLedger`：plan（`approvedAt` 已写）/ artifact（该 kind 成组 `confirmedAt` 已写）→ true；未落章 / 缺一 / 异 kind → false | `targetConfirmedInLedger：台账落章判定单点`（2 项） |
| 2 | `markInterrupted` 二次调用 `interruptedAt` 不变；未知 ticket → undefined 不抛 | `markInterrupted / 过期基准`（幂等项） |
| 3 | 过期基准 = `interruptedAt ?? createdAt`：createdAt 早于中止时间不提前失效 | `过期基准 = interruptedAt ?? createdAt` |

## 结论

目标命令全绿（9/9），回归 20/20。本卡测试阶段完成。
