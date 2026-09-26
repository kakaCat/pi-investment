# t-81b9be E2E 测试 - RTM 完整流程

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
E2E 测试 - RTM 完整流程

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
执行：`npx vitest run packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts`
期望：
1. 完整流程测试通过（所有断言成功）
2. 覆盖 3 个关键路径：拆分填充 → 提交填充 → 验收更新 → 门禁通过 → 自动归档
3. 测试用例运行时间 < 5s

## 实施方案（implementation）
1. 创建 `packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts`
2. 模拟完整流程：创建需求 → decompose → submit(verification) → accept_sheet（部分通过）→ 返工 → accept_sheet（全部通过）→ 自动归档
3. 编写断言验证每个阶段的数据正确性

## 上游产出摘要（dependsSummary）
- 工具集成 - reqboard_decompose 填充 task_coverage
- 工具集成 - reqboard_submit 填充 acceptance_tracking
- 工具集成 - reqboard_accept_sheet 更新 acceptance_tracking
- 工具集成 - reqboard_status 显示 FR 覆盖度和验收进度

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T12:52:22.071Z，窗口 session-18ecbbd5-0d45-4816-a90b-3040ed8a1a0c）

E2E 测试完成，验证 RTM 完整流程通过（1/1）

### 完成项

- 创建 E2E 测试 packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts
- - 完整流程测试：拆分 → 提交 → 验收 → 归档
- - 阶段 1（拆分）：验证 3个FR 全部覆盖，task_coverage 正确
- - 阶段 2（提交）：验证生成 12 个验收项（3个FR × 4个验收标准）
- - 阶段 3a（第一次验收）：10/12 通过，门禁阻塞，不应该归档
- - 阶段 3b（返工续验）：只生成 2 项（之前 failed 的），is_rework=true
- - 阶段 3c（第二次验收）：12/12 通过，门禁打开，should_archive=true
- - 阶段 4（状态查询）：覆盖度 100%，验收进度 100%，gate_status=passed
- 测试通过（1/1），运行时间 5ms
- 覆盖关键路径：拆分填充 → 提交填充 → 验收更新 → 门禁通过 → 自动归档

### 改动文件

- `packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts`

### 下一步

下一步：t-8a293d（文档 - RTM 使用指南）

---
