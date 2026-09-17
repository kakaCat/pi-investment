## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

- [ ] **覆盖 1 · 节点归属与落盘**：本仓技术设计产出一**套**文档（按主题分：架构 / 数据层 /
      选型 / UI / 测试用例；规模小可合一），路径写进计划摘要，落在
      `docs/requirements/REQ-xxxxxx/`；不是上文默认的 `docs/superpowers/plans/…`。
      用 `reqboard_submit(kind=plan)` 提交。
- [ ] **覆盖 2 · 不含最终任务 DAG（W7 边界）**：计划的任务表**可省略**；最终任务卡在
      **decomposing** 阶段创作并经拆分确认门确认。技术设计只管方向与"怎么做"，不写实现代码。
- [ ] **覆盖 3 · 批准闸门**：调 `reqboard_ask_confirm(target=plan)` 请人批准；未批准时
      `reqboard_decompose` 被代码级拒绝。批准后才可进入拆分。
- [ ] **覆盖 4 · 数据层与回滚**：本仓要求明确"是否改表 / 改 schema、迁移方式与回滚"——
      这是上文 "Global Constraints" 在代码层面的落点。
- [ ] **覆盖 5 · 交棒**：下一步：decomposing —— 用 reqboard_submit(kind=plan) 交棒；未获批准不得进入。
