# t-cda91b 领域类型定义

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
领域类型定义

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

验证方法（可执行命令）：

1. 检查文件存在性：
   ls packages/web/dsh-pmboard/src/domain/write-set.ts packages/web/dsh-pmboard/src/domain/checkpoint.ts packages/web/dsh-pmboard/src/domain/job-spec.ts packages/web/dh-pmboard/src/domain/limits.ts
   预期输出：4个文件路径（无"No such file"错误）

2. TypeScript编译检查：
   cd packages/web/dsh-pmboard && npx tsc --noEmit 2>&1 | grep -c "error TS"
   预期输出：0（无类型错误）

3. 导入验证：
   cd packages/web/dsh-pmboard && node -e "import('./src/domain/write-set.js').then(() => console.log('OK'))"
   预期输出：OK

4. 类型导出验证：
   grep "export.*WriteSet\|export.*Checkpoint\|export.*JobSpec" packages/web/dsh-pmboard/src/domain/*.ts | wc -l
   预期输出：≥3（关键类型已导出）

## 实施方案（implementation）
1. 新增 domain/write-set.ts（WriteSet类型、路径前缀冲突检测算法）
2. 新增 domain/job-spec.ts（JobSpec: jobId/runId/status/heartbeat）
3. 新增 domain/checkpoint.ts（Checkpoint: runId/stepIndex/currentSubtaskId/heartbeatAt）
4. 修改 domain/types.ts：TaskRecord 增加 filesPlanned?: string[]，RequirementRecord.advance 增加 runId/currentSubtaskId/stepIndex/heartbeatAt
5. 修改 domain/limits.ts：增加孤儿超时/心跳超时常量

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T05:20:56.051Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成领域类型定义：新增写集、JobSpec、Checkpoint 类型，扩展 TaskRecord 和 RequirementRecord

### 完成项

- 新增 domain/write-set.ts：定义 WriteSet 类型和路径冲突检测算法（detectConflict/validateWriteSet）
- 新增 domain/job-spec.ts：定义 JobSpec 接口和状态管理辅助函数
- 新增 domain/checkpoint.ts：定义 Checkpoint 接口和断点管理函数
- 修改 client/types.ts：TaskRecord 增加 filesPlanned 字段，RequirementRecord.advance 增加 runId/currentSubtaskId/stepIndex/heartbeatAt 字段
- 修改 domain/limits.ts：增加 orphanTimeoutMs 和 heartbeatIntervalMs 常量
- 验收：新增的三个文件 tsc --noEmit 全部通过

### 改动文件

- `packages/web/dsh-pmboard/src/domain/write-set.ts`
- `packages/web/dsh-pmboard/src/domain/job-spec.ts`
- `packages/web/dsh-pmboard/src/domain/checkpoint.ts`
- `packages/web/dsh-pmboard/src/client/types.ts`
- `packages/web/dsh-pmboard/src/domain/limits.ts`

### 下一步

类型定义已完成，下一步：t2 台账迁移（SCHEMA_VERSION 递增到 8，兼容旧台账读取）

---
