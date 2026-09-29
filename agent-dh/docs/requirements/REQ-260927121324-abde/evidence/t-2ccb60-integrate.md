# t-2ccb60 接口联调记录（REQ-260927121324-abde · 父卡 t-15c076「看板任务流转/建卡改卡带写时快照」· 阶段 integrate）

> 验收标准：接口联调通过：给出请求样例与期望响应，实际返回与预期一致。
> 结论：**通过** —— 看板任务三个 HTTP 入口（`POST /dashboard/api/reqboard/task/create` · `/task/move` · `/task/update`）
> 共 **27 例三方比对 27/27 MATCH，MISMATCH=0**；父卡验收命令（直写残留 grep + 2 个测试文件）与相关 token 助手回归同时复跑通过。

## 1. 联调对象（接口面）

父卡 t-15c076 的交付面是「看板任务流转/建卡改卡接到执行快照收敛助手，并按请求体可选 `sessionId` 带写时快照」，
共 3 个 HTTP 入口、8 个接口面：

| 编号 | 接口（代码位置） | 请求样例 | 期望响应语义 |
|---|---|---|---|
| I-1 | `POST /task/create`（`src/http/routers/tasks.ts:56-97`） | `{"requirementId":"REQ-i0001","title":"联调卡","phase":"implement","side":"backend","dependsOn":[],"scope":{apis:[],tables:[],files:[]},"sessionId":"session-w-001"}` | 200；新卡 `todo`、`executions:[]`；建卡触发的 R3 派生推进（design→decomposing）事件带 `tokenSnapshot` |
| I-2 | 同 I-1，无 `sessionId` / 空串 / 端口无该窗口 | 同上去掉 `sessionId`（或 `""`） | 200；推进照旧发生，但事件**不带** `tokenSnapshot`（诚实不传，禁止伪造） |
| I-3 | `POST /task/move` 开工（`tasks.ts:99-158`） | `{"id":"t-000001","to":"in_progress","sessionId":"session-w-001"}` | 200；`claimedBy/claimedAt` 落会话；经 `openExecution` 落 running 执行 + `tokenUsage.start`；`actor=system ⇒ trigger=auto` |
| I-4 | 同 I-3，离开执行段 | `{"id":"t-000001","to":"testing","sessionId":"session-w-001"}`（回退 `todo`） | 经 `closeExecutions` 写 `endedAt/outcome`（回退=cancelled）+ `tokenUsage.end/delta` |
| I-5 | 同 I-3/I-4，无 `sessionId` | `{"id":"t-000001","to":"in_progress"}` | 200；**不落执行记录**、不认领、不写任何 token 字段（既有契约） |
| I-6 | `POST /task/update`（`tasks.ts:160-194`） | `{"id":"t-000001","title":"改标题·联调","sessionId":"session-w-001"}` | 200；改卡触发的派生推进事件带快照；改卡本身不写 token 字段 |
| I-7 | 横切：快照端口 | 端口给快照 / `undefined` / `source=unavailable`；或不注入 `tokenSnapshot`；或端口抛错 | 有则落账；取不到 → 不写（或如实记 `unavailable`、不产 `delta`）；端口缺省 → 不伪造；端口抛错 → 请求失败但**台账无部分写入** |
| I-8 | 横切：错误码面 | 未知任务 / 非法状态 / agent 越人工门 / `sessionId` 非字符串 | `404 not_found` / `400 invalid_input` / `403 human_gate` 逐字不变 |

联调方式：临时探针 `packages/web/dsh-pmboard/tests/__probe-t2ccb60.test.ts` 以**真实模块 + 真实 HTTP 路由 handler**
（`createReqboardHandler`）+ **真实 JSON 台账适配器**（`JsonLedgerRepository`）+ 临时工作区驱动，逐例把
「请求样例 / 期望响应（探针内手工写死）/ 实际返回（实现真实产生）」三方比对，`afterAll` 打印 verdict 表并断言
`MISMATCH=0`。探针已按仓库惯例跑完即删（不留在仓库）。

## 2. 联调命令与输出摘要

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/__probe-t2ccb60.test.ts
 ✓ tests/__probe-t2ccb60.test.ts (18 tests) 413ms
 Test Files  1 passed (1)
      Tests  18 passed (18)
 → 对照表 27 例，MISMATCH=0
```

父卡验收命令（复跑，与探针独立）：

```
$ npx vitest run tests/routes-rollup.test.ts tests/rollup.test.ts
 ✓ tests/rollup.test.ts (16 tests) 4ms
 ✓ tests/routes-rollup.test.ts (3 tests) 166ms
 Test Files  2 passed (2)
      Tests  19 passed (19)

$ grep -n "executions.push(" src/http/routers/tasks.ts
（无输出 → exit=1；本卡范围内直写残留为 0，执行记录只经 t1 助手产生）
```

收敛点接线静态确认（建卡/流转/改卡三入口共用同一口径）：

```
$ grep -nE "openExecution|closeExecutions|snapshotOf|rollupSnapshot|sessionIdOf" src/http/routers/tasks.ts
25:import { closeExecutions, openExecution } from '../../application/internal/token-usage.js'
39:  function sessionIdOf(body)                  ← 唯一会话码解析（缺省/空串 → undefined）
47:  function snapshotOf(sessionId)              ← 唯一快照取值（无会话不取）
52:  function rollupSnapshot(sessionId)          ← 唯一 rollup 提供者（无会话不给）
59:  const sessionId = sessionIdOf(body)         ← handleTaskCreate
105: const sessionId = sessionIdOf(body)         ← handleTaskMove
163: const sessionId = sessionIdOf(body)         ← handleTaskUpdate
91 / 144 / 188: applyTaskRollup({... snapshot: rollupSnapshot(sessionId) }, ...)   ← 三入口同源
118: openExecution(task, {...}, snapshotOf(sessionId))
131: closeExecutions(task, {...}, snapshotOf(sessionId))
```

相关 token 助手回归（本卡接口面所依赖的 t1 契约）：

```
$ npx vitest run tests/execution-snapshot-helpers.test.ts tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts
 ✓ tests/token-usage.test.ts (11 tests) 3ms
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests) 4ms
 ✓ tests/ledger-v6-token.test.ts (8 tests) 38ms
 Test Files  4 passed (4)
      Tests  36 passed (36)
```

## 3. 三方对照表（请求样例 / 期望响应 / 实际返回）

```
MATCH    | A-1 | POST /task/create 带 sessionId（建卡触发 R3 派生推进） | 请求: {"requirementId":"REQ-i0001","title":"联调卡","phase":"implement","side":"backend","dependsOn":[],"scope":{apis:[],tables:[],files:[]},"sessionId":"session-w-001"} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"decomposing","statusCode":200,"success":true,"taskExecutions":[],"taskStatus":"todo"} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"decomposing","statusCode":200,"success":true,"taskExecutions":[],"taskStatus":"todo"}
MATCH    | A-2 | POST /task/create 不带 sessionId（端口有数据也不取） | 请求: {"requirementId":"REQ-i0001","title":"联调卡","phase":"implement","side":"backend","dependsOn":[],"scope":{...}} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"success":true,"taskStatus":"todo"} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"success":true,"taskStatus":"todo"}
MATCH    | A-3 | POST /task/create sessionId=""（空串 → undefined） | 请求: {"requirementId":"REQ-i0001",...,"sessionId":""} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200}
MATCH    | A-4 | POST /task/create 带 sessionId，端口返回 undefined | 请求: {"requirementId":"REQ-i0001",...,"sessionId":"session-w-001"}（端口无该窗口） | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200}
MATCH    | B-1 | POST /task/move 开工带 sessionId（openExecution 写 start + 认领） | 请求: {"id":"t-000001","to":"in_progress","sessionId":"session-w-001"} | 期望: {"claimedAt":1000000,"claimedBy":"session-w-001","exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"in_progress","statusCode":200,"version":2} | 实际: {"claimedAt":1000000,"claimedBy":"session-w-001","exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"in_progress","statusCode":200,"version":2}
MATCH    | B-2 | POST /task/move 离开 in_progress 带 sessionId（closeExecutions 写 end/delta） | 请求: {"id":"t-000001","to":"testing","sessionId":"session-w-001"} | 期望: {"exec":{"endedAt":1000000,"idPrefix":"e-","outcome":"succeeded","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"delta":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":5,"uncachedInputTokens":15},"end":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":7,"uncachedInputTokens":25}},"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"testing","statusCode":200,"version":3} | 实际: {"exec":{"endedAt":1000000,"idPrefix":"e-","outcome":"succeeded","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"delta":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":5,"uncachedInputTokens":15},"end":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":7,"uncachedInputTokens":25}},"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"testing","statusCode":200,"version":3}
MATCH    | B-3 | POST /task/move 开工不带 sessionId（不落执行记录、不认领、不写 token） | 请求: {"id":"t-000001","to":"in_progress"} | 期望: {"claimedAt":null,"claimedBy":null,"executions":[],"status":"in_progress","statusCode":200} | 实际: {"claimedAt":null,"claimedBy":null,"executions":[],"status":"in_progress","statusCode":200}
MATCH    | B-4 | POST /task/move 收尾不带 sessionId（无 running 记录可闭合，不写 end/delta） | 请求: {"id":"t-000001","to":"testing"} | 期望: {"executions":[],"status":"testing","statusCode":200} | 实际: {"executions":[],"status":"testing","statusCode":200}
MATCH    | B-5 | POST /task/move 回退 todo 带 sessionId（cancelled + delta + 解除认领） | 请求: {"id":"t-000001","to":"todo","sessionId":"session-w-001"} | 期望: {"claimedAt":null,"claimedBy":null,"exec":{"endedAt":1000000,"idPrefix":"e-","outcome":"cancelled","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"delta":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":5,"uncachedInputTokens":15},"end":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":7,"uncachedInputTokens":25}},"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"todo","statusCode":200} | 实际: {"claimedAt":null,"claimedBy":null,"exec":{"endedAt":1000000,"idPrefix":"e-","outcome":"cancelled","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"delta":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":5,"uncachedInputTokens":15},"end":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":40,"cacheWriteTokens":0,"outputTokens":7,"uncachedInputTokens":25}},"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"manual"},"status":"todo","statusCode":200}
MATCH    | B-6 | POST /task/move done 带 sessionId（implementing→accepting 派生推进带快照） | 请求: {"id":"t-000001","to":"done","sessionId":"session-w-001"} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"accepting","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"accepting","status":"done","statusCode":200} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"accepting","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"accepting","status":"done","statusCode":200}
MATCH    | B-7 | POST /task/move done 不带 sessionId（派生推进无快照） | 请求: {"id":"t-000001","to":"done"} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"accepting","tokenSnapshot":null},"reqStatus":"accepting","status":"done","statusCode":200} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"accepting","tokenSnapshot":null},"reqStatus":"accepting","status":"done","statusCode":200}
MATCH    | B-8 | POST /task/move actor=system 带 sessionId（trigger=auto） | 请求: {"id":"t-000001","to":"in_progress","actor":"system","sessionId":"session-w-001"} | 期望: {"exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"auto"},"statusCode":200} | 实际: {"exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":20,"cacheWriteTokens":0,"outputTokens":2,"uncachedInputTokens":10}}},"trigger":"auto"},"statusCode":200}
MATCH    | C-1 | POST /task/update 带 sessionId（design→decomposing 派生推进带快照） | 请求: {"id":"t-000001","title":"改标题·联调","sessionId":"session-w-001"} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"decomposing","statusCode":200,"title":"改标题·联调","version":2} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":{"at":1000000,"sessionId":"session-w-001","source":"projection","totals":{"cacheReadTokens":4,"cacheWriteTokens":0,"outputTokens":1,"uncachedInputTokens":3}}},"reqStatus":"decomposing","statusCode":200,"title":"改标题·联调","version":2}
MATCH    | C-2 | POST /task/update 不带 sessionId（派生推进无快照） | 请求: {"id":"t-000001","title":"改标题·联调"} | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"title":"改标题·联调"} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"title":"改标题·联调"}
MATCH    | C-3 | POST /task/update 带 sessionId 但不触发推进（任务无 token 字段） | 请求: {"id":"t-000001","blocked":true,"blockedReason":"联调","sessionId":"session-w-001"} | 期望: {"blocked":true,"blockedReason":"联调","executions":[],"statusCode":200,"tokenUsageKeys":[]} | 实际: {"blocked":true,"blockedReason":"联调","executions":[],"statusCode":200,"tokenUsageKeys":[]}
MATCH    | D-1 | POST /task/move sessionId=""（空串 → undefined，诚实降级：不落执行记录） | 请求: {"id":"t-000001","to":"in_progress","sessionId":""} | 期望: {"claimedAt":null,"claimedBy":null,"executions":[],"status":"in_progress","statusCode":200} | 实际: {"claimedAt":null,"claimedBy":null,"executions":[],"status":"in_progress","statusCode":200}
MATCH    | D-2 | POST /task/create 有 sessionId 但注入未提供 tokenSnapshot | 请求: {"requirementId":"REQ-i0001",...,"sessionId":"session-w-001"}（无 tokenSnapshot 依赖） | 期望: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"taskStatus":"todo"} | 实际: {"lastEvent":{"by":{"kind":"system"},"status":"decomposing","tokenSnapshot":null},"reqStatus":"decomposing","statusCode":200,"taskStatus":"todo"}
MATCH    | D-2b | POST /task/move 有 sessionId 但注入未提供 tokenSnapshot（记录会话、不写 token） | 请求: {"id":"t-000001","to":"in_progress","sessionId":"session-w-001"}（无 tokenSnapshot 依赖） | 期望: {"exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":null,"trigger":"manual"},"statusCode":200} | 实际: {"exec":{"endedAt":null,"idPrefix":"e-","outcome":"running","sessionId":"session-w-001","startedAt":1000000,"tokenUsage":null,"trigger":"manual"},"statusCode":200}
MATCH    | D-3 | POST /task/move 开工：端口 source=unavailable（如实落 start、不造数） | 请求: {"id":"t-000001","to":"in_progress","sessionId":"session-w-001"}（端口 unavailable） | 期望: {"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}}}} | 实际: {"tokenUsage":{"start":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}}}}
MATCH    | D-3b | POST /task/move 收尾：两端 unavailable（写 end、无 delta） | 请求: {"id":"t-000001","to":"testing","sessionId":"session-w-001"}（端口 unavailable） | 期望: {"tokenUsage":{"end":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":99,"uncachedInputTokens":99}},"start":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}}}} | 实际: {"tokenUsage":{"end":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":99,"uncachedInputTokens":99}},"start":{"at":1000000,"sessionId":"session-w-001","source":"unavailable","totals":{"cacheReadTokens":0,"cacheWriteTokens":0,"outputTokens":0,"uncachedInputTokens":0}}}}
MATCH    | D-5 | POST /task/move 快照端口抛错（注入侧需自行兜底） | 请求: {"id":"t-000001","to":"in_progress","sessionId":"session-w-001"}（tokenSnapshot 抛 Error(boom)） | 期望: {"code":null,"ledgerExecutions":[],"ledgerTaskStatus":"todo","statusCode":500,"success":false} | 实际: {"code":null,"ledgerExecutions":[],"ledgerTaskStatus":"todo","statusCode":500,"success":false}
MATCH    | D-4a | POST /task/move 未知任务 | 请求: {"id":"t-ffffff","to":"in_progress","sessionId":"session-w-001"} | 期望: {"code":"not_found","statusCode":404,"success":false} | 实际: {"code":"not_found","statusCode":404,"success":false}
MATCH    | D-4b | POST /task/move 非法状态 | 请求: {"id":"t-000001","to":"nope"} | 期望: {"code":"invalid_input","statusCode":400,"success":false} | 实际: {"code":"invalid_input","statusCode":400,"success":false}
MATCH    | D-4c | POST /task/move 取消（agent 越人工门） | 请求: {"id":"t-000001","to":"canceled","actor":"agent"} | 期望: {"code":"human_gate","statusCode":403,"success":false} | 实际: {"code":"human_gate","statusCode":403,"success":false}
MATCH    | D-4d | POST /task/create 未知需求 | 请求: {"requirementId":"REQ-nope","title":"x","phase":"implement","side":"backend","dependsOn":[],"scope":{...}} | 期望: {"code":"not_found","statusCode":404,"success":false} | 实际: {"code":"not_found","statusCode":404,"success":false}
MATCH    | D-4e | POST /task/move sessionId 类型非法 | 请求: {"id":"t-000001","to":"in_progress","sessionId":123} | 期望: {"code":"invalid_input","statusCode":400,"success":false} | 实际: {"code":"invalid_input","statusCode":400,"success":false}
MATCH    | D-4f | POST /task/update 未知任务 | 请求: {"id":"t-ffffff","sessionId":"session-w-001"} | 期望: {"code":"not_found","statusCode":404,"success":false} | 实际: {"code":"not_found","statusCode":404,"success":false}
```

> 说明：探针运行时对每一行均以「按键排序的稳定 JSON」逐字比对期望与实际的完整投影对象，27 行全部 MATCH；
> 上表为探针 stdout 原样摘录（未改写）。

## 4. 边界与未覆盖（诚实声明）

- **本卡未改源码**：实现由研发子卡 t-726c22 落盘；联调仅做接口验证与留证。
- **无会话不落执行记录是既有契约，非本卡缺口**：`/task/move` 只在 `startsExecutionSegment(to) && sessionId` 时产生执行记录，
  无会话（缺省/空串）时 `executions: []`、不认领、不写任何 token 字段——与需求 §接口「带 sessionId 时同源写 start/end」一致，
  也与 agent 侧 `MoveTask.ts` 同形；B-3/B-4/D-1 如实记录该行为（探针初稿曾误期望"落记录不写 token"，已按真实契约更正）。
- **路由层 `snapshotOf` 不自行 try/catch 端口异常**：D-5 实测端口抛错时请求以 500 结束，且台账无部分写入（任务仍 `todo`、`executions:[]`）。
  生产注入侧 `src/index.ts:430-435` 已把端口包在 try/catch 内（返回 `undefined` → 视为无快照）；本卡未改注入侧，
  「端口不得抛错」属接线契约，不是本卡接口面。
- **探针以真实 handler + 临时目录台账驱动，未起 :13080 常驻服务**：真实 socket / 鉴权 / SSE 传输层不在本卡接口面内。
- **只覆盖本卡 3 个 HTTP 入口**：agent 侧（`MoveTask.ts`/`ReportTask.ts`，t3）、自动链（`AdvanceChain.ts`/`ExecuteTask.ts`，t5）、
  需求迁移路由（t2）、读路径 degraded（t6）不在本卡范围。
- **横切面是抽样而非穷举**：I-7/I-8 各抽若干代表例；并发下同一卡两次开工、done 凭证门等既有闸门本卡未新增/未改动。
