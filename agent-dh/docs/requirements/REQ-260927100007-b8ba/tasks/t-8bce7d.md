# t-8bce7d 补齐 MoveTask 契约（现有测试即契约）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
补齐 MoveTask 契约（现有测试即契约）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd packages/web/dsh-pmboard && npx vitest run tests/execute-task.test.ts tests/lazy-expand.test.ts tests/concurrency-limits.test.ts tests/application/use-cases.test.ts 全绿（当前 40 passed / 28 failed）。

## 实施方案（implementation）
按 tests/execute-task.test.ts / lazy-expand.test.ts / concurrency-limits.test.ts / use-cases.test.ts 补齐：父卡开工懒展开子卡（expandSubtasks）、父卡并发上限（REQBOARD_PARENT_LIMIT）、开工返回 task_card{doc_path,implementation}、done 凭证门（REQBOARD_NO_REPORT）、父卡收尾门（REQBOARD_SUBTASK_GATE）、human_gate→REQBOARD_HUMAN_GATE 映射。

## 上游产出摘要（dependsSummary）
- 补 agent 侧需求/任务流转工具

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:45:55.748Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

agent 推进任务时不再"推一半"：开工调用直接把任务卡全文交回（照卡执行，不凭记忆），父卡开工自动带出子卡链并受同需求并发上限约束（第 4 张被拒），转 done 前必须过完工凭证门（无汇报/无文件证据/父卡有未完成子卡一律拒绝）；同时修掉子卡执行一启动就崩的旧缺陷（引擎返回的两层信封被当成产出对象，filesChanged 恒 undefined），并给无后台任务端口的调用方恢复了同步推进链的能力。

### 完成项

- 子卡执行：正确解包 WorkflowRunOutcome（校验 ok → 取 value.output），产出按既有 JSON 契约解析；run 失败/引擎缺失显式失败而非静默成功
- MoveTask 补齐契约：开工返回 task_card{doc_path,implementation}；父卡开工同事务懒展开子卡链；同需求并发父卡上限 REQBOARD_PARENT_LIMIT；转 done 前过 done 凭证门（父卡收尾门 / 子卡三项证据 / REQBOARD_NO_REPORT）
- 用例边界错误码映射：domain human_gate → REQBOARD_HUMAN_GATE（工具与看板各自保持既有码）
- AdvanceChain：抽出 driveChain，无后台任务端口时同步跑完并返回真实停止原因（不再返回 not_found 空壳）；AdvanceState 补 runId 类型
- 测试：execute-task / lazy-expand / concurrency-limits / use-cases 四文件 49 项全绿（此前 28 项红）

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`
- `packages/web/dsh-pmboard/src/application/internal/support.ts`
- `packages/web/dsh-pmboard/src/shared/protocol.ts`

---
