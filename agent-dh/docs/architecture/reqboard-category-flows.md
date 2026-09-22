---
id: reqboard-category-flows
title: 六立项类型的流程差异（reqboard）
summary: feature/bug/refactor/spike/doc/chore 六类需求各自走什么节点、过哪些门、哪里生效哪里是缺口——以代码为准的实测记录。
type: architecture
status: living
updated: 2026-09-23
owners: [w-90f10b62]
tags: [reqboard, category, flow, gates, l2]
---

# 六立项类型的流程差异（reqboard）

> 事实源：`CATEGORY_FLOW_PROFILES`（packages/web/dsh-pmboard/src/shared/protocol.ts）、
> `GATE_CATALOG`（domain/gate/GateCatalog.ts）、`REQ_TRANSITIONS`（domain/requirement/RequirementStatus.ts）。
> 本文与代码不一致时以代码为准。实测窗口：w-90f10b62（2026-09-23）。

## 1. 差异总表

| 类型 | 中文 | 启用节点 | 人工确认门 | 设计意图（代码注释） |
|---|---|---|---|---|
| feature | 功能 | draft → brainstorming → design → decomposing → implementing → accepting → archived（**全流水线**） | **五门全开** | 全流水线，五门全开 |
| bug | 缺陷 | draft → ~~brainstorming~~ → design → decomposing → implementing → accepting → archived | 3 门：design>decomposing / decomposing>implementing / accepting>archived | 免需求分析门：业务文档+复现定位即上下文，并入修复方案产物 |
| refactor | 重构 | 同 bug | 同 bug | 免需求分析：现状+目标态并入设计 |
| spike | 调研 | draft → ~~brainstorming/design/decomposing~~ → implementing → accepting → archived | **仅 1 门**：accepting>archived | 研究即实施，产物=研究报告 |
| doc | 文档 | 同 spike | 同 spike | 写作即实施 |
| chore | 杂项 | 同 spike | 同 spike | 最简流程 |

五道人工确认门全貌（GATE_CATALOG）：

| 门 | 转移 | 须确认产物 |
|---|---|---|
| G0 立项门 | （创建即入 draft，→ brainstorming 接手） | —（立项弹框本身即确认） |
| 需求文档门 | brainstorming > design | requirement（需求文档） |
| 设计文档门（G2） | design > decomposing | design（设计文档集，含完整性校验） |
| 拆分计划门 | decomposing > implementing | decomposition（拆分计划批准） |
| 验收门 | accepting > archived | verification（验收材料） |

跳过的节点对该类型**不产生物、不设门、不注入提示词**（沉默跳过）。

## 2. 分类感知在哪里生效（表现层 ✅）

| 消费点 | 代码位置 | 效果 |
|---|---|---|
| 提示词注入 | application/internal/capture-section.ts:152、adapters/CaptureHook.ts:276、application/gate/handlers/h3-inject.ts:46 | 禁用节点不注入阶段提示词 |
| 产物门禁 | application/internal/artifact-gates.ts（flowProfileFor / confirmGateKindFor） | 禁用节点无产物要求；确认门按类型过滤 |
| 看板展示 | application/query/QueryStageDetail.ts:106 | 跳过节点标灰"本分类跳过"，不算缺失 |
| 归档文档规则 | domain/artifact/ArtifactSpec.ts ARCHIVE_DOC_RULES | 按类型定必填归档文档（如 retro 仅 bug/refactor/spike） |
| 文档集校验 | application/internal/category-doc-sets.ts CATEGORY_DELTAS | 按类型定 requirement.md 必填节与设计文档集（BASE+DELTA 两层） |
| 提示词路由 | domain/prompt/router.ts | 路由键 (stage, difficulty, category)，类型是第三轴 |

## 3. 转移层的三个缺口（❌ 未分类感知）

状态机（REQ_TRANSITIONS / assertReqTransition）是**全局一张表，无 category 参数**：

1. **跳级转移不存在**：`draft` 只能转 `brainstorming / canceled`——bug 的 `draft>design`、
   spike/doc/chore 的 `draft>implementing` 在转移表里都没有，也没有任何
   `nextEnabledStage(category, from)` 式跳级逻辑。实际效果：bug 需求仍得
   `draft>brainstorming>design` 一步步走，brainstorming 对它是"空过"节点。
2. **人工门检查走全局表不走档案**：MoveRequirement 用全局 `ARTIFACT_CONFIRM_GATES` +
   `HUMAN_ONLY_REQ_TRANSITIONS` 判定 human_gate——bug 走 `brainstorming>design`
   **仍会被人工门拦**。档案注释"免需求分析门"实际只免了产物确认门（assertArtifactGates 分类感知），
   转移层人工门没免。
3. **反向不拦**：bug 需求可以合法 move 进 brainstorming（转移表允许），只是该节点对它沉默——
   "跳过"靠沉默实现，不是靠拦截。

**要真正按类型控制流程，需补**：① 转移断言加 category 维度（或加跳级逻辑）；
② MoveRequirement 的人工门判定改走 `confirmGateKindFor(category)`。

## 4. 与文档模板的关系

- 六类型各有独立的需求模板，**按"产出它的节点"分目录**（只有 feature 过需求分析节点）：
  `templates/brainstorming/requirement.feature.md`、`templates/design/requirement.{bug,refactor}.md`、
  `templates/implementing/requirement.{spike,doc,chore}.md`。
  feature/refactor/bug 含"行为改动区"（改动位置（文字坐标） + 改动对比）；spike/doc/chore 没有——
  按"是否改系统行为"分界，对齐专业 PRD 的 "When Needed" 原则。
- 条款编号前缀按类型分：FR-x / BUG-x / RF-x / SP-x / DOC-x / CH-x（下游任务卡
  requirement_refs 引用，覆盖门禁逐条核对）。
- 模板落盘时点 = **进入该类型的首个启用节点**（feature=brainstorming；bug/refactor=design；
  spike/doc/chore=implementing），不是写死的 draft>brainstorming。

## 5. 相关页面

- [需求看板实操（从立项到归档）](../guides/reqboard-workflow.md)
- [文档标准：六类文档各写什么](documentation-standard.md)
- [闸门确认后置链](gate-post-chain.md)
- [需求归档规范](requirement-archive.md)
- [工作流节点与看板展示](workflow-stages.md)
