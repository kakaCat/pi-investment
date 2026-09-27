# t-87f0da 定义队列类型与任务契约

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
定义队列类型与任务契约

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

① 聚焦类型检查退出码 0：`npx tsc --noEmit` 作用于仅含本卡两文件的临时 tsconfig（`src/domain/queue/QueueTypes.ts` + `tests/queue-types.test.ts`），实测退出码 0；② 类型级断言编译通过且**故障注入有效**——故意断言一个不存在的字段时 `tsc` 报 TS2344「Type 'false' does not satisfy the constraint 'true'」退出码 2（证明断言非恒真）；③ 脚本/断言比对 `QueueTask` 键集 − `TaskRecord` 键集恰为 `{layer}`（类型级双向包含 + 运行时样本核对）；④ `grep -c '^export interface' src/domain/queue/QueueTypes.ts` 输出 6（≥5）；⑤ `grep -c "from '../../shared/protocol" src/domain/queue/QueueTypes.ts` 命中 1（≥1，复用 TaskRecord 未重定义）；⑥ `npx vitest run tests/queue-types.test.ts` 4/4 通过；⑦ **增量不恶化**：全仓 `npx tsc --noEmit` 错误数 ≤ 基线 164，且与 `domain/queue` / `queue-types` 相关的错误数为 0。※ 原验收①「全仓 tsc 退出码 0」已按增量口径修订——工作区基线因他人未提交重构存在 164 个错误，非本卡可控。

## 实施方案（implementation）
新建 packages/web/dsh-pmboard/src/domain/queue/QueueTypes.ts。导出 QUEUE_VERSION=1 与类型：QueueFile（version/requirement_id/schemaVersion/generated_at/updated_at?/tasks/edges/layers/ready）、QueueTask = TaskRecord & { layer: number }（从 src/shared/protocol.ts import TaskRecord，不重定义字段）、QueueEdge{from,to}、QueueLayer{layer,tasks}、ValidationIssue{rule,message,path?}、ValidationResult{passed,issues}。严禁裁剪 TaskRecord 字段——少一个字段就破坏读方只换数据源的最小回归路径。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T12:56:36.506Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

队列类型契约落地：新增 QueueTypes.ts，用 `QueueTask extends TaskRecord` 把"完整包含任务字段"变成编译期不可能违反的约束（队列只比 TaskRecord 多 layer 一个字段），并定义 QueueFile/QueueEdge/QueueLayer/ValidationIssue/ValidationResult。配套 tests/queue-types.test.ts 用类型级断言 + 故障注入双重证明契约有效。

### 完成项

- 新建 src/domain/queue/QueueTypes.ts：QUEUE_VERSION=1 + 6 个导出（QueueTask/QueueEdge/QueueLayer/ValidationIssue/ValidationResult/QueueFile）
- QueueTask 用 `extends TaskRecord` 而非重新罗列字段——从类型层杜绝"迁移少一个字段"（缺 lastRun 会让子卡凭证门静默失效）
- 写清 version 与 schemaVersion 的分工（格式版本 vs 台账时代），避免后续误用
- 新增 tests/queue-types.test.ts：类型级断言证明 (a) QueueTask 等价 TaskRecord & {layer} (b) 键差集恰为 {layer} (c) TaskRecord 无字段遗漏 (d) layer 为 number (e) 校验规则编号恰为 V-1~V-6
- 故障注入实测：故意构造假事实 → tsc 报 TS2344（Type 'false' does not satisfy 'true'），退出码 2，证明断言真的会拦而非恒真
- 验收④ grep -c '^export interface' = 6（≥5）；验收⑤ grep -c "from '../../shared/protocol" = 1（≥1）

### 改动文件

- `packages/web/dsh-pmboard/src/domain/queue/QueueTypes.ts`
- `packages/web/dsh-pmboard/tests/queue-types.test.ts`

### 下一步

继续 t2（DAG 拓扑分层）。⚠️ 验收①（全仓 npx tsc --noEmit 退出码 0）当前无法满足：src/application/internal/worktree-notice.ts 存在他人未提交的语法错误（第 28 行多余 }），全仓 tsc 退出码 2。已用隔离 tsconfig 单独验证本卡文件退出码 0，且全仓唯一错误不在本卡文件内。此阻塞将影响后续所有以 tsc/build 为验收锚点的卡（t2/t4/t5/t6/t7/t9/t10/t11 等），需人裁决是否修复该文件。

---
