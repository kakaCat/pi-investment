# t-3b1e6d 拆分门禁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
拆分门禁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
1. 文件存在：ls packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts
2. 导出正确：grep "export.*taskCoverageGateCheck" src/application/gate/task-coverage-gate.ts
3. 单元测试通过：pnpm test -- task-coverage-gate.test.ts
4. 集成测试：拆分计划遗漏一个 FR → 被拒绝

## 实施方案（implementation）
创建 task-coverage-gate.ts：实现 taskCoverageGateCheck(req: Requirement): Promise<GateResult> 函数，检查所有 functional_requirements 的 task_refs 是否非空，返回 GateResult（passed/orphan_clauses）。创建单元测试 task-coverage-gate.test.ts。

## 上游产出摘要（dependsSummary）
- 扩展数据结构

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T14:33:54.759Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成拆分门禁：实现 taskCoverageGateCheck 函数，检查所有 FR 的 task_refs，单元测试全部通过

### 完成项

- 创建 packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts
- 实现 taskCoverageGateCheck(req, workspaceRoot) 函数
- 检查 functional_requirements.task_refs 是否非空
- 返回孤儿条款列表（orphan_clauses）
- 创建单元测试 tests/unit/gate/task-coverage-gate.test.ts
- 3 个测试用例全部通过：完整场景、部分缺失、RTM 不存在
- 编译验证通过

### 改动文件

- `packages/web/dsh-pmboard/src/application/gate/task-coverage-gate.ts`
- `packages/web/dsh-pmboard/tests/unit/gate/task-coverage-gate.test.ts`

### 下一步

推进任务到 done 状态，提交检查点

---
