# t-86ae1e 收敛 host 工具回执引用（render-summaries）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
收敛 host 工具回执引用（render-summaries）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
grep -n "SUBMIT_KIND_CN" src/tools/ 无任何命中；pnpm vitest run tests/render-summaries.test.ts 全绿（含 plan→「拆分计划（旧版）」断言）；pnpm typecheck 通过

## 实施方案（implementation）
src/tools/render-summaries.ts 删 L24 SUBMIT_KIND_CN 表，L50 改 artifactKindLabel(kind)；确认 plan 渲染为「拆分计划（旧版）」。

## 上游产出摘要（dependsSummary）
- 新增 artifact-labels 唯一事实源模块与防漂移单测

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T13:31:00.679Z，窗口 session-89aa3b25-9e19-48c0-a032-cf932135f88b）

host 侧工具回执的中文名也已收敛：reqboard_submit 的回执摘要遇到 design/decomposition/task_detail 不再裸显英文，plan 由旧表的「拆分计划」统一为「拆分计划（旧版）」——与看板、会话卡片用词完全一致。至此前端六处本地映射表已收敛五处，仅剩追溯链（t5）。

### 完成项

- render-summaries.ts：删 SUBMIT_KIND_CN 表，import artifactKindLabel
- submitSummary：kind 取值改 artifactKindLabel（plan→「拆分计划（旧版）」术语统一）
- 验收：grep SUBMIT_KIND_CN 在 src/tools/ 零命中；render-summaries.test.ts 20/20 绿；typecheck exit 0

### 改动文件

- `packages/web/dsh-pmboard/src/tools/render-summaries.ts`

### 下一步

t5 追溯链标签改造（stage-panel.ts，本需求的核心可见变化）

---
