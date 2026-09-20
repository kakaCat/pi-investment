# t-dd6c5c 看板通道 B：确认即推进 + 链侧投递

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
看板通道 B：确认即推进 + 链侧投递

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/artifact-confirm-board.test.ts（新增）断言 POST /req/artifact/confirm 返回体 advanced=true 且 delivered=true；agents.get 返 undefined 时返回体 advanced=false 且 note 包含"窗口不在线"；B 后再走 A 只推进一次

## 实施方案（implementation）
扩展 http/routers/requirements.ts 的 confirm handler；http/routes.ts deps 加 delivery/chain；index.ts 注入

## 上游产出摘要（dependsSummary）
- 后置链框架：H1..H5 + 两相执行 + 幂等/降级
- 修投递死链路：AgentDeliverer 统一投递形状

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T06:35:52.808Z，窗口 session-878da638-a076-4266-ae40-70a2390060f2）

看板通道 B 纳入切面：POST /req/artifact/confirm 由"只落章"升级为"确认即推进 + 链侧投递"，两件事都以「绑定窗口在线」为前提；窗口离线只落章并如实说明。通道 A/B 至此对**人**的语义一致：确认一次 = 门开 + 自动往下走。

### 完成项

- handleArtifactConfirm 扩展：① 落章（既有行为不变）② 窗口在线才推进（按闸门目录 gateFromStage 推导目标状态，只对 autoAdvance 白名单生效）③ 入链（enqueue + runPending，会话句柄取自 agent.session 供 H2 使用）
- 新增护栏：确认的产物必须**正是该门要求的产物**（gate.requiredKind === kind）——否则二次确认同一产物会顺着新状态的门再推进一次（连跳两格）
- 响应体新增 advanced / delivered / note 三字段；离线与幂等命中都带如实说明，不伪造成功
- RouterCtx.deps 与 ReqboardRouteDeps 增 gateChain / agents；组合根 index.ts 注入（链与 agents 服务）
- 新增 tests/artifact-confirm-board.test.ts 4 用例：在线→advanced=true 且 delivered=true 且状态已推进且链路 executed=1；离线→advanced=false、note 含「窗口不在线」、状态未推进、落章仍发生；二次确认→不再推进（幂等）；未登记产物→400 拒绝（既有语义不变）
- 门禁核验：tsc 无新增错误（仅基线一条）；全量 vitest 与 pristine 基线 diff → 新增失败 0（14 vs 15）；客户端产物重建并过 verify-client
- 顺带修正：http 层新增消息一律走 fmt（不引入中文字面量拼接，避免触发该层的棘轮约束）

### 改动文件

- `packages/pages/dsh-pmboard/src/http/routers/requirements.ts`
- `packages/pages/dsh-pmboard/src/http/routers/shared.ts`
- `packages/pages/dsh-pmboard/src/http/routes.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/artifact-confirm-board.test.ts`

### 下一步

t8 立项 pm 专有弹框（需 REQ-99f5fe 停手）；t10 门禁收口 + 文档漂移同步

---
