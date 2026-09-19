# 设计（design）· 轻档

> 轻档：目标 / 步骤 / 验收三行即可；计划文档仍要落盘、仍要人批准。

- [ ] **目标**：一句话写清本需求在代码层面要达成什么（可证伪）。
- [ ] **步骤**：列出改动步骤（改哪些文件 / 模块），3 步以内讲清"怎么做"。
- [ ] **验收**：给出可执行的验收命令与期望输出（跑什么、看到什么算过）。
- [ ] **落盘**：把计划写进 docs/requirements/REQ-xxxxxx/plan.md，
      用 `reqboard_submit(kind=plan)` 提交；计划里不写最终任务 DAG（任务卡属拆分阶段）。
- [ ] **批准闸门 + 下一步**：调 `reqboard_ask_confirm(target=plan)` 请人批准。
      下一步：decomposing —— 用 reqboard_submit(kind=plan) 交棒；未获批准不得进入。
