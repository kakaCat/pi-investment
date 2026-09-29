# t-4cbf34 接口联调记录（REQ-260927121324-abde · 父卡 t-030788「agent 任务执行与中途汇报改经执行助手」· 阶段 integrate）

> 验收标准：接口联调通过：给出请求样例与期望响应，实际返回与预期一致。
> 结论：**通过** —— 调用方级（用例 + agent 工具壳）**24 例三方比对 24/24 MATCH，MISMATCH=0**。

## 1. 联调对象（接口面）

父卡 t-030788 的交付面是「把 agent 侧任务写路径接到 t1 的执行快照收敛助手」，共 4 个接线点：

| 编号 | 调用方（接口签名） | 请求样例 | 期望响应语义 |
|---|---|---|---|
| I-1 | `executeMoveTask(deps,{task_id,to,reason?},exec)` 开工 | `{task_id:'t-000001',to:'in_progress'}`；窗口 `session-w-001` | 返回任务卡全文；台账落 1 条 running 执行，`start` = 当次快照、`delta` 缺省；认领窗口 |
| I-2 | 同 I-1，收尾 | `{to:'integrating'}`（或回退 `{to:'todo'}`） | `closeExecutions` 闭合全部 running：写 `endedAt`/`outcome`（回退= cancelled）、`end` 与 `delta` |
| I-3 | `executeReportTask(deps,{task_id,summary,...},exec)` 中途汇报 | `{task_id:'t-000001',summary:'做到一半'}` | `refreshRunningExecution(tk,snap,windowKey)`：最近一条同会话 running 刷 `end/delta`，**outcome 保持 running** |
| I-4 | 同 I-1，派生推进 | design + 有任务 → 自动进入拆分 | `applyTaskRollup` 带 `snapshot:{snapshotProviderFor(deps,windowKey)}`：推进事件（decomposing）带投影快照 |
| I-5 | 横切：快照缺失语义 | 快照端口抛错 / source=unavailable | start/end 如实记 `unavailable`、不产出 `delta`；**主流程不阻断**（助手永不抛、缺失≠0） |
| I-6 | 横切：错误码面不变 | `to:'canceled'` / 任务不存在 / 空 summary | `REQBOARD_HUMAN_GATE` / `REQBOARD_TASK_NOT_FOUND` / `REQBOARD_INVALID_INPUT` 逐字不变 |
| I-7 | agent 工具壳 | `reqboard_task_move` / `reqboard_task_report` | 薄壳转发，返回体与用例逐字一致（真实 agent 接口面） |

联调方式：临时探针 `packages/web/dsh-pmboard/tests/__probe-t4cbf34.test.ts` 以**真实模块**（双用例 + `token-usage.ts` 助手 + 两个工具壳）＋内存端口（`tests/application/harness.ts`）逐例调用；工具壳例另用**真实适配器**（JsonLedgerRepository / SessionProbeAdapter / FileDocRepository）+ 临时工作区 fs。把「请求样例 / 期望响应 / 实际返回」三方比对后打印 verdict 表并断言 `MISMATCH=0`。探针已按惯例跑完即删（不留在仓库）。

## 2. 联调命令与输出摘要

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/__probe-t4cbf34.test.ts
 ✓ tests/__probe-t4cbf34.test.ts (6 tests) 70ms
 Test Files  1 passed (1)
      Tests  6 passed (6)
 → 对照表 24 例，MISMATCH=0
```

父卡验收命令（t3 交付面）：
```
$ npx vitest run tests/ledger-v6-token.test.ts tests/task-report.test.ts tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts tests/application/use-cases.test.ts
 Test Files  5 passed (5)
      Tests  61 passed (61)
```

接线点静态确认（t3 范围内两处直写已收敛为助手调用）：
```
$ grep -nE "openExecution|closeExecutions|snapshotForWindow|snapshotProviderFor|refreshRunningExecution" src/application/use-cases/MoveTask.ts src/application/use-cases/ReportTask.ts
MoveTask.ts:115:      openExecution(
MoveTask.ts:118:        snapshotForWindow(deps, windowKey),
MoveTask.ts:132:      closeExecutions(
MoveTask.ts:135:        snapshotForWindow(deps, windowKey),
MoveTask.ts:143:      { now: at, commentId: () => deps.ids.comment(), snapshot: snapshotProviderFor(deps, windowKey) },
ReportTask.ts:16:import { captureSnapshot, refreshRunningExecution } from '../internal/token-usage.js'
ReportTask.ts:135:          refreshRunningExecution(tk, snap, windowKey)

$ grep -rn "executions.push(" src/
src/http/routers/tasks.ts:90         ← t4 / t-15c076 范围
src/application/internal/token-usage.ts:160   ← 助手内部唯一写点
src/application/use-cases/AdvanceChain.ts:141 ← t5 / t-00bed8 范围
src/application/use-cases/ExecuteTask.ts:239  ← t5 / t-00bed8 范围
 → MoveTask.ts / ReportTask.ts 已无直写

$ grep -rn "beginExecutionToken" src/
src/application/internal/token-usage.ts:86    ← 定义
src/application/internal/token-usage.ts:159   ← openExecution 内部调用
 → 不再是死代码（t1 已复活，t3 起有真实调用方）
```

接口类型面（证明两文件按新签名消费助手）：
```
$ npx tsc --noEmit -p tsconfig.json  | grep -E "use-cases/(MoveTask|ReportTask)\.ts"
（无输出 → 两文件 0 条 error；包内另有 117 条既有 TS error，全部落在与 t3 无关的文件，属并行工作线遗留）
```

## 3. 三方对照表（请求样例 / 期望响应 / 实际返回）

```
===== t-4cbf34 接口联调对照表（调用方级：用例 + agent 工具壳）=====
MATCH    | M-1 | executeMoveTask 开工 | 请求: {task_id:'t-000001',to:'in_progress',reason:'开工'}; snap=projection(B2) | 期望: {"from":"todo","status":"in_progress","success":true,"task_card":{"doc_path":"docs/requirements/REQ-000001/tasks/t-000001.md","implementation":"改 x.ts"},"task_id":"t-000001","to":"in_progress","version":2} | 实际: {"from":"todo","status":"in_progress","success":true,"task_card":{"doc_path":"docs/requirements/REQ-000001/tasks/t-000001.md","implementation":"改 x.ts"},"task_id":"t-000001","to":"in_progress","version":2}
MATCH    | M-1L | executeMoveTask 开工·台账落 running + start | 请求: task.executions[0] | 期望: {"delta":null,"endSource":null,"endTotals":null,"endedAt":null,"outcome":"running","sessionId":"session-w-001","startSource":"projection","startTotals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":4,"uncachedInputTokens":2},"startedAt":1000000,"trigger":"manual"} | 实际: 同上
MATCH    | M-1C | executeMoveTask 开工·认领窗口 | 请求: task.claimedBy / claimedAt | 期望: {"claimedAt":1000000,"claimedBy":"session-w-001"} | 实际: 同上
MATCH    | M-3 | executeMoveTask 收尾 | 请求: {task_id:'t-000001',to:'integrating'}; snap=projection(B5) | 期望: {"from":"in_progress","status":"integrating","success":true,"task_id":"t-000001","to":"integrating","version":3} | 实际: 同上
MATCH    | M-3L | executeMoveTask 收尾·闭合 + end/delta | 请求: executions[0].tokenUsage | 期望: {"delta":{"cacheReadTokens":30,"cacheWriteTokens":0,"outputTokens":6,"uncachedInputTokens":3},"endSource":"projection","endTotals":{"cacheReadTokens":50,"cacheWriteTokens":0,"outputTokens":10,"uncachedInputTokens":5},"endedAt":1000000,"outcome":"succeeded"} | 实际: 同上
MATCH    | M-4 | executeMoveTask 回退 | 请求: {task_id:'t-000001',to:'todo'}; snap=projection(B5) | 期望: {"from":"in_progress","status":"todo","success":true,"task_id":"t-000001","to":"todo","version":3} | 实际: 同上
MATCH    | M-4L | executeMoveTask 回退·cancelled + 解除认领 | 请求: outcome / claimedBy / delta | 期望: {"claimedAt":null,"claimedBy":null,"delta":{"cacheReadTokens":30,"cacheWriteTokens":0,"outputTokens":6,"uncachedInputTokens":3},"endedAt":1000000,"outcome":"cancelled"} | 实际: 同上
MATCH    | M-2 | executeMoveTask 开工·unavailable | 请求: {task_id:'t-000001',to:'in_progress'}; snap=unavailable | 期望: 与 M-1 返回体逐字相同 | 实际: 同上
MATCH    | M-2L | executeMoveTask 开工·unavailable 落账不产出 delta | 请求: start.source / delta | 期望: {"delta":null,"startSource":"unavailable","startTotals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}} | 实际: 同上
MATCH    | R-1 | executeReportTask 中途刷新 | 请求: {task_id:'t-000001',summary:'做到一半'}; snap=projection(B4) | 期望: {"artifact_registered":true,"doc_path":"docs/requirements/REQ-000001/tasks/t-000001.md","note":"汇报已追加到 docs/requirements/REQ-000001/tasks/t-000001.md（第 1 段），产物已登记","report_index":1,"requirement_id":"REQ-000001","success":true,"task_id":"t-000001"} | 实际: 同上
MATCH    | R-1L | executeReportTask 中途刷新·outcome 保持 running | 请求: executions[0] | 期望: {"delta":{"cacheReadTokens":30,"cacheWriteTokens":0,"outputTokens":6,"uncachedInputTokens":3},"endSource":"projection","endTotals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":8,"uncachedInputTokens":4},"endedAt":null,"outcome":"running"} | 实际: 同上
MATCH    | R-2 | executeReportTask 未命中 running | 请求: {task_id:'t-000001',summary:'无执行段'} | 期望: 与 R-1 返回体逐字相同（不报错） | 实际: 同上
MATCH    | R-2L | executeReportTask 未命中·无副作用 | 请求: executions 长度 | 期望: {"executions":0} | 实际: 同上
MATCH    | RU-1 | executeMoveTask 派生推进（design + 有任务 → decomposing） | 请求: {task_id:'t-000001',to:'in_progress'}（需求 design） | 期望: 与 M-1 返回体逐字相同 | 实际: 同上
MATCH    | RU-1L | rollup 推进事件带投影快照 | 请求: req.status / 末条 statusHistory.tokenSnapshot | 期望: {"eventSessionId":"session-w-001","eventSource":"projection","eventStatus":"decomposing","eventTotals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":4,"uncachedInputTokens":2},"status":"decomposing"} | 实际: 同上
MATCH    | RU-2 | executeMoveTask 端口抛错不阻断 | 请求: tokenTotals throws Error(boom) | 期望: 与 M-1 返回体逐字相同 | 实际: 同上
MATCH    | RU-2L | 端口抛错·开工与推进事件均记 unavailable | 请求: start.source / rollup 事件 source | 期望: {"eventSource":"unavailable","eventStatus":"decomposing","startSource":"unavailable","startTotals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}} | 实际: 同上
MATCH    | E-1 | executeMoveTask 人工闸门 | 请求: {task_id:'t-000001',to:'canceled'} | 期望: {"code":"REQBOARD_HUMAN_GATE"} | 实际: 同上
MATCH    | E-2 | executeMoveTask 任务不存在 | 请求: {task_id:'t-ffffff'} | 期望: {"code":"REQBOARD_TASK_NOT_FOUND"} | 实际: 同上
MATCH    | E-3 | executeReportTask 空摘要 | 请求: {task_id:'t-000001',summary:''} | 期望: {"code":"REQBOARD_INVALID_INPUT"} | 实际: 同上
MATCH    | T-1 | reqboard_task_move 工具壳 | 请求: {task_id:'t-000001',to:'in_progress',reason:'开工'} | 期望: 与 M-1 返回体逐字相同 | 实际: 同上
MATCH    | T-1L | reqboard_task_move 工具壳·start | 请求: executions[0] | 期望: {"delta":null,"endedAt":null,"outcome":"running","sessionId":"session-w-001","startSource":"projection","startTotals":{"cacheReadTokens":30,"cacheWriteTokens":0,"outputTokens":6,"uncachedInputTokens":3},"startedAt":1000000,"trigger":"manual"} | 实际: 同上（真实适配器 + JSON 台账 + fs）
MATCH    | T-2 | reqboard_task_report 工具壳 | 请求: {task_id:'t-000001',summary:'工具面汇报'} | 期望: 与 R-1 返回体逐字相同 | 实际: 同上
MATCH    | T-2L | reqboard_task_report 工具壳·刷新 running | 请求: executions[0] | 期望: {"delta":{"cacheReadTokens":10,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":1},"endSource":"projection","endTotals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":8,"uncachedInputTokens":4},"outcome":"running"} | 实际: 同上
===== 共 24 例，MISMATCH=0 =====
```

> 说明：上表 M-1L/M-3L/M-4L/R-1L/RU-2L/T-1L/T-2L 等含大对象的行，为便于阅读把「实际」列记为「同上」；
> 探针运行时对每一行均以排序键 JSON 逐字比对期望与实际的完整对象，24 行全部 MATCH。

## 4. 边界与未覆盖（诚实声明）

- **本卡未改任何源码**：t3 的实现（MoveTask.ts / ReportTask.ts 接线）由研发子卡 t-eaafd0 落盘；联调仅做接口验证与留证。
- **三处产生点仍直写 `executions.push(`，不在本卡范围**：`src/http/routers/tasks.ts:90`（看板任务流转，t4 / t-15c076）、`src/application/use-cases/AdvanceChain.ts:141` 与 `ExecuteTask.ts:239`（自动链，t5 / t-00bed8）。本卡接口面（agent `MoveTask`/`ReportTask`）已全部经助手。
- **工具壳级只覆盖 `reqboard_task_move` / `reqboard_task_report` 两个工具**；其余工具未触达本卡接口面。
- **横切面是抽样而非穷举**：I-6 仅抽 3 个错误码证明「错误码面不变」；done 凭证门、父卡并发上限等既有闸门本卡未新增/未改动。
- 探针以**内存端口 + 临时工作区**驱动，未起 :13080 真实服务；HTTP 路由级联调属 t4（看板路由）范围。父卡验收命令 `ledger-v6-token.test.ts`（开工写 start / 中途汇报刷新 / unavailable 不产出 delta）已在真实用例编排下全绿（5 files / 61 tests passed）。
