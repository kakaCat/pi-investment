---
req_id: REQ-260927121324-abde
title: 节点级 Token 统计写路径收口 · 测试用例
stage: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
---

# 测试用例（REQ-260927121324-abde）

**一句话**：用「既有单测从 3 red 转 0 red + 新增结构性守卫 + 真实会话抽样」三件事证明
三条写路径都不再漏账，缺失一律在页面上如实呈现。

## 测试策略 <!-- serves: FR-9 -->

- **单元**：token 助手（四桶运算、start/end/delta、degraded 判定）纯函数级；
- **用例级（内存端口）**：`makeHarness` + `FakeSession.tokenSnapshot` 驱动 `executeMoveTask` /
  `executeReportTask` / `transitionRequirement` / `applyTaskRollup`，断言台账字段；
- **路由级**：`createReqboardHandler` + 假请求驱动看板 `task/move`、`req/move`、`verify/*`、`verdicts`；
- **结构守卫**：源码扫描断言「写点只准在助手内」；
- **E2E 抽样**：真实窗口开工一张卡 → 查线上 `/requirements/:id/token`（见验收命令最后一节）。

## 覆盖矩阵 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

| 功能点 | 主要验证点 | 用例/守卫 |
|---|---|---|
| FR-1 | 迁移动用收敛点、无直接赋值、快照带/不带 | requirement-transition-guard + token-transition-helper |
| FR-2 | 批准计划两分支 + 看板确认推进带快照 | confirm-settle-plan-persist + token-transition-helper |
| FR-3 | 看板验收/裁决/回退同源带快照 | verdicts-and-rework + accept-verdicts-snapshot |
| FR-4 | 四处产生点写 start，begin 不再死代码 | ledger-v6-token(任务执行) + task-move-snapshot |
| FR-5 | 完工/汇报写 end 与 delta，不可算则缺省 | ledger-v6-token(任务执行) + task-report |
| FR-6 | rollup 有会话结算、无会话不伪造 | rollup + rollup-snapshot |
| FR-7 | 缺失与 unavailable 都 degraded | token-endpoint + token-fallback |
| FR-8 | 写点收敛到助手，绕过即红灯 | execution-token-guard |
| FR-9 | 四条验收命令全绿 | 汇总回归 |

## 用例表（含实际文件） <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

| 用例 | 场景 | 期望 | 实际文件 |
|---|---|---|---|
| T-1 | agent 任务开工（todo→in_progress） | `executions[0].tokenUsage.start.totals` = 当次快照；delta 缺省 | tests/ledger-v6-token.test.ts |
| T-2 | agent 任务完工（→integrating） | `end.totals` = 第二次快照；`delta` = 两者之差 | tests/ledger-v6-token.test.ts |
| T-3 | 中途 `task_report` | running 执行 end/delta 刷新，outcome 仍 running | tests/ledger-v6-token.test.ts, tests/task-report.test.ts |
| T-4 | 快照不可得 | start/end 记 `unavailable`；`delta === undefined` | tests/ledger-v6-token.test.ts |
| T-5 | 看板 `task/move` 带 sessionId | 与 agent 路径同源写 start/end | tests/task-move-snapshot.test.ts |
| T-6 | 看板 `task/move` 无 sessionId | 不写快照，读路径 degraded=true | tests/task-move-snapshot.test.ts |
| T-7 | 需求迁移带 snap | 离开节点进 byStage，新事件带投影快照 | tests/token-transition-helper.test.ts |
| T-8 | 需求迁移无 snap | 不结算、事件无快照（缺失不等于 0） | tests/token-transition-helper.test.ts |
| T-9 | 看板 `req/move` | 经收敛点迁移；带 sessionId 时事件带快照 | tests/requirement-transition-guard.test.ts |
| T-10 | 看板 `verify/pass\|rework` | 经收敛点；accepting 有值或如实无快照 | tests/verdicts-and-rework.test.ts |
| T-11 | 逐项裁决 failed 自动回退 | 回退事件带快照（有会话时） | tests/accept-verdicts-snapshot.test.ts |
| T-12 | 批准计划 → 实施（正常分支） | implementing 事件带投影快照 | tests/confirm-settle-plan-persist.test.ts |
| T-13 | rollup 有会话 | `implementing` 节点在 byStage 中有值 | tests/rollup-snapshot.test.ts |
| T-14 | rollup 无会话（启动对账） | 不产生伪造快照，节点保持无快照 | tests/rollup-snapshot.test.ts |
| T-15 | 读路径：事件缺 tokenSnapshot | `degraded === true` | tests/token-endpoint.test.ts |
| T-16 | 读路径：执行缺 start/end | `degraded === true` | tests/token-endpoint.test.ts, tests/token-fallback.test.ts |
| T-17 | 读路径：全投影数据 | `degraded === false`（既有断言保持） | tests/token-endpoint.test.ts |
| T-18 | 结构性守卫 | `executions.push(` / `tokenUsage` 写点只在助手内 | tests/execution-token-guard.test.ts |
| T-19 | 迁移收敛守卫 | `src/application`+`src/http` 无 `req.status =` | tests/requirement-transition-guard.test.ts |
| T-20 | 四桶/格式契约 | 既有 token 数学契约保持 | tests/token-usage.test.ts |

## 失败形态（写路径漏快照即红灯） <!-- serves: FR-8, FR-9 -->

1. 把任一处 `openExecution` 的 `snap` 实参去掉 → T-1/T-2/T-5 变红（token 单测失败）。
2. 在任意非助手文件新增 `executions.push(` 或 `execution.tokenUsage = …` → T-18 变红。
3. 在 `src/application`/`src/http` 新增 `req.status = to` → T-19 变红。
4. 把读路径缺失判定改回「只认 unavailable」 → T-15/T-16 变红。

## 验收命令 <!-- serves: FR-9 -->

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts
# 期望：0 failed（修复前 3 failed | 16 passed）

npx vitest run tests/token-endpoint.test.ts tests/verdicts-and-rework.test.ts tests/accept-verdicts-snapshot.test.ts tests/rollup-snapshot.test.ts tests/execution-token-guard.test.ts tests/requirement-transition-guard.test.ts tests/task-move-snapshot.test.ts
# 期望：0 failed

grep -rn "req.status = \|r.status = " src/application src/http
# 期望：只命中 application/internal/token-usage.ts（收敛点内部）

grep -rn "beginExecutionToken" src/
# 期望：看到 token-usage.ts 内的调用方（不再是死代码）

curl -s http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token | jq '.data.degraded'
# 期望：true（修复前 false）
```
