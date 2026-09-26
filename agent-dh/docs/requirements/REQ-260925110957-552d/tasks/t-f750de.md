# t-f750de 孤儿回收

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
孤儿回收

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
单测验证：超时+无心跳→孤儿；attempt+1；选择器可选中 resume 卡

## 实施方案（implementation）
1. 新增 application/internal/orphan-recovery.ts
2. 实现 identifyOrphans(subtasks, activeJobIds, thresholdMs) → SubtaskRecord[]
3. 判定：status=in_progress 且 lastHeartbeat 超阈值（3分钟）且不在 activeJobIds
4. 新增 tests/unit/orphan-recovery.test.ts 覆盖边界（刚启动、正常心跳、真孤儿）

## 上游产出摘要（dependsSummary）
- 领域类型定义

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T06:52:40.014Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成孤儿回收：识别超时且无活跃执行的 in_progress 子卡

### 完成项

- 新增 application/internal/orphan-collector.ts：孤儿识别算法
- 实现 identifyOrphans()：识别所有孤儿任务
- 实现 isOrphan()：判断单个任务是否为孤儿
- 实现 calculateRetryAttempt()：计算重试次数
- 孤儿判定：status=in_progress 且心跳超时（默认3分钟）
- 新增 tests/unit/orphan-collector.test.ts：16个测试全部通过
- 测试覆盖：正常运行、超时、边界情况、不同状态、无执行记录、混合场景、自定义阈值

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/orphan-collector.ts`
- `packages/web/dsh-pmboard/tests/unit/orphan-collector.test.ts`

### 下一步

孤儿回收完成，下一步：t8 checkpoint 管理器（批次3最后一个）

---

### 验证方法（可执行命令）
1. 单元测试通过: `cd packages/web/dsh-pmboard && npx vitest run tests/unit/orphan-collector.test.ts` 预期输出包含 "tests" 和 "passed"
2. identifyOrphans存在: `grep "export function identifyOrphans" packages/web/dsh-pmboard/src/application/internal/orphan-collector.ts` 预期有输出
