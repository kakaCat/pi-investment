# t-9af0f9 集成门禁到 MoveRequirement

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
集成门禁到 MoveRequirement

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
1. 代码包含门禁检查：grep "designGateCheck" packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts
2. 三个门禁检查都已集成
3. E2E 测试：门禁不通过时推进被阻塞

## 实施方案（implementation）
修改 MoveRequirement.ts：在 design → decomposing 推进前调用 designGateCheck，在 decomposing → implementing 推进前调用 taskCoverageGateCheck，在 accepting → archived 推进前调用 acceptanceGateCheck。门禁不通过时抛出错误，阻塞推进。

## 上游产出摘要（dependsSummary）
- 门禁系统统一导出

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T14:52:24.203Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成集成门禁到 MoveRequirement：在状态推进前调用三个 RTM 门禁检查，门禁不通过时阻塞推进

### 完成项

- 在 MoveRequirement.ts 顶部添加门禁函数 import
- 集成设计门禁：design → decomposing 时检查 design_refs
- 集成拆分门禁：decomposing → implementing 时检查 task_refs
- 集成验收门禁：accepting → archived 时检查 acceptance_status
- 门禁不通过时 reject 并返回错误码
- 编译验证通过

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`

### 下一步

推进任务到 done 状态，提交检查点

---
