# t-00bed8 接口联调记录（REQ-260927121324-abde · 父卡「自动链任务执行与接手推进改经执行助手并带快照」· 阶段 integrate）

> 验收标准：接口联调通过：给出请求样例与期望响应，实际返回与预期一致。
> 结论：**通过** —— 6 个接口面 / **12 例三方比对 12/12 MATCH，MISMATCH=0**；父卡验收命令（2 个测试文件 + 直写残留 grep）与相关 token/rollup 回归（5 文件 52 例）同时复跑通过。

## 1. 联调对象（接口面）

父卡 t-00bed8 交付面：「自动链父卡开工/收尾、子卡执行开工/收尾、接手推进与启动对账的派生推进」
全部收口到执行快照助手（openExecution / closeExecutions / snapshotProviderFor），**缺失 ≠ 0**。
共 6 个接口面：

| 编号 | 接口（代码位置） | 请求样例 | 期望响应语义 |
|---|---|---|---|
| I-1 | advanceRequirement（AdvanceChain.ts:134-169 openParent / :171-203 finalizeParent / :224-238 rollupStep） | advanceRequirement(deps,'REQ-000001',{agent:{id:'session-auto-7'}})（需求 implementing + 1 父卡 todo） | 父卡执行 trigger=auto、sessionId=exec 会话码、start=开工快照、end=收尾快照、delta=end−start、outcome=succeeded；rollup 事件 accepting 带写时快照 |
| I-2 | 同 I-1，exec 为 system 且需求无 sourceSessionId | advanceRequirement(deps,'REQ-000001',{agent:{id:'system'}}) | 执行记录照落、outcome=succeeded，但**不写** sessionId/token 字段；rollup 事件无 tokenSnapshot；端口 0 次调用 |
| I-4a | executeSubtask（ExecuteTask.ts:253-278 openExecution / :297-324 closeExecutions） | {subtaskId:'t-s',windowKey:'system',exec:{agent:{id:'session-auto-9'}}} | 引擎成功：执行 auto、sessionId=session-auto-9、start/end/delta 齐备 |
| I-4b | 同 I-4a，无引擎（engine_unavailable） | 同上（deps.workflow=undefined） | **born-failed**：outcome=failed、endedAt=startedAt、error='engine_unavailable'，**不写 start/end**（无 tokenUsage）；返回 REQBOARD_SUBTASK_GATE |
| I-4c | 同 I-4a，exec=system 且需求无 sourceSessionId | {subtaskId:'t-s',windowKey:'system',exec:{agent:{id:'system'}}} | 成功但不写任何 token 字段；端口 0 次调用（诚实不传） |
| I-4d | 同 I-4a，exec=system 但需求有 sourceSessionId | 同上（需求 sourceSessionId='session-req-fallback'） | 会话码回落需求绑定窗口 session-req-fallback，start/end/delta 齐备 |
| I-5 | applyPickupAdvance（pm-capture-root.ts:129-140 调用形状） | applyPickupAdvance(ledger,'REQ-pick',{now,commentId,snapshot:snapshotProviderFor(deps,windowKey)}) | 显式窗口码优先 → 回落 req.sourceSessionId → 都无则事件**不带** tokenSnapshot |
| I-6 | 启动对账 applyPickupReconcile / applyTaskRollup（src/index.ts:162-171 不传 snapshot） | applyTaskRollup(ledger,{now,commentId}) / applyPickupReconcile(ledger,{now,commentId}) | 推进照旧发生，但事件**不带** tokenSnapshot（无会话不伪造）；传提供者时带快照（对照） |

联调方式：临时探针 packages/web/dsh-pmboard/tests/__probe-t00bed8.test.ts 以**真实导出用例 + 真实内存端口**
（makeHarness：InMemoryRepo/FakeDocs/FakeSession/FixedClock）驱动，计数式会话快照（第 i 次调用返回
at=1000+i、totals=B(i)、同 sessionId、source=projection），逐例把「请求样例 / 期望响应（探针内手工写死）/
实际返回（实现真实产生）」三方比对，afterAll 打印 verdict 表并断言 MISMATCH=0。探针已按仓库惯例跑完即删（不留在仓库）。

## 2. 联调命令与输出摘要

    $ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
    $ npx vitest run tests/__probe-t00bed8.test.ts
     ✓ tests/__probe-t00bed8.test.ts (12 tests) 10ms
     Test Files  1 passed (1)
          Tests  12 passed (12)
     → 对照表 12 例，MISMATCH=0

父卡验收命令（复跑，与探针独立）：

    $ npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts
     ✓ tests/advance-chain.test.ts (8 tests) 14ms
     ✓ tests/execute-task.test.ts (11 tests) 18ms
     Test Files  2 passed (2) / Tests 19 passed (19)

相关 token / rollup 回归（写路径收敛的既有行为，未被本卡改动破坏）：

    $ npx vitest run tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts tests/ledger-v6-token.test.ts tests/rollup.test.ts tests/routes-rollup.test.ts
     ✓ tests/execution-snapshot-helpers.test.ts
     ✓ tests/token-usage.test.ts
     ✓ tests/ledger-v6-token.test.ts
     ✓ tests/rollup.test.ts
     ✓ tests/routes-rollup.test.ts (3 tests) 169ms
     Test Files  5 passed (5) / Tests 52 passed (52)

## 3. 三方对照表（12 例）

| 编号 | 请求样例 | 期望响应（关键字段） | 实际返回 | 判定 |
|---|---|---|---|---|
| I-4a | {subtaskId:'t-s',windowKey:'system',exec:{agent:{id:'session-auto-9'}}} | ok=true; calls=2; exec.sessionId=session-auto-9; outcome=succeeded; start@1001; end@1002; delta=B(1) | 同左 | MATCH |
| I-4b | 同上（无引擎） | ok=false; calls=2; code=REQBOARD_SUBTASK_GATE; exec.outcome=failed; endedAt=startedAt; error=engine_unavailable; tokenUsage 缺省 | 同左 | MATCH |
| I-4c | exec:{agent:{id:'system'}}; 需求无 sourceSessionId | ok=true; calls=0; exec 无 sessionId、无 tokenUsage; outcome=succeeded | 同左 | MATCH |
| I-4d | exec:{agent:{id:'system'}}; 需求 sourceSessionId=session-req-fallback | ok=true; calls=2; exec.sessionId=session-req-fallback; start@1001/end@1002/delta=B(1) | 同左 | MATCH |
| I-1 | advanceRequirement(deps,'REQ-000001',{agent:{id:'session-auto-7'}}) | stopped=rollup; req=accepting; calls=11; 父卡 sessionId=session-auto-7, succeeded, start@1001, end@1010, delta=B(9); rollup 事件 tokenSnapshot@1011 | 同左 | MATCH |
| I-2 | 同 I-1，exec:{agent:{id:'system'}} + 需求无 sourceSessionId | stopped=rollup; req=accepting; calls=0; 父卡无 sessionId/token；rollup 事件无 tokenSnapshot | 同左 | MATCH |
| I-5a | applyPickupAdvance(..., snapshot:snapshotProviderFor(deps,'session-pick')) | req=brainstorming; calls=1; 事件 tokenSnapshot@1001 sessionId=session-pick | 同左 | MATCH |
| I-5b | snapshotProviderFor(deps,undefined)；需求 sourceSessionId=session-pick | 同上（回落 sourceSessionId） | 同左 | MATCH |
| I-5c | snapshotProviderFor(deps,undefined)；需求无 sourceSessionId | req=brainstorming; calls=0; 事件无 tokenSnapshot | 同左 | MATCH |
| I-6a | applyPickupReconcile(ledger,{now,commentId})（不传 snapshot） | req=brainstorming; calls=0; 事件无 tokenSnapshot | 同左 | MATCH |
| I-6b | applyTaskRollup(ledger,{now,commentId})（不传 snapshot） | advancedCount=1; req=accepting; calls=0; 事件无 tokenSnapshot | 同左 | MATCH |
| I-6c | applyTaskRollup(ledger,{now,commentId,snapshot:snapshotProviderFor(deps,'session-r2')}) | req=accepting; calls=1; 事件 tokenSnapshot@1001 sessionId=session-r2 | 同左 | MATCH |

节选两例原始 JSON（其余同格式）：

    MATCH | I-1 | 请求: {"requirementId":"REQ-000001","exec":{"agent":{"id":"session-auto-7"}}}
    期望: {"stopped":"rollup","reqStatus":"accepting","tokenTotalsCalls":11,"parentExecution":{"sessionId":"session-auto-7","trigger":"auto","startedAt":1000000,"endedAt":1000000,"outcome":"succeeded","tokenUsage":{"start":{"sessionId":"session-auto-7","at":1001,"totals":{"uncachedInputTokens":1,"outputTokens":2,"cacheReadTokens":10,"cacheWriteTokens":0},"source":"projection"},"end":{"sessionId":"session-auto-7","at":1010,"totals":{"uncachedInputTokens":10,"outputTokens":20,"cacheReadTokens":100,"cacheWriteTokens":0},"source":"projection"},"delta":{"uncachedInputTokens":9,"outputTokens":18,"cacheReadTokens":90,"cacheWriteTokens":0}}},"rollupEvent":{"status":"accepting","at":1000000,"by":{"kind":"system"},"reason":"全部 5 个实施任务已完成，自动进入验收","tokenSnapshot":{"sessionId":"session-auto-7","at":1011,...}}}
    实际: （与期望逐字一致）
    MATCH | I-2 | 请求: {"requirementId":"REQ-000001","exec":{"agent":{"id":"system"}}}
    期望: {"stopped":"rollup","reqStatus":"accepting","tokenTotalsCalls":0,"parentExecution":{"trigger":"auto","startedAt":1000000,"endedAt":1000000,"outcome":"succeeded"},"rollupEvent":{"status":"accepting","at":1000000,"by":{"kind":"system"},"reason":"全部 5 个实施任务已完成，自动进入验收"}}
    实际: （与期望逐字一致）

> 说明：I-1/I-2 的 rollup 理由为「全部 **5** 个实施任务已完成」——父卡 + 展开的 4 张子卡共 5 个未取消任务
> （planRollup 的 activeTasksOf 口径），非笔误。

## 4. 结构核查（源码级）

    $ grep -rn "executions.push(" src/application src/http
    src/application/internal/token-usage.ts:113:// 调用方不得自行 task.executions.push(...) 或写 execution.tokenUsage（结构守卫
    src/application/internal/token-usage.ts:160:  task.executions.push(execution)
     → 仅助手自身一处（第 160 行 openExecution 内）+ 其注释；用例/路由**零**直写。
       （卡片原文写「无输出」系指"写点仅助手内"；助手本身即该唯一写点，故 grep 必然命中它。）

    $ grep -rn "tokenUsage =|.tokenUsage." src/application src/http | grep -v internal/token-usage.ts
    src/application/query/QueryRequirementToken.ts:108-109  （仅**读**取 tokenUsage.totals，非写）
     → 写点未散逸。

    $ sed -n '162-171p' src/index.ts
    const ctx: RollupContext = { now: now(), commentId: () => newCommentId() };   // 启动对账明确不传 snapshot（FR-6）
    const advanced = [...applyPickupReconcile(ledger, ctx), ...applyTaskRollup(ledger, ctx)];

    $ sed -n '129-140p' src/wiring/pm-capture-root.ts
    const snapshot = snapshotProviderFor(deps.useCaseDeps(), windowKey);           // 接手推进带写时快照提供者（FR-6）
    .map((d) => applyPickupAdvance(ledger, d.id, { now: deps.now(), commentId: () => newCommentId(), snapshot }))

## 5. 结论

- 12 例三方比对**全部 MATCH**：父卡开工/收尾 + 子卡执行开工/收尾 + 接手推进 + 启动对账的快照语义与「缺失 ≠ 0」纪律，均与实现真实返回一致。
- 会话码解析链（safeWindowKey(deps, exec) ?? req.sourceSessionId）三态（有会话 / 回落到需求 / 诚实不写）实测符合设计：无会话路径端口调用数为 0，执行记录照落但不写任何 token 字段。
- born-failed（outcome=failed）实测**不写 start**，仅以已闭合终止记录落账（endedAt=startedAt）。
- 父卡验收命令与相关 52 例 token/rollup 回归全绿；executions.push( 直写已收敛到助手内唯一一处。
- 未发现偏差，无需返工。
