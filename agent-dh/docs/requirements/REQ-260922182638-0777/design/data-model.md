---
requirement_refs: FR-2, FR-5
---

# 数据模型 · 统一追溯链逻辑：全链路展示中文化

> REQ-260922182638-0777 · 本需求**无数据模型变更**，本份文档是不变式声明。

## D-1 无变更声明 `serves: FR-2`

无新增/变更字段、无表结构变化、无登记协议变化：ArtifactKind 枚举、StageArtifact（kind/path/confirmedAt）、reqboard_submit 契约全部保持原样。
本需求只改「显示名取值」一个变量，属于纯前端展示层行为变更。

## D-2 复用字段口径 `serves: FR-5`

任务卡名称解析复用既有字段，不新增后端字段：`StageTaskRef.title`（protocol.ts:385）为名称来源，`StageTaskRef.cardDoc`（protocol.ts:394）与 `StageArtifact.path` 精确字符串相等即配对。
匹配关系天然 1:1（cardDoc 由 decompose 生成、path 由 task_report 登记，同源同值）；匹配不到属正常态（卡文档未登记），降级为编号形态「任务卡（t-xxx）」，不报错、不阻断渲染。

## D-3 未知值数据契约 `serves: FR-3`

未知 kind / 未知文件名不进任何存储，只是渲染期兜底形态：「产物（原枚举值）」「<kind中文>（<文件名>）」——括号内保留原文，排查线索不丢。
兜底形态属预期显示变更，验收时显式核对（人为构造 mystery_kind / foo.md 验证）。
