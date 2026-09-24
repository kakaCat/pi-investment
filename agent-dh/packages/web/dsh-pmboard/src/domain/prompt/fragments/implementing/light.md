# 实施（implementing）· 轻档

> 轻档：直接改、自测通过就汇报；任务卡状态与产物链照旧维护。

- [ ] **照卡执行**：调 `reqboard_task_move(to=in_progress)` 取任务卡全文，按卡里的实施方案
      直接改，不临时加功能、不扩范围。
- [ ] **自测**：改动后跑与该任务相关的测试 / 命令，确认通过（不跑不算完成）。
- [ ] **汇报**：调 `reqboard_task_report`（summary / completed / files_changed）落一份完工记录。
- [ ] **遇门用弹框**：需要人拍板（范围变更 / 方案取舍）用 `reqboard_ask_confirm`。
## Worktree 规范（防多窗口 Git 冲突）

> 本需求应在独立 worktree 开发；不强制、不硬编码 git 命令，由 agent 判断。

- [ ] 创建：`git worktree add .worktrees/REQ-<号>/ -b feature/REQ-<号>`
- [ ] 提交：子任务完成在 worktree 内 commit 一次（检查点）
- [ ] 收尾：归档时合并回主线并 `git worktree remove` 清理

- [ ] **下一步**：下一步：accepting —— 用 reqboard_submit(kind=verification) 交棒；未获批准不得进入。
