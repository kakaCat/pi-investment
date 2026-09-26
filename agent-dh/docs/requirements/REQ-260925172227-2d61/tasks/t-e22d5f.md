# t-e22d5f 工具集成 - reqboard_status 显示 FR 覆盖度和验收进度

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具集成 - reqboard_status 显示 FR 覆盖度和验收进度

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-status.test.ts`
期望：
1. 返回包含 fr_coverage（total_frs=3, covered_frs=2, unreceived_clauses=[FR-3], coverage_rate=67%）
2. 返回包含 fr_acceptance_progress（total=12, passed=10, failed=2, pass_rate=83%, gate_status=blocked）

## 实施方案（implementation）
1. 修改 `packages/tools/reqboard/src/tools/reqboard-status.ts`
2. 新增 fr_coverage 字段（调用 CoverageChecker.checkCoverage）
3. 新增 fr_acceptance_progress 字段（调用 AcceptanceGate.checkGate）
4. 编写集成测试验证 2 个字段

## 上游产出摘要（dependsSummary）
- 数据模型 - RTM 类型定义
- 工具实现 - RTM 管理器（核心）
- 工具实现 - 覆盖度检查器
- 工具实现 - 验收门禁

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T12:49:10.271Z，窗口 session-18ecbbd5-0d45-4816-a90b-3040ed8a1a0c）

已完成 reqboard_status 的 RTM 集成，所有测试通过（3/3）

### 完成项

- 创建 Status RTM 集成辅助函数 packages/web/dsh-pmboard/src/application/internal/status-rtm-integration.ts
- - generateStatusRTM: 生成 FR 覆盖度和验收进度
- - 返回 fr_coverage（total_frs/covered_frs/unreceived_clauses/coverage_rate）
- - 返回 fr_acceptance_progress（total/passed/failed/pending/pass_rate/gate_status）
- 修改 packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts
- - 在 schema 中添加 fr_coverage 和 fr_acceptance_progress 字段
- 修改 packages/web/dsh-pmboard/src/application/query/QueryState.ts
- - 添加 generateStatusRTM 导入
- - 在返回前调用 RTM 集成
- - 有验收单时自动添加验收进度
- 创建集成测试 packages/web/dsh-pmboard/tests/status-rtm-integration.test.ts
- - FR覆盖度场景：3个FR/2个已覆盖，返回 67%
- - 验收进度场景：12项/10 passed/2 failed，返回 83% + blocked
- - 兼容性场景：无FR文件不报错
- 所有测试通过（3/3）

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/status-rtm-integration.ts`
- `packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`
- `packages/web/dsh-pmboard/src/application/query/QueryState.ts`
- `packages/web/dsh-pmboard/tests/status-rtm-integration.test.ts`

### 下一步

下一步：t-81b9be（E2E 测试 - RTM 完整流程）

---
