# t-bdbab2 追溯链标签改造（文件名中文 + 任务卡逐张展开）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
追溯链标签改造（文件名中文 + 任务卡逐张展开）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
pnpm vitest run tests/stage-panel.test.ts 全绿（含 TC-006 新增断言：design 显示「架构文档」等中文名、任务卡逐张带名称、不再出现「任务卡×」、缺失红字保留）；grep -n "ARTIFACT_KIND_LABELS" src/client/stage-panel.ts 无命中；pnpm typecheck 通过

## 实施方案（implementation）
src/client/stage-panel.ts：1. 删 L60 ARTIFACT_KIND_LABELS 表，三处 ?? kind 兜底改 artifactKindLabel(kind)。2. traceNodeLabel（L88）：单份产物→artifactKindLabel；design 多份→docFileLabel(artifact.path, kind)；tooltip 完整路径不动。3. renderTraceChain（L562-569）：删 task_detail 折叠分支，逐条渲染；新增 taskTitleByCardDoc(payload) 建 cardDoc→title 映射，命中用 StageTaskRef.title，标签=taskCardLabel(path,title)，匹配不到降级「任务卡（t-xxx）」；缺失红字「（缺失）」分支不变。4. tests/stage-panel.test.ts 扩展 TC-006。

## 上游产出摘要（dependsSummary）
- 新增 artifact-labels 唯一事实源模块与防漂移单测

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T13:35:19.068Z，窗口 session-89aa3b25-9e19-48c0-a032-cf932135f88b）

追溯链完成中文化改造——这是本需求用户可见的核心变化：①设计节点的多份文档不再裸显 architecture.md / interfaces.md 等英文文件名，主标签直接显示「架构文档」「接口文档」（完整路径保留在 tooltip，排查线索不丢）；②任务卡不再折叠成「任务卡×N」，逐张列出且带任务名称（如「任务卡 · 实现映射模块」，经产物路径↔任务卡文档精确匹配取任务名，匹配不到降级「任务卡（t-xxx）」）；③未知文件名中文兜底「设计文档（foo.md）」；缺失必备产物的红字「（缺失）」行为不变。改造经 renderStageNode 共用入口，看板与会话流程节点面板同时生效。

### 完成项

- stage-panel.ts：删本地 ARTIFACT_KIND_LABELS 表，三处取值改 artifactKindLabel
- traceNodeLabel：design 多份改 docFileLabel（中文文档名），单份产物仍种类名
- renderTraceChain：删 task_detail「×N」折叠分支，逐张渲染 taskCardLabel(path, 匹配的 title)
- 新增 taskTitleByCardDoc(payload)：decompose/implement 节点体 tasks 建 cardDoc→title 映射
- tests/stage-panel.test.ts：更新 2 处旧断言 + 新增 TC-006a~d（带名称展开/降级编号/未知文件名兜底/缺失红字保留）
- 验收：stage-panel.test.ts 53/53 绿；grep ARTIFACT_KIND_LABELS 在 stage-panel.ts 零命中；typecheck exit 0

### 改动文件

- `packages/web/dsh-pmboard/src/client/stage-panel.ts`
- `packages/web/dsh-pmboard/tests/stage-panel.test.ts`

### 下一步

t6 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）

---
