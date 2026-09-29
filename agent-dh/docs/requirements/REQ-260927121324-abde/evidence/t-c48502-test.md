# t-c48502 测试记录（REQ-260927121324-abde · 父卡 t-806d6e「新增执行快照收敛助手（任务执行唯一写入口）」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过（t1 交付面全绿）**——目标命令 2 files / 25 tests 全绿，退出码 0；
> 父卡「得到什么结果」中的整个 `ledger-v6-token.test.ts` 尚有 3 例红，红线在**调用方未接线**（t3/t-030788），
> 不属 t1 交付面（详见 §3 诚实声明）。

- 测试时间：2026-09-27（本轮执行内）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面：`src/application/internal/token-usage.ts` 的 6 个新增导出 + `tests/execution-snapshot-helpers.test.ts`（14 例契约）

---

## 1. 目标命令（t1 分包口径）与结果摘要

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/token-usage.test.ts (11 tests) 2ms
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests) 4ms

 Test Files  2 passed (2)
      Tests  25 passed (25)
   Duration  254ms
EXIT=0
```

## 2. 导出面（父卡「得到什么结果」前半句）

```
$ grep -nE "export function (openExecution|closeExecutions|refreshRunningExecution|snapshotForWindow|safeWindowKey|snapshotProviderFor)" src/application/internal/token-usage.ts
148:openExecution  175:closeExecutions  192:refreshRunningExecution
207:snapshotForWindow  216:safeWindowKey  230:snapshotProviderFor
$ ... | wc -l
       6            # 期望 6，实际 6
```

## 3. 相关回归（token/快照一族，无新增失败）

```
$ npx vitest run tests/token-usage.test.ts tests/execution-snapshot-helpers.test.ts \
    tests/session-probe-token.test.ts tests/token-card.test.ts tests/token-tab.test.ts \
    tests/task-report.test.ts tests/token-endpoint.test.ts tests/token-fallback.test.ts \
    tests/token-transition-helper.test.ts
 Test Files  9 passed (9)
      Tests  58 passed (58)
   Duration  884ms        # EXIT=0
```

## 4. 诚实声明：父卡整句验收命令中的 3 例红不在 t1 交付面

```
$ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts
 Test Files  1 failed | 3 passed (4)
      Tests  3 failed | 22 passed (25)        # EXIT=1
```

- 3 例红集中在 `tests/ledger-v6-token.test.ts > REQ-a33899 t3 · 写时快照：任务执行`（开工写 start / 中途汇报刷新 end+delta / unavailable 不产 delta）。
- 根因（实测，非推测）：`grep -rn "openExecution|closeExecutions|refreshRunningExecution" src/` 在 `token-usage.ts` 之外**零命中**；`MoveTask.ts:108` 仍是裸 `task.executions.push(...)`（未写 snapshot），即调用方尚未改经助手。
- 归属：正是 `t-030788`（t3，台账 in_progress）的接线范围；改动 `MoveTask.ts` 会与该卡并行写冲突，故本卡**不越界**。
- 这与联调卡 `evidence/t-6b6559-integrate.md` §4、复核卡 `evidence/t-f9462e-review.md` §3.7 的声明一致：3 red 是「3 failed → 0 failed」的基线，随 t3 接线转绿。

## 5. 结论

- t1 交付面（6 个助手契约 + 既有 token 数学契约）**目标命令全绿**，退出码 0，无回归。
- 本卡未改任何源码：实现与 14 例契约测试由研发子卡 t-882d5d 落盘；本卡只做独立复跑与留证。
- 遗留（跨卡）：`ledger-v6-token.test.ts` 的 3 例红待 t3（t-030788）接线后转绿；届时父卡「得到什么结果」整句才算 100% 绿。

测试人：实施子代理（t-c48502）；时间：2026-09-27
