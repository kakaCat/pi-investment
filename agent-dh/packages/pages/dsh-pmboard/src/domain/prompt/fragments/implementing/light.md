# 实施（implementing）· 轻档

> 轻档：直接改、自测通过就汇报；任务卡状态与产物链照旧维护。

- [ ] **照卡执行**：调 `reqboard_task_move(to=in_progress)` 取任务卡全文，按卡里的实施方案
      直接改，不临时加功能、不扩范围。
- [ ] **自测**：改动后跑与该任务相关的测试 / 命令，确认通过（不跑不算完成）。
- [ ] **汇报**：调 `reqboard_task_report`（summary / completed / files_changed）落一份完工记录。
- [ ] **遇门用弹框**：需要人拍板（范围变更 / 方案取舍）用 `reqboard_ask_confirm`。
- [ ] **下一步**：下一步：accepting —— 用 reqboard_submit(kind=verification) 交棒；未获批准不得进入。
