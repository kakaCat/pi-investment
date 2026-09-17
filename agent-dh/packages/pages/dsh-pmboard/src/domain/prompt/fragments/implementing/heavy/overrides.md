## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

- [ ] **覆盖 1 · 任务来源**：上文说"读 plan 文件、按 bite-sized steps 执行"。本仓的任务卡由
      `reqboard_decompose` 落库：开工时 `reqboard_task_move(to=in_progress)` 返回任务卡全文
      （title / description / acceptance / implementation / context），照卡执行，不凭记忆、不二次创作。
- [ ] **覆盖 2 · 汇报 = 完工记录**：每张卡完成必须 `reqboard_task_report`（做了什么 / 改了哪些文件 /
      下一步）——它是 done 凭证门的前置；无汇报、无真实工具动作、60s 内连环关任务会被代码级拒绝。
- [ ] **覆盖 3 · 构建新鲜度**：改了 packages/pages/*/src 必须重建对应 client 产物，
      否则关任务会被构建新鲜度门拒绝（STALE_BUILD）。
- [ ] **覆盖 4 · 附属按需片段（同一次注入最多挂一个）**：只在出现对应场景时才用
      test-driven-development / subagent-driven-development / using-git-worktrees /
      dispatching-parallel-agents / requesting-code-review，不默认全挂。
- [ ] **覆盖 5 · 遇门用弹框**：范围变更 / 方案取舍用 `reqboard_ask_confirm`；
      普通信息征询用 `ask_user_question`（宿主工具，非 reqboard_* 工具集）。
- [ ] **覆盖 6 · 交棒**：下一步：accepting —— 用 reqboard_submit(kind=verification) 交棒；未获批准不得进入。
