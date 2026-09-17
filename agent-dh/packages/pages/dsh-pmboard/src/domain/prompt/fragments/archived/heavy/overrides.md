## 本仓覆盖条目（覆盖上文与本仓冲突之处；priority=floor，永不被裁）

- [ ] **覆盖 1 · 归档语义（REQ-9f4a44）**：上文讲的是"合并分支 / 清理 worktree"。本仓归档指
      "把结论并进项目文档"：验收通过即自动进入 archived，本阶段用
      `reqboard_submit(kind=archive)` 补齐材料（目录 / 文档清单 / 合并去向 / 索引条目 /
      说明书更新点）。
- [ ] **覆盖 2 · 必填文档按分类**：按需求类型核对必填文档与合并去向（ARCHIVE_DOC_RULES）：
      feature→architecture/guides、bug→known-issues、refactor→architecture/work-logs、
      spike→research、doc→docs、chore→work-logs；缺项会被代码级拒绝。
- [ ] **覆盖 3 · 合并去向必须真写**：mergedInto 里写了哪份文档，就必须把结论真的写进那份文档；
      归档不是挪目录。
- [ ] **覆盖 4 · 金字塔生长**：feature / refactor / spike 必须申报 manual_updates
      （更新了哪份文档的哪一节、多了什么认知）；bug / doc / chore 写 manual_note 即可。
- [ ] **覆盖 5 · 交棒**：下一步：无（归档是终态）—— 材料补齐用 reqboard_submit(kind=archive)。
