## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

以下 6+1 条是本仓对 superpowers 原文的接线：原文在前、本仓规则在后，冲突时以本段为准。

- [ ] **覆盖 1 · 交棒**：上文把交棒写成"调用 writing-plans skill"。本仓不用 skill 自主 load：
      下一步：design —— 用 reqboard_ask_confirm(target=artifact, kind=requirement) 交棒；未获批准不得进入。
      肯定答复会**自动落章并推进**；本节点不得直接跳到拆分 / 实施。
- [ ] **覆盖 2 · 落盘路径**：上文把设计文档存到 docs/superpowers/specs/…。本仓一律落
      `docs/requirements/REQ-xxxxxx/requirement.md`（头部带 REQ id），并用
      `reqboard_submit(kind=requirement)` 登记产物；**不要求** agent 执行 git commit。
- [ ] **覆盖 3 · 显式否掉 server/http 与浏览器本体**：不得启动任何 server、不得打开浏览器
      （上文 `--open` / "start the server" 一类动作在本仓不存在，照做会变成无法执行的副作用）。
      如确需可视化，用**独立一次弹框**提议（弹框内只放提议本身，不带其他内容），
      并按"看图是否比读字更清楚"逐个问题判断。
- [ ] **覆盖 4 · 产物豁免无效**：上文 Spike / Bounded 的 "No design doc"、"No spec file"、
      "No implementation plan document" 在本仓**不适用**——轻路径 = 文档短 + 提示词精简，
      **产物不得省**；requirement.md 必须产出并经人确认。
- [ ] **覆盖 5 · 任务语义**：上文 "create a task for each item" 在本仓指**节点内可勾选清单**
      （注入文本自查），不是 reqboard 任务卡；任务卡属 decomposing 节点（拆分阶段创作），
      本节点不得越界建卡。
- [ ] **覆盖 6 · 闸门**：HARD-GATE 由 `reqboard_ask_confirm` 承载；"太简单不用走流程"
      由代码级拦截（artifact_not_confirmed）拒绝，不由模型自裁。
- [ ] **覆盖 7 · 节点归属**：上文 "Cover: architecture, components, data flow, error handling,
      testing" 在本仓属 **design** 节点的设计覆盖面；brainstorming 阶段不得越界写设计。
