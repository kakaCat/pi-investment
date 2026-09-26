# t-7edc1c 工具集成 - reqboard_submit 填充 acceptance_tracking

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具集成 - reqboard_submit 填充 acceptance_tracking

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-submit.test.ts`
期望：
1. 测试用例"提交验收"：3 个 FR（12 个验收项），返回 acceptance_tracking_count=12，rtm.yaml 包含 12 条 pending 记录
2. 测试用例"续验"：上版 2 项 failed，本次只生成这 2 项（不重复生成 passed 项）

## 实施方案（implementation）
1. 修改 `packages/tools/reqboard/src/tools/reqboard-submit.ts`
2. 在 kind=verification 分支，调用 RTMManager.fillAcceptanceTracking
3. 返回值新增 acceptance_tracking_count 字段
4. 编写集成测试覆盖 2 个场景

## 上游产出摘要（dependsSummary）
- 数据模型 - RTM 类型定义
- 工具实现 - FR 文件解析器
- 工具实现 - RTM 管理器（核心）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T12:24:41.053Z，窗口 session-18ecbbd5-0d45-4816-a90b-3040ed8a1a0c）

已完成 reqboard_submit 的 RTM 集成，所有测试通过（3/3）

### 完成项

- 创建 RTM 集成辅助函数 packages/web/dsh-pmboard/src/application/internal/submit-rtm-integration.ts
- - generateAcceptanceTracking: 从 FR 文件生成验收追踪
- - 支持返工模式：只生成上版 failed 的项
- 修改 packages/web/dsh-pmboard/src/application/use-cases/SubmitVerification.ts
- - 添加 generateAcceptanceTracking 导入
- - 在返回前调用 RTM 集成
- - 返回值新增 acceptance_tracking_count 字段
- - 返工时自动标记 rework_only=true
- 创建集成测试 packages/web/dsh-pmboard/tests/submit-rtm-integration.test.ts
- - 提交验收场景：3个FR/12个验收项，返回 count=12
- - 续验场景：上版2项failed，只生成这2项
- - 兼容性场景：无FR文件不报错
- 所有测试通过（3/3）

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/submit-rtm-integration.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/SubmitVerification.ts`
- `packages/web/dsh-pmboard/tests/submit-rtm-integration.test.ts`

### 下一步

下一步：t-a965eb（reqboard_accept_sheet 更新 acceptance_tracking）

---
