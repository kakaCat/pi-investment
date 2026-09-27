# t-0e7fac 实现 DAG 拓扑分层与派生视图

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 DAG 拓扑分层与派生视图

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

① npx vitest run tests/queue/topology.test.ts 全绿（TC-1.1~TC-1.7）；② 菱形 t1→{t2,t3}→t4 断言 layers 等于 [[t1],[t2,t3],[t4]] 且 ready 等于 ['t1']；③ 环输入断言抛错且 message 包含 CIRCULAR；④ 空输入断言返回空三件套且未抛错；⑤ grep -c "node:fs" src/domain/queue/topology.ts 输出 0（纯函数）。※ 原验收①路径 src/domain/queue/topology.test.ts 不可执行（本仓 vitest.config.ts 的 include 为 tests/**/*.test.ts），按开工实测修订为 tests/queue/topology.test.ts，未改 vitest 配置。

## 实施方案（implementation）
新建 src/domain/queue/topology.ts，实现纯函数：computeLayers(tasks)（Kahn 入度分层；有环抛 Error 含 CIRCULAR）、computeEdges(tasks)（由 dependsOn 展开）、computeReady(tasks)（依赖全 done 且自身 todo 者入 ready）。computeReady 必须是唯一实现，写路径不得另写一份（否则 V-5 假就绪/漏就绪必现）。配 topology.test.ts 覆盖线性/菱形/多层/环/空/多 ready/依赖已 done 七种形状。

## 上游产出摘要（dependsSummary）
- 定义队列类型与任务契约

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T13:13:27.746Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

队列现在能自己算「执行批次」了：给一组带依赖的任务，它能算出先做哪些、再做哪些的分层结果，并算出「此刻就能动手」的 ready 列表；遇到互相依赖成环会直接报错并给出 CIRCULAR 错误码，而不是悄悄返回一个空列表。看板甘特与后续调度据此排批次，不用再人工数依赖。

### 完成项

- src/domain/queue/topology.ts：computeEdges / computeLayers / computeReady 三个纯函数（不 import node:fs / node: 任何模块）
- 环依赖抛 CIRCULAR_DEPENDENCY 错误码而非静默返回空 ready（TC-1.3）
- 空输入返回空三件套且不抛错（TC-1.4）
- tests/queue/topology.test.ts 15 用例覆盖：线性链/菱形/多 ready/依赖已 done/多层/自环/悬空引用/去重/不改入参
- Lead 独立复核：vitest 15/15 通过、grep -c node:fs = 0

### 改动文件

- `packages/web/dsh-pmboard/src/domain/queue/topology.ts`
- `packages/web/dsh-pmboard/tests/queue/topology.test.ts`

### 下一步

t-394339 队列数据校验 V-1~V-6（validateQueue.ts + 测试）

---
