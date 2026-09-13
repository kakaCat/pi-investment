# 文档金字塔与项目说明书（归档让项目认知向上生长）

- **日期**：2026-09-13
- **窗口**：w-1cee2467
- **分支**：feat/reqboard-pyramid → main
- **用户要求（原文）**：「归档后应该是金字塔模型一样，是项目的一个说明书，agent 可以通过这个更了解项目」

## 设计：四层金字塔

| 层 | 内容 | 位置 | 谁读 |
|---|---|---|---|
| L0 入口 | 一行指引 | `CLAUDE.md`（根 / 子项目） | agent 每次启动 |
| L1 说明书 | 项目是什么 / 三层架构 / 术语表 / 怎么跑 / 指针 / 最近更新 | `docs/architecture/project-manual.md` + `docs/README.md` | 新人；agent 接手任何任务之前 |
| L2 领域篇 | 一个主题一篇（架构/指南/ADR/RFC/研究） | `architecture/ guides/ adr/ rfcs/ strategy-research/` | 做具体事情时按需读 |
| L3 证据档案 | 需求档案 + 工作日志 | `requirements/REQ-xxxxxx/`、`work-logs/YYYY-MM/` | 只用于追溯"当时为什么" |

**生长规则（归档时执行）**：L3 必写 + L2 至少一篇；**改变项目级认知的类型（feature/refactor/spike）
必须申报 L1/L2 更新点（manual_updates：path/section/summary）**——代码拒绝没有更新点的这类归档；
bug/doc/chore 写 `manual_note` 说明即可；L1 每次变更在「最近更新」表追加一行。

## 落地

1. **新建 L1 说明书** `docs/architecture/project-manual.md`：项目是什么、三层架构表、术语表（含指针）、
   怎么跑起来、去哪儿找细节、怎么维护（含"最近更新"表）；
2. **L0 入口** 根 `CLAUDE.md` 顶部加"项目认知入口"指引；`docs/README.md` 顶部指向说明书；
3. **项目级规范补章**：`docs/DOCUMENT-MANAGEMENT-PLAN.md` 新增「文档金字塔与项目说明书」；
4. **归档细则**：`agent-dh/docs/architecture/requirement-archive.md` 增 §0.5（金字塔生长）；
5. **代码级生长闸门**：`ARCHIVE_DOC_RULES[*].requireManual` + `ArchiveRecord.manualUpdates/manualNote`；
   `assertArchiveMaterials` 校验（缺更新点 → 拒；更新点必须写全 path/section/summary）；
   归档工具与看板归档区展示更新点；skill 与绑定窗口提示段同步；
6. **测试**：金字塔规则正反例 + 归档工具落库与评论留痕 + 归档区渲染 187 例全绿。

## 判据与反模式

- 判据：**读完 L1 就该知道"这个项目是什么、现在有哪些关键认知"**；
- 反模式：把 L3 细节抄进 L1（说明书变流水账）；结论只留 L3（认知长不上去）；
  新文档建了不挂进 L1/L2 索引（等于没写）。

## 遗留

- L1 说明书目前是**骨架 + 可核实内容**（架构/术语/入口），各领域细节仍需在后续归档中逐步补进 L2 并让 L1 指针变密；
- 尚未做"L1 与代码不一致"的自动巡检（可作为后续归档探针的一部分）。
