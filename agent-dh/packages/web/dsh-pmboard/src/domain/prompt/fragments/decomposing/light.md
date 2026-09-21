# 拆分（decomposing）· 轻档

> 2026-09-21 用户裁定：**拆分计划在拆分阶段写**（设计阶段只写设计文档）。
> 拆分计划 = decomposition.md（改动盘点 + 任务表），批准后自动落库任务卡并进实施。

- [ ] **写计划**：对照设计文档逐份盘点代码改动（新增/修改/删除）+ 列任务表
      （key / title / phase / side / depends_on / implementation / acceptance），
      写进 docs/requirements/REQ-xxxxxx/decomposition.md。
- [ ] **提交**：`reqboard_submit(kind=plan)`（path=decomposition.md，summary=目标+做法，tasks=任务表）。
- [ ] **批准闸门**：调 `reqboard_ask_confirm(target=plan)` 弹框请人批准——
      批准后自动落库任务卡并进入实施（看板「批准计划」同样有效）；未获批准不得落库。
- [ ] **卡内必给验收**：每张卡写可证伪的 acceptance（跑什么、看到什么算过），不放空话。
- [ ] 下一步：implementing —— 用 reqboard_ask_confirm(target=plan) 交棒；未获批准不得进入。
