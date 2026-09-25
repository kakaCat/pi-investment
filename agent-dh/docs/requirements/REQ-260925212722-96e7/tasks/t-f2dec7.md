# t-f2dec7 验收门禁

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
验收门禁

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
1. 文件存在：ls packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts
2. 导出正确：grep "export.*acceptanceGateCheck" src/application/gate/acceptance-gate.ts
3. 单元测试通过：pnpm test -- acceptance-gate.test.ts
4. 集成测试：验收单有失败项 → 无法归档

## 实施方案（implementation）
创建 acceptance-gate.ts：实现 acceptanceGateCheck(req: Requirement): Promise<GateResult> 函数，检查所有 functional_requirements 的 acceptance_status，返回 GateResult（passed/failed_clauses）。创建单元测试 acceptance-gate.test.ts。

## 上游产出摘要（dependsSummary）
- 扩展数据结构

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T14:47:31.192Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成验收门禁：实现 acceptanceGateCheck 函数，检查所有 FR 的 acceptance_status，单元测试全部通过

### 完成项

- 创建 packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts
- 实现 acceptanceGateCheck(req, workspaceRoot) 函数
- 检查 functional_requirements.acceptance_status 是否为 passed
- 返回失败条款列表（failed_clauses）
- 创建单元测试 tests/unit/gate/acceptance-gate.test.ts
- 3 个测试用例全部通过：全部通过、部分失败、RTM 不存在
- 编译验证通过

### 改动文件

- `packages/web/dsh-pmboard/src/application/gate/acceptance-gate.ts`
- `packages/web/dsh-pmboard/tests/unit/gate/acceptance-gate.test.ts`

### 下一步

推进任务到 done 状态，提交检查点

---
