# 拆分（decomposing）· 轻档

> 轻档：直接列任务卡、卡内给验收；拆分清单仍要经人确认。

- [ ] **列卡**：按实施计划列出任务卡（key / title / phase / side / depends_on）。
- [ ] **卡内必给验收**：每张卡写可证伪的 acceptance（跑什么、看到什么算过），不放空话。
- [ ] **落库 + 确认**：用 `reqboard_decompose` 落库，再调
      `reqboard_ask_confirm(kind=decomposition)` 请人确认后进入实施。
- [ ] **下一步**：下一步：implementing —— 用 reqboard_decompose 交棒；未获批准不得进入。
