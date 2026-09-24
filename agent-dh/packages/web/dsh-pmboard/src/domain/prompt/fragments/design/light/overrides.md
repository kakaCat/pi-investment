## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

- [ ] **覆盖 1 · 登记命令与触发者（不要猜 kind）**：登记不是自动发生的——文档落盘后由**本窗口
      agent 自己**调 `reqboard_submit(kind=design)`（缺省扫 design/ 全目录、幂等）。
      **不要猜 kind**：设计文档只认 `design`，`requirement/plan/verification/archive`
      传错必被拒。登记齐后调 `reqboard_ask_confirm(target=artifact, kind=design)` 请人确认。
- [ ] **覆盖 2 · 每节必须标注服务哪条功能点**：每个二级章节带 `serves: FR-4`（多值逗号分隔）；
      缺标注即**孤儿章节**，提交计划被门禁拒（design_orphan）；文档级标注写 H1/front-matter。
- [ ] **覆盖 3 · 语言强度按层（读者是谁就用谁的语言）**：设计**技术为主**（每节标 serves）；
      拆分用**业务标题** + 技术细节下沉；需求/验收用**全业务**语言 + 可执行操作；
      实施技术为主 + 业务三要素。业务化 ≠ 把设计写成散文。
