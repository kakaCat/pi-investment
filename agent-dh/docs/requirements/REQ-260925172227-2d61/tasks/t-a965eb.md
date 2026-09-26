# t-a965eb 工具集成 - reqboard_accept_sheet 更新 acceptance_tracking

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
工具集成 - reqboard_accept_sheet 更新 acceptance_tracking

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
执行：`npx vitest run packages/tools/reqboard/tests/tools/reqboard-accept-sheet.test.ts`
期望：
1. 测试用例"部分通过"：12 项验收（10 passed, 2 failed），返回 gate_status=blocked, archived=false
2. 测试用例"全部通过"：12 项验收（12 passed），返回 gate_status=passed, archived=true，需求状态变为 archived

## 实施方案（implementation）
1. 修改 `packages/tools/reqboard/src/tools/reqboard-accept-sheet.ts`
2. 在用户裁决后，调用 RTMManager.updateAcceptanceTracking 和 AcceptanceGate.checkGate
3. 如果 shouldAutoArchive() 返回 true，自动调用 reqboard_move(to="archived")
4. 返回值新增 gate_check 字段
5. 编写集成测试覆盖 2 个场景

## 上游产出摘要（dependsSummary）
- 数据模型 - RTM 类型定义
- 工具实现 - RTM 管理器（核心）
- 工具实现 - 验收门禁

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T12:30:32.469Z，窗口 session-18ecbbd5-0d45-4816-a90b-3040ed8a1a0c）

已完成 reqboard_accept_sheet 的 RTM 集成，所有测试通过（4/4）

### 完成项

- 创建 AcceptSheet RTM 集成辅助函数 packages/web/dsh-pmboard/src/application/internal/accept-sheet-rtm-integration.ts
- - checkAcceptanceGate: 检查验收门禁状态
- - 返回 gate_check（total/passed/failed/pending/pass_rate/gate_status）
- - 返回 should_archive（是否应该自动归档）
- 修改 packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts
- - 添加 checkAcceptanceGate 导入
- - 在返回前调用 RTM 门禁检查
- - 返回值新增 gate_status 和 archived 字段
- 创建集成测试 packages/web/dsh-pmboard/tests/accept-sheet-rtm-integration.test.ts
- - 部分通过场景：10 passed + 2 failed，gate_status=blocked, archived=false
- - 全部通过场景：12 passed，gate_status=passed, archived=true
- - 部分待验场景：5 passed + 5 pending，gate_status=pending, archived=false
- - 兼容性场景：无验收单不报错
- 所有测试通过（4/4）

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/accept-sheet-rtm-integration.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts`
- `packages/web/dsh-pmboard/tests/accept-sheet-rtm-integration.test.ts`

### 下一步

下一步：t-e22d5f（reqboard_status 显示 FR 覆盖度和验收进度）

---
