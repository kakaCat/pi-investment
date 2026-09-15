# 需求：需求详情页增加文档记录展示（需求/UI/设计文档）

> REQ-7f6a8e · feature · 立项 2026-09-15 · 窗口 w-264964df

## 需求背景

需求详情页缺少「文档记录」展示——需求执行过程中创建的需求文档、UI 文档、设计文档等，
散落在 `docs/requirements/REQ-xxx/` 目录，看板上看不到这个需求产生了哪些文档、文档在哪。
用户提出借鉴 [superpowers](https://github.com/obra/superpowers) 的文档创建要求。

## 现状问题（真实数据核实，2026-09-15）

| 问题 | 事实 |
|---|---|
| docLinks 字段有定义但未使用 | 25 个需求全部 `docLinks=None` |
| 需求详情页无文档展示 | 只有「归档」章节展示 archive.docs |
| 文档产出稀疏 | 实际目录多数只有 plan.md，缺 requirement.md / UI / 设计文档 |
| 归档文档清单局限 | archive.docs 仅在归档章节展示，进行中需求看不到 |

## 功能描述

需求详情页新增「📁 文档记录」区块，聚合展示该需求关联的全部文档：

| 类型 | 图标 | 数据来源 |
|---|---|---|
| 需求文档 | 📄 | docLinks.requirement |
| UI 文档 | 🎨 | docLinks.ui |
| 设计文档 | 📐 | docLinks.proposal |
| 实施计划 | 📝 | plan.path |
| 验收材料 | ✅ | archive.docs (verification) |
| 复盘 | 🔁 | archive.docs (retro) |
| 其他 | 📒 | archive.docs (notes) |

## 借鉴 superpowers

superpowers 的文档理念：每个工作应有结构化文档产出（需求/设计/实现/复盘分开），
系统化记录、可追溯、可复用。本需求落地为：文档类型明确 + 需求记录引用文档路径 + 详情页聚合展示。

## 涉及模块

- 前端：`packages/pages/dsh-pmboard/src/client/view.ts`（渲染）+ `styles.ts`（样式）
- 数据：`RequirementRecord.docLinks` / `plan.path` / `archive.docs`（已有字段，Phase 1 无需后端改动）

## 实施状态

- Phase 1（前端展示 MVP）：✅ 已完成
- Phase 2（文档记录填充机制 + 文档创建规范）：待做
