# t-b4e6df 工具实现 - RTM 管理器（核心）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具实现 - RTM 管理器（核心）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
执行：`npx vitest run packages/tools/reqboard/tests/rtm/rtm-manager.test.ts`
期望：
1. fillTaskCoverage: 输入 2 个任务，输出 task_coverage 包含 2 项，covers_acceptance 正确填充
2. fillAcceptanceTracking: 输入 3 个 FR（共 12 个验收项），输出 12 条 pending 记录
3. updateAcceptanceTracking: 输入 judgements（10 passed, 2 failed），更新后状态正确

## 实施方案（implementation）
1. 创建 `packages/tools/reqboard/src/rtm/rtm-manager.ts`
2. 实现 RTMManager 类的 3 个方法：fillTaskCoverage / fillAcceptanceTracking / updateAcceptanceTracking
3. 编写单元测试覆盖所有方法

## 上游产出摘要（dependsSummary）
- 数据模型 - RTM 类型定义
- 工具实现 - FR 文件解析器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T11:23:33.848Z，窗口 session-18ecbbd5-0d45-4816-a90b-3040ed8a1a0c）

已完成 RTM 管理器核心功能，实现了 3 个关键方法，所有测试通过（3/3）

### 完成项

- 创建 packages/tools/reqboard/src/rtm/rtm-manager.ts
- fillTaskCoverage: 根据任务的 requirement_refs 填充 task_coverage
- - 扫描 FR 文件获取所有验收标准
- - 为每个任务生成 covers_frs 和 covers_acceptance
- fillAcceptanceTracking: 从 FR 元数据生成初始验收追踪
- - 所有验收项初始状态为 pending
- - 包含 description 和 verification 信息
- updateAcceptanceTracking: 根据裁决结果更新验收状态
- - 支持 passed/failed 两种状态
- - 记录 evidence、feedback、judged_at、judged_by
- 更新 FR 解析器，支持两种验收项格式（- **A1**: 和 - A1:）
- 创建单元测试 packages/tools/reqboard/tests/rtm/rtm-manager.test.ts
- 所有测试通过（3/3）

### 改动文件

- `packages/tools/reqboard/src/rtm/rtm-manager.ts`
- `packages/tools/reqboard/src/rtm/fr-parser.ts`
- `packages/tools/reqboard/tests/rtm/rtm-manager.test.ts`

### 下一步

下一步可以并行执行：t-2a7c20（覆盖度检查器）和 t-627cc8（验收门禁），它们都依赖本任务

---
