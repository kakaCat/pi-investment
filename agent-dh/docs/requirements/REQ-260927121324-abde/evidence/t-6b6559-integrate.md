# t-6b6559 接口联调记录（REQ-260927121324-abde · 父卡 t-806d6e「新增执行快照收敛助手（任务执行唯一写入口）」· 阶段 integrate）

> 验收标准：接口联调通过：给出请求样例与期望响应，实际返回与预期一致。
> 结论：**通过** —— 6 个导出 × 20 例三方比对 **20/20 MATCH，MISMATCH=0**。

## 1. 联调对象（接口面 = src/application/internal/token-usage.ts 的 6 个导出）

| 编号 | 接口（请求签名） | 期望响应语义 |
|---|---|---|
| I-1 | `openExecution(task, spec, snap?)` | 落 1 条执行记录；running 且 snap 可得 → 写 start、delta 留空；born-failed（outcome='failed'）→ 不写 start、直接 endedAt=at；snap=undefined → 不写任何 token 字段 |
| I-2 | `closeExecutions(task, {at,outcome,error?}, snap?)` | 闭合**全部** running（写 endedAt/outcome/error）并写 end+delta，返回闭合条数；snap=undefined → 只闭合记录、不写 end/delta；已闭合的不再动 |
| I-3 | `refreshRunningExecution(task, snap, sessionId?)` | 命中最近一条同会话 running → 写 end/delta、**outcome 保持 running**，返回 true；未命中 → false 且不写；sessionId 缺省 = 不限会话 |
| I-4 | `snapshotForWindow(deps, windowKey?)` | 窗口码缺失/空串 → undefined（不伪造）；有窗口码 → 端口快照；端口抛错 → `{source:'unavailable', totals:empty}`（不阻断主流程） |
| I-5 | `safeWindowKey(deps, exec?)` | 真实窗口码直取；`'system'` 哨兵 / 空串 / 端口抛错 / 端口返回非字符串 → undefined |
| I-6 | `snapshotProviderFor(deps, windowKey?)` | 派生函数：显式窗口码优先，回落 `req.sourceSessionId`；两者都缺 → undefined（不触发端口调用） |
| I-7 | （横切）缺失≠0 | start/end 均 `source='unavailable'` → 如实落账但不产出 delta（禁止编造） |

联调方式：临时探针 `packages/web/dsh-pmboard/tests/__probe-t6b6559.test.ts` 以**真实模块**（token-usage.ts）＋内存端口（tests/application/harness.ts）逐例调用，把「请求样例 / 期望响应 / 实际返回」三方比对后打印 verdict 表并断言 MISMATCH=0。探针已按惯例跑完即删（不留在仓库）。

## 2. 联调命令与输出摘要

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/__probe-t6b6559.test.ts
 ✓ tests/__probe-t6b6559.test.ts (6 tests)
 Test Files  1 passed (1)
      Tests  6 passed (6)
 → 对照表 20 例，MISMATCH=0
```

父卡验收命令（t1 交付面）：
```
$ grep -nE "export function (openExecution|closeExecutions|refreshRunningExecution|snapshotForWindow|safeWindowKey|snapshotProviderFor)" src/application/internal/token-usage.ts
148:openExecution  175:closeExecutions  192:refreshRunningExecution  207:snapshotForWindow  216:safeWindowKey  230:snapshotProviderFor
COUNT=6   （期望 6，实际 6）

$ npx vitest run tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts
 Test Files  2 passed (2)
      Tests  25 passed (25)   （execution-snapshot-helpers 14/14 + token-usage 11/11）
```

接口类型面（证明导出可被调用方按签名消费）：
```
$ npx tsc --noEmit -p tsconfig.json  →  token-usage.ts 命中 0 条 error
（注：包内另有 118 条既有 TS error，全部落在与 t1 无关的文件，属并行工作线遗留，本卡未触碰）
```

## 3. 三方对照表（请求样例 / 期望响应 / 实际返回）

```
===== t-6b6559 接口联调对照表 =====
MATCH   | I-1a | openExecution(task, spec, snap) | 请求: task.executions=[]; spec={id:'e-1',sessionId:'s',trigger:'manual',at:10}; snap=projection(B(2),'s') | 期望: {"records":1,"outcome":"running","startedAt":10,"endedAt":null,"start":{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},"delta":null} | 实际: {"records":1,"outcome":"running","startedAt":10,"endedAt":null,"start":{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},"delta":null}
MATCH   | I-1b | openExecution born-failed | 请求: spec={id:'e-1',trigger:'auto',at:10,outcome:'failed',error:'gate'}; snap=projection(B(2)) | 期望: {"records":1,"outcome":"failed","endedAt":10,"error":"gate","tokenUsage":null} | 实际: {"records":1,"outcome":"failed","endedAt":10,"error":"gate","tokenUsage":null}
MATCH   | I-1c | openExecution snap=undefined | 请求: spec={id:'e-1',trigger:'manual',at:10}; snap 不传 | 期望: {"records":1,"tokenUsage":null} | 实际: {"records":1,"tokenUsage":null}
MATCH   | I-2a | closeExecutions(task, opts, snap) | 请求: opts={at:20,outcome:'succeeded'}; snap=projection(B(5),'s') | 期望: {"closed":2,"outcomes":["succeeded","succeeded"],"endedAt":[20,20],"start":[{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0}],"end":[{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0},{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0}],"delta":[{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0},{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}]} | 实际: {"closed":2,"outcomes":["succeeded","succeeded"],"endedAt":[20,20],"start":[{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0}],"end":[{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0},{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0}],"delta":[{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0},{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}]}
MATCH   | I-2b | closeExecutions snap=undefined | 请求: opts={at:20,outcome:'failed',error:'boom'}; snap 不传 | 期望: {"closed":1,"first":{"endedAt":20,"error":"boom","start":{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},"end":null,"delta":null},"born":{"outcome":"failed","endedAt":11,"tokenUsage":null}} | 实际: {"closed":1,"first":{"endedAt":20,"error":"boom","start":{"uncachedInputTokens":2,"outputTokens":4,"cacheReadTokens":20,"cacheWriteTokens":0},"end":null,"delta":null},"born":{"outcome":"failed","endedAt":11,"tokenUsage":null}}
MATCH   | I-3a | refreshRunningExecution(task, snap, sessionId) | 请求: snap=projection(B(4),'s'); sessionId='s' | 期望: {"hit":true,"e2":{"outcome":"running","end":{"uncachedInputTokens":4,"outputTokens":8,"cacheReadTokens":40,"cacheWriteTokens":0},"delta":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}},"e1End":null} | 实际: {"hit":true,"e2":{"outcome":"running","end":{"uncachedInputTokens":4,"outputTokens":8,"cacheReadTokens":40,"cacheWriteTokens":0},"delta":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}},"e1End":null}
MATCH   | I-3b | refreshRunningExecution 未命中 | 请求: sessionId='s' 但无同会话 running | 期望: {"hit":false,"e1End":null} | 实际: {"hit":false,"e1End":null}
MATCH   | I-3c | refreshRunningExecution sessionId 缺省 | 请求: snap=projection(B(5)); 不传 sessionId | 期望: {"hit":true,"e2":{"outcome":"running","end":{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0},"delta":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}},"e1End":null} | 实际: {"hit":true,"e2":{"outcome":"running","end":{"uncachedInputTokens":5,"outputTokens":10,"cacheReadTokens":50,"cacheWriteTokens":0},"delta":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0}},"e1End":null}
MATCH   | I-4a | snapshotForWindow(deps, undefined|"") | 请求: windowKey 缺失 / 空串 | 期望: {"missing":null,"empty":null} | 实际: {"missing":null,"empty":null}
MATCH   | I-4b | snapshotForWindow(deps, "session-w-001") | 请求: windowKey='session-w-001'; 端口返回 projection(B(3)) | 期望: {"totals":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0},"source":"projection","sessionId":"session-w-001"} | 实际: {"totals":{"uncachedInputTokens":3,"outputTokens":6,"cacheReadTokens":30,"cacheWriteTokens":0},"source":"projection","sessionId":"session-w-001"}
MATCH   | I-4c | snapshotForWindow 端口抛错 | 请求: tokenTotals 抛 Error(boom) | 期望: {"source":"unavailable","totals":{"uncachedInputTokens":0,"outputTokens":0,"cacheReadTokens":0,"cacheWriteTokens":0}} | 实际: {"source":"unavailable","totals":{"uncachedInputTokens":0,"outputTokens":0,"cacheReadTokens":0,"cacheWriteTokens":0}}
MATCH   | I-5a | safeWindowKey 正常 | 请求: exec={agent:{id:'session-w-001'}} | 期望: "session-w-001" | 实际: "session-w-001"
MATCH   | I-5b | safeWindowKey system 哨兵 | 请求: exec={agent:{id:'system'}} | 期望: null | 实际: null
MATCH   | I-5c | safeWindowKey 空串 | 请求: exec={agent:{id:''}} | 期望: null | 实际: null
MATCH   | I-5d | safeWindowKey 端口抛错 | 请求: windowKey 抛 REQBOARD_AGENT_REQUIRED | 期望: null | 实际: null
MATCH   | I-5e | safeWindowKey 脏值（非字符串） | 请求: windowKey 返回 123 | 期望: null | 实际: null
MATCH   | I-6a | snapshotProviderFor 显式窗口码优先 | 请求: windowKey='win-a'; req.sourceSessionId='req-sess' | 期望: {"totals":{"uncachedInputTokens":7,"outputTokens":14,"cacheReadTokens":70,"cacheWriteTokens":0},"seen":["win-a"]} | 实际: {"totals":{"uncachedInputTokens":7,"outputTokens":14,"cacheReadTokens":70,"cacheWriteTokens":0},"seen":["win-a"]}
MATCH   | I-6b | snapshotProviderFor 退回 sourceSessionId | 请求: windowKey 缺失; req.sourceSessionId='req-sess' | 期望: {"totals":{"uncachedInputTokens":7,"outputTokens":14,"cacheReadTokens":70,"cacheWriteTokens":0},"seen":["win-a","req-sess"]} | 实际: {"totals":{"uncachedInputTokens":7,"outputTokens":14,"cacheReadTokens":70,"cacheWriteTokens":0},"seen":["win-a","req-sess"]}
MATCH   | I-6c | snapshotProviderFor 都无 → undefined | 请求: windowKey 缺失; req.sourceSessionId=undefined | 期望: {"snapshot":null,"seen":["win-a","req-sess"]} | 实际: {"snapshot":null,"seen":["win-a","req-sess"]}
MATCH   | I-7 | open+close 均 unavailable | 请求: start/end 快照 source=unavailable | 期望: {"startSource":"unavailable","endSource":"unavailable","delta":null} | 实际: {"startSource":"unavailable","endSource":"unavailable","delta":null}
===== 共 20 例，MISMATCH=0 =====
```

## 4. 边界与未覆盖（诚实声明）

- **caller 级联调不在本卡范围**：把 openExecution/closeExecutions/refreshRunningExecution 接到真实写路径（`MoveTask`/`ReportTask`/`tasks.ts`/`AdvanceChain`/`ExecuteTask`）是 t-030788（t3）/ t-15c076（t4）/ t-00bed8（t5）三张卡的工作。
- 因此 `tests/ledger-v6-token.test.ts` 仍有 **3 例红**（REQ-a33899 t3 的「开工写 start / 中途汇报刷新 / unavailable 不产出 delta」），失败原因是调用方尚未改经助手（`MoveTask.executions.push` 未替换），**不是本卡接口的缺陷**；该 3 例即计划中「由 3 failed 转 0 failed」的基线，随 t3 接线转绿。本卡交付面（6 导出接口契约）已全绿。
- 本卡未改任何源码：t1 的实现与 14 例契约测试由研发子卡 t-882d5d 落盘（见 t-806d6e 汇报 1），联调仅做接口验证与留证。
