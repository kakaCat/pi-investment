# REQ-283168 相关文档索引（历史项目看板文档挂载）

> 本需求（项目看板内容代码丢失）涉及的历史设计/实施文档汇总。文档按文档放置规范保留在原位
> （work-logs 留在 work-logs、设计稿留在 design），此处只做索引挂载，不移动原文件。

## 一、双视图模式（本次丢失并恢复的核心）

| 文档 | 说明 |
|------|------|
| [pmboard-dual-view-mode.md](../../work-logs/2026-09/pmboard-dual-view-mode.md) | 列表视图 + 泳道视图切换的实施方案——本次从 stash@{0} 恢复的就是这套代码 |

## 二、节点内容差异化（stash 产生的上下文：feat/pmboard-node-diff）

| 文档 | 说明 |
|------|------|
| [pmboard-node-content-design.md](../../design/pmboard-node-content-design.md) | 节点内容差异化设计：不同类型节点展示不同详情 |
| [pmboard-node-diff-implementation.md](../../work-logs/2026-09/pmboard-node-diff-implementation.md) | 节点差异化实施报告（P0 阶段，分支 feat/pmboard-node-diff）——stash 描述中提到的合并目标 |

## 三、任务页 UI 改进（P2 工作线）

| 文档 | 说明 |
|------|------|
| [pmboard-task-page-ui-improvement.md](../../design/pmboard-task-page-ui-improvement.md) | 任务页 UI 改进设计（监控定位、统计卡片、筛选工具栏） |
| [pmboard-task-page-ui-preview.md](../../design/pmboard-task-page-ui-preview.md) | 任务页 UI 效果预览（ASCII 布局图） |
| [pmboard-task-page-implementation-summary.md](../../design/pmboard-task-page-implementation-summary.md) | 实施总结（5 大核心问题识别与设计目标） |
| [pmboard-task-page-implementation-complete.md](../../design/pmboard-task-page-implementation-complete.md) | Phase 1 实施完成报告（styles.ts 样式增强） |
| [pmboard-task-page-test-plan.md](../../design/pmboard-task-page-test-plan.md) | 测试计划 |
| [pmboard-task-page-delivery.md](../../design/pmboard-task-page-delivery.md) | 交付总结（已部署，:13080） |

## 四、流程与整体设计

| 文档 | 说明 |
|------|------|
| [pmboard-complete-design.md](../../work-logs/2026-09/pmboard-complete-design.md) | 完整流程设计：Goal + Workflow + 人机回路 |
| [pmboard-implementation-plan.md](../../work-logs/2026-09/pmboard-implementation-plan.md) | 优化实施方案（任务卡 = 执行指令、完成 hook、Goal 跟踪） |
| [pmboard-optimization-plan.md](../../work-logs/2026-09/pmboard-optimization-plan.md) | 优化计划（人机回路诊断） |
| [pmboard-new-tools-design.md](../../work-logs/2026-09/pmboard-new-tools-design.md) | 新增工具设计（Requirement 层 + Task 层状态机） |
| [pmboard-menu-optimization.md](../../work-logs/2026-09/pmboard-menu-optimization.md) | 菜单优化方案（入口按钮 → 可见内容） |
| [pmboard-final-status.md](../../design/pmboard-final-status.md) | 看板状态总结（2026-09-14，代码修复待重启时点） |

## 与本次恢复的对应关系

- **丢失的代码** = 第一节「双视图模式」方案的实现（view.ts 的 buildListView/renderList*、board-mount.ts 的视图切换状态、styles.ts 的 viewswitch/list/pager/cprog 样式），曾整体沉没在 stash@{0}；
- **stash 的产生背景** = 第二节 feat/pmboard-node-diff 合并前的暂存操作（合完 728a77b0 后忘了 pop）；
- **后续覆盖来源** = 第三节 P2 任务页工作线的提交（41feb8f5 等），在 stash 未 pop 的工作区上继续开发，把丢失固化成了"既成事实"。
