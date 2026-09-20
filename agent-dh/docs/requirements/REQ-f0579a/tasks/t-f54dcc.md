# t-f54dcc 恢复看板视图三处回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
恢复看板视图三处回归

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
npx vitest run tests/client-view.test.ts 全绿；buildBoard 输出含 dsh-pm-archived-bar 与「待归档」；产物标签含种类可读名且保留文件名（af8a2ac0 诉求）

## 实施方案（implementation）
views/board.ts：toReqCards 不再过滤 done、accepting 泳道恢复含 done、恢复底部 archived-bar 段（按 f215753f 原样）；views/verification.ts collectReqDocs 的 label 改为「种类名 · 文件名」双呈现

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T10:43:25.176Z，窗口 session-dd6cfa29-d8ff-43fe-99d7-371a69442076）

恢复看板视图三处回归：done 归验收泳道（REQ-6f39b5）、底部归档条（M3 原样恢复）、产物标签双呈现（种类名·文件名）

### 完成项

- toReqCards 不再过滤 done（972b2262 覆盖丢失恢复）
- accepting 泳道恢复含 done
- buildBoard 底部归档条恢复（lanes 视图）
- collectReqDocs 标签改为「种类可读名 · 文件名」（兼容 af8a2ac0 真名诉求）

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/client/views/board.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/views/verification.ts`

### 下一步

t3 精确化操作条 move-req 断言

---
