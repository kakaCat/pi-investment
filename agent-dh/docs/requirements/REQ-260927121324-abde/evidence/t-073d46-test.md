# t-073d46 测试记录（REQ-260927121324-abde · 父卡 t-a6293c「读路径把快照缺失与不可得同等计入 degraded」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**源码层通过** —— 父卡「得到什么结果」的 vitest 口径命令全绿（3 files / 18 tests，exit 0），
> 读路径对**真台账** REQ-260927100007-b8ba 的源码头路径判定 `degraded=true`（与父卡期望一致）；
> 但**线上 curl 口径仍为 false**：运行实例加载的 dist 产物陈旧（复核卡 D-1），需 `pnpm build` + 重启后复验。
> 本卡为测试卡，未改任何源码；探针跑完即删。

- 测试时间：2026-09-27 14:57–14:59（+08:00）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面：`src/application/query/QueryRequirementToken.ts`（唯一变更文件，git diff 仅 2 hunk）

---

## 1. 目标命令 A —— 父卡「得到什么结果」vitest 口径（`通过`）

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/token-endpoint.test.ts tests/token-fallback.test.ts tests/token-degraded-integration.test.ts

 ✓ tests/token-fallback.test.ts (3 tests) 2ms
 ✓ tests/token-endpoint.test.ts (6 tests) 106ms
 ✓ tests/token-degraded-integration.test.ts (9 tests) 140ms

 Test Files  3 passed (3)
      Tests  18 passed (18)
   Duration  612ms
EXIT=0
```

- 期望：父卡口径两文件通过；实际 **18/18 passed，exit 0**（另并入联调卡落盘的 `token-degraded-integration.test.ts`）。
- 联调用例逐例实测（HTTP 边界 · 真路由 + 真台账仓储）：`REQ-ok-all-proj→false`、`REQ-gap-missing→true`（事件缺快照·本次主项）、
  `REQ-gap-unavail→true`、`REQ-run-open-ok→false`、`REQ-run-open-gap→true`、`REQ-closed-gap-end→true`、`REQ-no-events→false`，
  响应 `status=200`、`byStage` 恒 7 项、`degraded` 为 boolean。

## 2. 目标命令 B —— 父卡「得到什么结果」curl 口径

### 2.1 源码头路径（对**真台账**）+ `degraded=true` ✅

临时探针以真台账 `.dsh-data/dsh-reqboard.json` 驱动源码 handler（跑完已删）：

```
[探针·真台账] {"hasTokenUsage":true,"events":7,"missingEventSnap":1,"nonProjEventSnap":0,
               "execs":16,"closed":16,"closedMissingStart":16,"closedMissingEnd":16}
[探针·源码头路径] status=200 degraded=true byStage=7
 ✓ tests/__probe-t073d46-real-ledger.test.ts (1 test) 66ms
 Test Files  1 passed (1) / Tests  1 passed (1)   EXIT=0
```

- 台账事实：该需求 7 条状态事件中 **1 条缺 `tokenSnapshot`**；16 条已闭合执行记录 **16/16 缺 start、16/16 缺 end** →
  新判定式下 `degraded=true`，证明父卡期望（修复前 false）在源码头路径已成立。
- 探针删除留痕：`ls tests/ | grep -c "__probe"` → `0`（未落常驻用例；行为用例按拆分计划由 t-49d8d4 落盘）。

### 2.2 线上 curl `http://127.0.0.1:13080` ❌（D-1 未闭环，非本卡可修）

```
$ curl -s -m 8 http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token
degraded=false   (byStage=7)

$ stat -f '%Sm %N' src/application/query/QueryRequirementToken.ts dist/index.mjs
src  14:52:15 2026        (已改)
dist 14:07:14 2026        (陈旧)

$ grep -c hasSnapshotGap dist/index.mjs        → 0
$ grep -c hasUnavailableSnapshot dist/index.mjs → 2
```

- **判定**：线上 false 的根因是**发布落点未闭环**（运行实例按 `package.json main=./dist/index.mjs` 加载旧产物），
  与源码判定无关——同为复核卡 D-1，本卡复现一致。
- **不能在本卡内闭环的原因**：让线上生效必须重启 :13080（该进程即承载本实施链会话），
  重启会中断在途会话、使本卡结果无法回传；构建/重启是发布动作（`agent-dh/scripts/restart-with-build.sh`），
  应由父卡收口阶段或编排方在会话外执行。
- **剩余步骤（交接）**：`cd packages/web/dsh-pmboard && pnpm build`（或 `agent-dh/scripts/restart-with-build.sh`）
  → 重启实例 → 复跑上方 curl，期望 `degraded=true`。在复验通过前，父卡「得到什么结果」的 curl 验收项**视为未达成**。

## 3. 扩展回归（token 一族，独立复跑）

```
$ npx vitest run tests/token-endpoint.test.ts tests/token-fallback.test.ts tests/token-degraded-integration.test.ts \
    tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/ledger-v6-token.test.ts tests/session-probe-token.test.ts

 ✓ tests/token-transition-helper.test.ts (3 tests)
 ✓ tests/token-usage.test.ts (11 tests)
 ✓ tests/session-probe-token.test.ts (6 tests)
 ✓ tests/token-fallback.test.ts (3 tests)
 ✓ tests/ledger-v6-token.test.ts (8 tests)
 ✓ tests/token-endpoint.test.ts (6 tests)
 ✓ tests/token-degraded-integration.test.ts (9 tests)

 Test Files  7 passed (7)
      Tests  46 passed (46)
EXIT=0
```

## 4. 静态复验（不采信上游自述）

```
$ grep -rn "hasUnavailableSnapshot" src/            → 0（旧函数体已删，非并存）
$ grep -rn "hasSnapshotGap" src/
src/application/query/QueryRequirementToken.ts:39:function hasSnapshotGap(req, ledger): boolean {
src/application/query/QueryRequirementToken.ts:106:    degraded: usage === undefined || hasSnapshotGap(req, ledger),
```

`$ git diff -- packages/web/dsh-pmboard/src/application/query/QueryRequirementToken.ts` 仅 2 hunk：

- `:33-52` `hasUnavailableSnapshot` → `hasSnapshotGap`（含注释）：需求侧 `tokenSnapshot === undefined || source !== 'projection'` → gap；
  任务侧 `startOk/endOk`，`endedAt === undefined ? !startOk : !(startOk && endOk)` → gap。
- `:106` `degraded = usage === undefined || hasSnapshotGap(req, ledger)`。
- `byStage`/`executions`/`totals` 装配逻辑与对外形状（`degraded: boolean`）零改动。

---

## 5. 结论

- **目标命令 A 全绿**：3 files / 18 tests passed（exit 0），扩展回归 7 files / 46 tests passed（exit 0），无回归。
- **读路径语义经真台账验证**：源码头路径对 REQ-260927100007-b8ba 判 `degraded=true`，父卡期望成立。
- **目标命令 B 部分未达成**：线上 curl 仍 `degraded=false`，根因是 dist 陈旧（D-1），需 `pnpm build` + 重启后复验；
  本卡为测试卡不越界执行发布动作（重启会中断承载本会话的 :13080 进程）。
- 本卡未改任何源码；临时探针跑完即删；行为用例（含 O-2「已闭合缺 start」对称例）按拆分计划由 t-49d8d4 落盘。

测试人：实施子代理（t-073d46）；时间：2026-09-27 14:5x (+08:00)
