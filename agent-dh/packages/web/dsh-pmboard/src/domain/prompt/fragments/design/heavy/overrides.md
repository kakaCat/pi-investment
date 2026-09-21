## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

- [ ] **覆盖 1 · 节点归属与落盘**：本仓设计产出一**套**文档（按主题分：架构 / 数据层 /
      选型 / UI / 测试用例；规模小可合一），落在 `docs/requirements/REQ-xxxxxx/design/*.md`；
      不是上文默认的 `docs/superpowers/plans/…`。设计文档落盘即产物（目录自动发现登记），
      交齐后调 `reqboard_ask_confirm(target=artifact, kind=design)` 请人确认。
- [ ] **覆盖 2 · 不含任何拆分内容（W7 边界）**：设计只管方向与"怎么做"，不写实现代码；
      **任务表 / 任务 DAG / 拆分计划章节一律归 decomposing（拆分）阶段创作**——拆分计划
      在那里提交并经人批准（批准即自动落卡开跑）。设计文档里出现任务表特征
      （depends_on 表头等）会被拆分内容门禁拒绝确认（design_contains_decomposition）。
- [ ] **覆盖 3 · 确认闸门（G2）**：调 `reqboard_ask_confirm(target=artifact, kind=design)`
      请人确认设计文档——一次确认 = 全部设计文档成组落章；文档集未交齐（feature 五份
      必交 + 端侧条件必交）或未全部确认时，design→decomposing 被代码级拒绝
      （design_doc_incomplete）。
- [ ] **覆盖 4 · 数据层与回滚**：本仓要求明确"是否改表 / 改 schema、迁移方式与回滚"——
      这是上文 "Global Constraints" 在代码层面的落点。
- [ ] **覆盖 5 · 交棒**：下一步：decomposing —— 确认设计文档后自动推进；未获确认不得进入。
- [ ] **覆盖 6 · 章节可追溯 + 语言强度按层**：设计文档的**每个二级章节**必须带
      «B»serves: FR-4«B» 标注（多值逗号分隔）——缺标注即**孤儿章节**，拆分阶段提交计划
      被门禁拒绝（design_orphan）。语言强度按层：**设计以技术语言为主，不必写成散文**，
      但每节要能回答"服务哪条功能点"；需求与验收用全业务语言；拆分用业务标题 + 技术细节下沉。
