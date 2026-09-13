---
id: std-audit-and-docs
title: 留痕与文档规范（写哪里 / 不写哪里）
type: standard
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [standards, audit, docs]
---

# 留痕与文档规范

**这页回答**：一次工作做完，结论该写进哪个系统；什么内容不该写。

## 结论先行

1. **三个留痕口分工明确**：
   - `memory_write`：**结论**，供未来检索（namespace: analysis / experience / decision）；
   - `decision_audit`：**决策**，供事后评估（观察/跳过/交易/池子管理各对应评估策略）；
   - `board_post`：**要别人知道或动手的事**（needs_action=true 走悬赏档，需先问用户确认；
     needs_action=false 纯记录，免确认）。日常流水与回执**不上板**，写 memory。
2. **文档放置走决策树**（根 CLAUDE.md + `docs/DOCUMENT-MANAGEMENT-PLAN.md`）：
   决策→`adr/`、提案→`rfcs/`、架构→`architecture/`、指南→`guides/`、**规范→`standards/`**、
   工作记录→`work-logs/YYYY-MM/`；子项目放各自 `docs/`。
3. **docs 按 wiki 维护**：每页有 front-matter（`id/title/type/status/updated`），页尾写「相关页面」，
   新页必须从首页或上层页链到；`status: stub` = 待写页（后续需求候选）。
4. **归档 = 存底 + 合并**：需求档案留过程（L3），结论合并进既有页面（L2/L1）并写索引；
   **合并去向只允许既有规范目录，不许自创**；改变项目认知的类型必须申报说明书更新点。
5. **不留什么**：过程性噪声（中间调试、回执、临时截图）不进 wiki 与看板；重复犯错的教训必须留痕。

## 关键机制

- 归档闸门（代码级）：`reqboard_archive_submit` 校验需求目录形状、必填文档、合并去向合法目录、
  索引条目、以及 feature/refactor/spike 的 `manual_updates`；人工点「归档」才进 `archived`。
- 巡检：`python3 agent-dh/scripts/wiki_probe.py`（死链/孤儿页/待写页/缺 front-matter，退出码 1）。
- 需求档案索引：`agent-dh/docs/requirements/INDEX.md`（一行一个已归档需求 + 结论 + 去向）。

## 依据

- 文档混乱整治（`DOCUMENT-MANAGEMENT-PLAN.md`）；
- 用户要求「归档要是项目说明书、agent 能据此更懂项目」→ 文档金字塔 + wiki 页面模型；
- 公告板噪声治理（reminder delivered / auto-track 这类被护栏拒绝）。

## 自检清单

- [ ] 这次的结论，未来谁会检索？写进 memory 了吗？检索得到吗（写清实体与关键词）？
- [ ] 有需要别人动手的事吗？→ 走悬赏档并先问用户。
- [ ] 新文档放对目录了吗？有 front-matter 吗？挂进首页了吗？`wiki_probe` 绿吗？
- [ ] 归档材料里的合并去向，我真的把内容写进去了吗？

## 相关页面

- [编码与协作规范](coding.md)
- [需求归档规范](../architecture/requirement-archive.md)
- [RFC 014 需求看板](../rfcs/014-requirement-board.md)
- [文档规范与 Wiki 约定](../../../docs/DOCUMENT-MANAGEMENT-PLAN.md)
