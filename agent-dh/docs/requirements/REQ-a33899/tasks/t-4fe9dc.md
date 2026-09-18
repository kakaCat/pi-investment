# t-4fe9dc 台账 v6 + 写路径快照与迁移

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
台账 v6 + 写路径快照与迁移

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
单测：跨 2 节点后 StatusEvent 含 tokenSnapshot；任务写 start/end/delta；v5 样例可 load 不改版本；迁移后 schemaVersion=6 且 migrations 有 {from:5,to:6}；pnpm test 全绿。

## 实施方案（implementation）
改 src/shared/protocol.ts、src/application/use-cases/MoveRequirement.ts、MoveTask.ts、ReportTask.ts、src/application/internal/*、scripts/migrate-ledger.ts；测试 tests/ledger-v6-token.test.ts。验证：pnpm test。

## 上游产出摘要（dependsSummary）
- 立 Token 契约与纯函数
- 会话 Token 读取端口与降级

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T21:50:44.177Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

台账 schema v6 + 写路径快照 + 迁移：StatusEvent.tokenSnapshot / ExecutionRecord.tokenUsage / RequirementRecord.tokenUsage 三个可选字段落地，REQBOARD_SCHEMA_VERSION 5→6；新增 application/internal/token-usage.ts（captureSnapshot / entrySnapshotFor / accumulateStageDelta / begin·endExecutionToken，负差截断、同会话才相减、不可得就不记）；CreateRequirement 立项即写 draft 事件+快照，MoveRequirement 结算离开节点差值并给新事件带快照，MoveTask 开工/完工写 start/end/delta，ReportTask 刷新运行中执行的中途进度；migrate-ledger.ts 改为链式 v4→v5→v6（逐段留痕、幂等）。

### 完成项

- protocol.ts：StatusEvent.tokenSnapshot / ExecutionRecord.tokenUsage / RequirementRecord.tokenUsage + recordStatus 透传快照 + SCHEMA_VERSION=6
- application/internal/token-usage.ts：写路径单点实现（缺失不补 0、跨会话不减法）
- CreateRequirement / MoveRequirement / MoveTask / ReportTask 全部接入写时快照
- scripts/migrate-ledger.ts：链式 v4→v5→v6，migrations 逐段留痕，已是 v6 幂等
- 新增 tests/ledger-v6-token.test.ts 8 条；更新 4 个既有测试的 schemaVersion 期望到 6；migration 测试改链式期望
- pnpm typecheck 通过；全量测试仅剩 1 例基线红（board-info-fixes #8，改动前即红）

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/shared/protocol.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/internal/token-usage.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/internal/support.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/application/use-cases/ReportTask.ts`
- `agent-dh/packages/pages/dsh-pmboard/scripts/migrate-ledger.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/ledger-v6-token.test.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/migration.test.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/timeline.test.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/application/repository.test.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/acceptance-criteria.test.ts`

### 下一步

t4：读路径装配与 HTTP（/requirements/:id/token + progress/state 扩展）。

---
