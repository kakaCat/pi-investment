# t-0bacf5 测试记录（REQ-260927121324-abde · 父卡 t-00bed8「自动链任务执行与接手推进改经执行助手并带快照」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过**——父卡「得到什么结果」整句全绿（2 files / 19 tests，exit 0）；扩展快照回归 5 files / 52 tests 全绿；
> 另以临时探针实测行为面（有会话落 start/end/delta + rollup 事件带快照；system 且无源会话一律不写 token 字段），探针跑完即删。

- 测试时间：2026-09-27（本轮执行内）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面（工作区未提交改动）：`src/application/use-cases/AdvanceChain.ts`（父卡开工/收尾、rollup 三接线点）、
  `src/application/use-cases/ExecuteTask.ts`（子卡开工/收尾）、`src/wiring/pm-capture-root.ts`（接手推进带提供者）、
  `src/index.ts`（启动对账明确不传 snapshot）

---

## 1. 目标命令 —— 父卡 t-00bed8「得到什么结果」整句

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/advance-chain.test.ts (8 tests) 15ms
 ✓ tests/execute-task.test.ts (11 tests) 19ms

 Test Files  2 passed (2)
      Tests  19 passed (19)
   Duration  362ms
EXIT=0
```

- 期望：自动链全流程（开父卡 → 跑子卡 → 收尾 → rollup）与子卡执行两组全绿；实际 **19/19 passed，exit 0**。

## 2. 扩展回归（执行快照一族，独立复跑）

```
$ npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts \
    tests/execution-snapshot-helpers.test.ts tests/ledger-v6-token.test.ts tests/token-usage.test.ts

 ✓ tests/token-usage.test.ts (11 tests) 3ms
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests) 5ms
 ✓ tests/advance-chain.test.ts (8 tests) 15ms
 ✓ tests/execute-task.test.ts (11 tests) 25ms
 ✓ tests/ledger-v6-token.test.ts (8 tests) 43ms

 Test Files  5 passed (5)
      Tests  52 passed (52)
EXIT=0
```

## 3. 目标命令 · 静态口径（写点收敛）

```
$ grep -rn "executions.push(" src/application src/http | grep -v "internal/token-usage.ts"
（无输出）OUTSIDE_EXIT=1     # 期望：写点仅收敛在助手内

$ grep -rn "executions.push(" src/application src/http
src/application/internal/token-usage.ts:113   （注释：调用方不得自行 push）
src/application/internal/token-usage.ts:160   （唯一写点 openExecution 内）
```

- 说明：父卡口径的括号已写明「写点仅助手内」——命中两行均落在收敛助手 `src/application/internal/token-usage.ts` 内，
  除该助手外 **0 处**直写（其余用-case/路由文件无 `executions.push(`）。

## 4. 接线点静态复验（不采信上游自述）

| 落点 | 位置 | 实测 |
|---|---|---|
| AdvanceChain 父卡开工 | `AdvanceChain.ts:151/152/160` `safeWindowKey(deps, exec) ?? req.sourceSessionId` → `openExecution(..., snapshotForWindow(deps, sessionKey))` | ✅ |
| AdvanceChain 父卡收尾 | `AdvanceChain.ts:192/193` → `closeExecutions(parent, { at, outcome:'succeeded' }, snapshotForWindow(...))` | ✅ |
| AdvanceChain rollup 快照 | `AdvanceChain.ts:229-231` → `snapshot: snapshotProviderFor(deps, safeWindowKey(deps, exec))` | ✅ |
| ExecuteTask 子卡开工 | `ExecuteTask.ts:150/267/276` → `openExecution(..., outcome:'failed' 不写 start 由助手内部处理, snapshotForWindow(...))` | ✅ |
| ExecuteTask 子卡收尾 | `ExecuteTask.ts:305`（done）/ `:317`（failed，带 error）→ `closeExecutions(...)` | ✅ |
| 接手推进带提供者 | `pm-capture-root.ts:135/137` → `snapshotProviderFor(deps.useCaseDeps(), windowKey)` 传入 `applyPickupAdvance` | ✅ |
| 启动对账不带快照 | `index.ts:167` `const ctx: RollupContext = { now, commentId }`（无 snapshot） | ✅ |
| 助手导出齐全 | `token-usage.ts:148/175/192/207/216/230` 六个导出函数 | ✅ |

- `safeWindowKey`：无 exec / 缺 agent / 端口抛错 / `'system'` 哨兵 → `undefined`，永不抛（`token-usage.ts:216-224`）。
- `snapshotProviderFor`：显式窗口码优先，退回 `req.sourceSessionId`，都无 → `undefined`（`token-usage.ts:230-238`）。
- `openExecution` born-failed（`outcome:'failed'`）不写 start、直接以终止记录落账（`token-usage.ts:148-162`）。

## 5. 临时端到端探针（实测行为面，跑完即删）

> 目标命令（既有两文件）只证明自动链无回归，未断言快照字段；为不把「绿灯」当「行为已验」，
> 本卡另起临时探针 `tests/__probe-t0bacf5-autochain.test.ts` 驱动 `advanceRequirement` 跑真链路，
> 执行后**已删除**（常驻行为用例按拆分计划由 t-49d8d4「补看板/自动链/读路径行为用例」落盘，避免写冲突）。

```
$ npx vitest run tests/__probe-t0bacf5-autochain.test.ts
 ✓ tests/__probe-t0bacf5-autochain.test.ts (2 tests) 9ms
 Test Files  1 passed (1)
      Tests  2 passed (2)
EXIT=0
```

| 场景 | 断言 | 实测 |
|---|---|---|
| A. 有真实会话（`exec.agent.id='session-w-001'`，tokenSnapshot source=projection）跑完父卡链 | 父卡 `executions[0].tokenUsage.start.totals` 有值、收尾后 `end` 写入、`delta`=空桶；4 张子卡各自 `start` 有值 | ✅ |
| A. rollup 进 accepting | 需求状态事件 `tokenSnapshot.totals` 等于当次快照（提供者真透传） | ✅ |
| B. 无会话（`exec.agent.id='system'` 且需求无 `sourceSessionId`） | 执行记录照常落账，但所有 `tokenUsage` 均为 `undefined`；accepting 事件 `tokenSnapshot===undefined`（不伪造） | ✅ |

- 删除留痕：`ls tests/ | grep -c "__probe"` → 0；`git status --porcelain tests/__probe-t0bacf5-autochain.test.ts` 无输出。

## 6. 结论

- 父卡 t-00bed8「得到什么结果」整句**全绿**：目标命令 19/19 passed（exit 0）+ 写点收敛 grep 无越界，无回归。
- 行为面经临时探针实测：有会话时自动链父卡/子卡开工写 start、收尾写 end/delta、rollup 事件带快照；
  system/无源会话一律不伪造 token 字段（缺失 ≠ 0）。
- 本卡未改任何源码（探针文件跑完即删）；四文件接线由研发子卡 t-86bafa 落盘。
- 遗留（跨卡）：自动链/看板/读路径的**常驻**行为用例按拆分计划由 t-49d8d4 落盘，本卡不越界。

测试人：实施子代理（t-0bacf5）；时间：2026-09-27
