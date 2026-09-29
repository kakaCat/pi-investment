# t-fc2982 测试记录（REQ-260927121324-abde · 父卡 t-15c076「看板任务流转/建卡改卡带写时快照」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过**——父卡「得到什么结果」整句全绿（2 files / 19 tests，exit 0；静态 grep 无输出）；
> 另以临时探针实测行为面：带 sessionId 开工写 start / 收尾写 end+delta / rollup 事件带快照，
> 无 sessionId 不落执行记录、不写 token 字段（不伪造），探针跑完即删（常驻行为用例属 t8 范围）。

- 测试时间：2026-09-27（本轮执行内）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面（t4 = 研发子卡 t-726c22 落盘的 `src/http/routers/tasks.ts` 单文件，52 insertions / 19 deletions）：
  - `:118-122` 开工 `openExecution(task, {id,sessionId,trigger,at}, snapshotOf(sessionId))`
  - `:131-135` 收尾 `closeExecutions(task, {at,outcome}, snapshotOf(sessionId))`
  - `:89-93`（建卡）/ `:142-146`（流转）/ `:186-190`（改卡）三处 `applyTaskRollup({ ..., snapshot: rollupSnapshot(sessionId) })`
  - `:39` `sessionIdOf` / `:47` `snapshotOf` / `:52` `rollupSnapshot`：会话码解析与快照取值单点化
- 测试方式：独立复跑父卡验收命令 + 静态接线复验 + 临时端到端探针（不采信上游自述）

---

## 1. 目标命令（父卡 t-15c076「得到什么结果」）与结果摘要

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/routes-rollup.test.ts tests/rollup.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/rollup.test.ts (16 tests) 4ms
 ✓ tests/routes-rollup.test.ts (3 tests) 186ms

 Test Files  2 passed (2)
      Tests  19 passed (19)
   Duration  873ms
EXIT=0
```

- 期望：路由层派生推进（`/task/create`、`/task/move` 经真 HTTP handler）与 rollup 纯函数两组全绿；实际 **19/19 passed，exit 0**。

## 2. 目标命令 · 静态口径（grep 无输出）

```
$ grep -n "executions.push(" src/http/routers/tasks.ts
（无输出）GREP_EXIT=1        # 期望：无输出

$ grep -nE "tokenUsage|executions\.push" src/http/routers/tasks.ts
（无输出）DIRECT_EXIT=1      # 期望：tasks.ts 内 0 条直写

$ grep -nE "sessionIdOf|snapshotOf|rollupSnapshot|openExecution|closeExecutions|applyTaskRollup" src/http/routers/tasks.ts
24: import { applyTaskRollup } ...
25: import { closeExecutions, openExecution } ...
39: sessionIdOf   47: snapshotOf   52: rollupSnapshot
59 / 105 / 163:  const sessionId = sessionIdOf(body)      ← create / move / update 三入口
89 / 142 / 186:  applyTaskRollup({ ... snapshot: rollupSnapshot(sessionId) }, ...)
118: openExecution(...)  121: snapshotOf(sessionId)
131: closeExecutions(...) 134: snapshotOf(sessionId)
```

- 期望：唯一写入口收敛于助手；三入口同一口径；实际逐条落位，tasks.ts 无任何 `executions.push` / `tokenUsage` 直写。

## 3. 临时端到端探针（实测行为面，跑完即删）

> 目标命令（`routes-rollup`）只证明路由/rollup 无回归，未断言快照字段；为不把「绿灯」当「行为已验」，
> 本卡另起临时探针 `tests/__probe-t4-snapshot.test.ts` 直连 `createReqboardHandler`（注入 `tokenSnapshot` 提供者）跑真链路，
> 执行后**已删除**（常驻行为用例由 t8「补看板/自动链/读路径行为用例」落盘，避免与 t8 写冲突）。

```
$ npx vitest run tests/__probe-t4-snapshot.test.ts
 ✓ tests/__probe-t4-snapshot.test.ts (2 tests) 103ms
 Test Files  1 passed (1)
      Tests  2 passed (2)
EXIT=0
```

| 场景 | 断言 | 实测 |
|---|---|---|
| A. `/task/move` 带 `sessionId:'sess-A'` 到 in_progress | 落 1 条执行记录且 `sessionId='sess-A'`、`tokenUsage.start.totals.outputTokens=10` | ✅ |
| A. 同会话再移到 testing（离开执行段） | `tokenUsage.end` 与 `delta` 均写入 | ✅ |
| A. 全任务 done（带会话）触发 rollup | 需求进 `accepting`，该状态事件 `tokenSnapshot.totals.outputTokens=10`（rollup 快照提供者真的透传） | ✅ |
| A. `/task/update` 带可选 `sessionId` | 200、响应形状不变、title 更新生效 | ✅ |
| B. 全链路**不带** `sessionId` | `executions.length=0`（既有契约）、accepting 事件 `tokenSnapshot=undefined`、`req.tokenUsage=undefined`（无会话不伪造） | ✅ |

- 删除留痕：`ls tests/ | grep -c "__probe"` → 0；`git status --porcelain tests/` 无该文件。

## 4. 扩展回归（token/快照一族，独立复跑）

```
$ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts \
    tests/execution-snapshot-helpers.test.ts tests/task-report.test.ts tests/token-transition-helper.test.ts

 Test Files  5 passed (5)
      Tests  43 passed (43)
EXIT=0
```

## 5. 结论

- 父卡 t-15c076「得到什么结果」整句**全绿**：目标命令 19/19 passed（exit 0）+ 静态 grep 无输出，无回归。
- 行为面经临时探针实测：三入口同一快照口径成立，有会话落 start/end/delta 与 rollup 事件快照，无会话一律不伪造。
- 本卡未改任何源码（探针文件跑完即删）；t4 实现由研发子卡 t-726c22 落盘。
- 遗留（跨卡）：看板快照的**常驻**行为用例按拆分计划由 t8（t-49d8d4）落盘，本卡不越界。

测试人：实施子代理（t-fc2982）；时间：2026-09-27
