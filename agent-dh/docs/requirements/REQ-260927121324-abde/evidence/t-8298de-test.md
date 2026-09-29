# t-8298de 测试记录（REQ-260927121324-abde · 父卡 t-030788「agent 任务执行与中途汇报改经执行助手」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过**——父卡口径命令全绿（2 files / 15 tests，exit 0），父卡「得到什么结果」整句（含 5 文件回归口径）
> 在 t3 接线后已 100% 转绿（5 files / 61 tests，exit 0）。

- 测试时间：2026-09-27（本轮执行内）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面（t3）：`src/application/use-cases/MoveTask.ts`（开工/收尾/rollup 三接线点）+ `src/application/use-cases/ReportTask.ts`（中途刷新）

---

## 1. 目标命令 A —— 父卡「得到什么结果」整句（2 文件口径）

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/ledger-v6-token.test.ts tests/task-report.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/task-report.test.ts (7 tests) 233ms
 ✓ tests/ledger-v6-token.test.ts (8 tests) 40ms

 Test Files  2 passed (2)
      Tests  15 passed (15)
   Duration  787ms
EXIT=0
```

- 期望：token 写时快照三例（开工写 start / 中途汇报刷新 end+delta 且 outcome 仍 running / 快照不可得不产 delta）由 red 转 green；实际 15/15 passed。

## 2. 目标命令 B —— 5 文件回归口径（父卡验收命令扩展，独立复跑）

```
$ npx vitest run tests/ledger-v6-token.test.ts tests/task-report.test.ts \
    tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts tests/application/use-cases.test.ts

 ✓ tests/token-usage.test.ts (11 tests) 3ms
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests) 4ms
 ✓ tests/ledger-v6-token.test.ts (8 tests) 40ms
 ✓ tests/application/use-cases.test.ts (21 tests) 57ms
 ✓ tests/task-report.test.ts (7 tests) 248ms

 Test Files  5 passed (5)
      Tests  61 passed (61)
   Duration  784ms
EXIT=0
```

> 说明：`application/use-cases.test.ts` 中出现 1 条 stderr 告警（`[QueryState] 追溯链统计失败: text.split is not a function`，来自与本卡无关的 `checkFullTraceability` 路径）；测试仍 21/21 passed，不影响目标命令结论。

## 3. 接线点静态复验（不采信上游自述）

```
$ grep -rn "beginExecutionToken" src/
src/application/internal/token-usage.ts:86   （定义）
src/application/internal/token-usage.ts:159  （openExecution 内真实调用方 → 不再是死代码）
EXIT=0

$ grep -rn "executions.push(" src/application/use-cases/MoveTask.ts src/application/use-cases/ReportTask.ts
（无输出）EXIT=1   # 两文件 0 条直写，写点收敛于助手内
```

- `MoveTask.ts:115-119`：`openExecution(task, { id, sessionId: windowKey, trigger: 'manual', at }, snapshotForWindow(deps, windowKey))`
- `MoveTask.ts:132-136`：`closeExecutions(task, { at, outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded' }, snapshotForWindow(deps, windowKey))`
- `MoveTask.ts:141-145`：`applyTaskRollup(ledger, { now, commentId, snapshot: snapshotProviderFor(deps, windowKey) }, reqId)`
- `ReportTask.ts:123/135`：`captureSnapshot(deps, windowKey)` → `refreshRunningExecution(tk, snap, windowKey)`（outcome 保持 running）

## 4. 结论

- 父卡验收命令（2 文件）与扩展回归口径（5 文件）**全绿，exit 0**，无回归、无新增失败。
- 三处执行助手接线点逐字落位，两文件无直写；`beginExecutionToken` 已被真实调用（不再是死代码）。
- 本卡未改任何源码：实现由研发子卡 t-eaafd0 落盘；本卡只做独立复跑与留证。

测试人：实施子代理（t-8298de）；时间：2026-09-27
