# t-9a6bdb 下沉产物发现核心并薄壳化 ArtifactSync

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
下沉产物发现核心并薄壳化 ArtifactSync

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/sync-artifacts.test.ts 全绿且既有断言逐字不变；npx vitest run tests/layer-boundary.test.ts 不新增越界（新增文件位于 application 且不 import node:/adapters）

## 实施方案（implementation）
新增 packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts（discoverArtifactsFrom(docs,req) 纯函数，走 DocRepository 端口）；改 packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts 为薄壳调它 + 落库（行为零变更）；回归 packages/web/dsh-pmboard/tests/sync-artifacts.test.ts。

## 上游产出摘要（dependsSummary）
- 定义新契约类型与端口

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
