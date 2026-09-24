---
requirement_refs: [FR-1, FR-2, FR-3, FR-5, FR-8, FR-9, FR-10]
---

# 用例设计（REQ-260923222557-d3b0）

## UC-1 agent 进入实施收到 worktree 规范 <!-- serves: FR-1 -->

需求确认拆分进 implementing → 绑定窗口系统提示词出现「Worktree 操作规范」：`git worktree add .worktrees/REQ-{id}/ -b feature/REQ-{id}`、目录与分支约定、不强制执行的说明。agent 据此在独立 worktree 开工，不再与并行窗口抢主工作区。

## UC-2 子任务完成收到 commit 提示 <!-- serves: FR-2 -->

子任务 reqboard_task_move → done → 提示「子任务 {task_title} 已完成，请在 worktree 提交检查点」（含 commit 命令示例）。每个子任务形成可回滚检查点。

## UC-3 验收归档收到合并清理提示 <!-- serves: FR-3 -->

验收通过进 archived → 提示合并 `feature/REQ-{id}` 回主线并 `git worktree remove` 清理。worktree 生命周期闭环。

## UC-4 用户审阅不被 2 分钟/10 分钟打断 <!-- serves: FR-5, FR-6 -->

任何 reqboard 确认弹框（ask_confirm / capture / accept_sheet / advance）发出后，用户最长 1 小时内作答均有效；超时后返回语义不变。

## UC-5 预览未到达节点不再被误导 <!-- serves: FR-10 -->

需求在 design 阶段，用户点「拆分」节点预览：头部显示「未开始 · 待拆分」，而非旧版的「已拆分 · 待拆分」自相矛盾组合。

## UC-6 设计文档可点、未交可见 <!-- serves: FR-8, FR-9 -->

设计节点：✅ 已交文档点击右栏打开阅读；⬜ 未交保持占位可见。拆分节点未写 decomposition.md 时显示「⬜ 拆分计划：decomposition.md（未交）」，不再像"文档丢了"。头部胶囊同步显示「设计文档 n/5 已交/待确认」而非恒「待提交计划」。
