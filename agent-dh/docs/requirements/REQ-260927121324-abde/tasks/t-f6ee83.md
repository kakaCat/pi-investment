# t-f6ee83 需求迁移写路径统一经收敛点并带写时快照

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
需求迁移写路径统一经收敛点并带写时快照

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd packages/web/dsh-pmboard && grep -rn "req.status = \|r.status = " src/application src/http 只剩 src/application/internal/token-usage.ts 一处；npx vitest run tests/token-transition-helper.test.ts tests/verdicts-and-rework.test.ts tests/confirm-settle-plan-persist.test.ts 通过。

## 实施方案（implementation）
confirm-settle.ts:278/:304 批准计划→实施两分支补 snap: captureSnapshot(deps, d.windowKey)；http/routers/requirements.ts:111-115 的 req.status/version/updatedAt/updatedBy/recordStatus 五连写改调 transitionRequirement（快照取请求体可选 sessionId 再回落 r.sourceSessionId，取不到诚实不传）；requirements.ts:270 看板确认即推进补 snap 并给 actor 带 sessionId；http/routers/verdicts.ts:106-112 五连写改经 transitionRequirement，:170-172 applyVerdicts 补第 8 实参 snap；HandleFailure.ts:87/:109 直接赋值改经 transitionRequirement（snap 用 req.sourceSessionId，取不到则不传）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
