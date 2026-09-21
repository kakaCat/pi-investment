# 验收（accepting）· 轻档

> 轻档：自检清单过一遍；验收仍是**人工决定**，不能自判通过。

- [ ] **自检清单**：对照需求文档与任务卡验收标准逐条自检，逐条给证据
      （命令 + 输出摘要 / 测试报告路径）。
- [ ] **提交验收材料**：调 `reqboard_submit(kind=verification)`
      （summary = 交付结论；evidence 引用的工作区路径必须真实存在）。
- [ ] **请人审核**：用 `reqboard_accept_sheet` 或 `reqboard_ask_confirm` 请人逐项打勾——
      全部通过才归档；有未过项时需求**留在验收态**（REQ-a8d582 FR-2 起裁决不再自动打回），
      由人点看板「退回返工」才回实施并按未过项生成返工卡。
- [ ] **下一步**：下一步：archived —— 用 reqboard_accept_sheet 交棒；验收通过为人工闸门。
