---
id: glossary
title: agent-dh 术语表
type: manual
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [overview, glossary]
---

# agent-dh 术语表

**这页回答**：这些词分别指什么、去哪看细节。术语按"最容易混"排序。

| 术语 | 一句话解释 | 细节 |
|---|---|---|
| **Profile** | DSH 的装载单元：一组 cordis 插件 + 配置 + 提示词；本仓是 investment profile | [agent-dh 是什么](agent-dh-overview.md) |
| **插件 / 工具** | 插件（package）向框架注册工具（tool）；工具是模型能调用的能力 | [工具开发规范](../standards/tool-development.md) |
| **host 半 / client 半** | 页面插件分两半：host 跑在服务端（需重启），client 打进浏览器包（刷新即生效） | [插件与页面插件规范](../standards/plugin-and-pages.md) |
| **dist / src 加载** | 包的 `main` 指向 `dist/index.mjs`（需构建）或 `src`（tsx 直载） | [构建与发版规范](../standards/build-and-release.md) |
| **DSH_HOME** | 运行时根目录（`agent-dh/.dsh-data`）：profile、台账、技能、会话 | [agent-dh 是什么](agent-dh-overview.md) |
| **窗口 / 窗口编码** | 一个 DSH 会话 = 一个"窗口"；编码形如 `w-1cee2467`（会话 id 前 8 位） | [身份与 agents.json](identity-and-agents-json.md)（待写） |
| **基因组（genome）** | agent 的宪法/原则/规则/教训四段提示词；可进化、有版本、过验证门才转正 | [自主能力总览](../architecture/AUTONOMY-SYSTEM.md) |
| **决策审计（decision_audit）** | 决策台账：记录 + 事后评估（观察/跳过/交易各有评估策略） | [留痕与文档规范](../standards/audit-and-docs.md) |
| **需求看板（reqboard）** | 需求→任务两级流水线台账 + 看板页面 | [RFC 014](../rfcs/014-requirement-board.md) |
| **计划模式（plan mode）** | 拆分的前置闸门：先写计划（含任务表）→ 人批准 → 才能落库任务卡 | [RFC 014](../rfcs/014-requirement-board.md) |
| **验收人工审核** | 交付后由人看着证据点"验收通过"或"退回返工"；验收通过是人工闸门 | [需求归档规范](../architecture/requirement-archive.md) |
| **归档 = 存底 + 合并** | 需求档案留过程（L3）；结论合并进既有页面（L2/L1）并写索引 | [需求归档规范](../architecture/requirement-archive.md) |
| **文档金字塔 / wiki** | 金字塔 = 认知高度（L1 说明书 / L2 领域篇 / L3 档案）；wiki = 页面互链 + front-matter | [文档规范](../../../docs/DOCUMENT-MANAGEMENT-PLAN.md) |
| **regime / 阈值钳制** | 市场状态决定权益仓位上限；与现金≥10%、总仓硬顶 80% 取最严 | [账户与交易纪律](../standards/account-and-trading.md) |
| **降级 / 新鲜度** | 数据源不可用时的兜底状态；风控与决策前必须先校验新鲜度 | [数据与降级规范](../standards/data-and-degradation.md) |
| **trade_guard** | 后端下单风控（总仓硬顶等），所有委托都过它 | [下单 API 指南](../guides/order-api-guide.md) |
| **skill（技能）** | 按需加载的 SOP 文档（`skills/<name>/SKILL.md`），模型用 skill 工具取用 | [技能装载](../guides/skill-loading.md) |
| **四层分层（domain / application / adapters / tools·http）** | 页面插件内部按 DDD 分层：domain 纯规则（零 I/O）、application 用例（只依赖端口）、adapters 唯一 I/O 入口、tools 与 http 是薄适配。依赖单向向内 | [RFC 014 §15](../rfcs/014-requirement-board.md) |
| **端口 / 用例（port / use case）** | 端口 = 用例依赖的抽象（仓储/文档/时钟/ID/会话/弹框）；用例 = 一个动作一个模块，只编排不判定 | [RFC 014 §15](../rfcs/014-requirement-board.md) |
| **机械门禁（layer-boundary / size-budget / output-contract）** | 用可失败的测试把架构约束钉死：依赖方向、文件行数上限（带"必须仍超限"的白名单）、工具返回键必须已声明。**门禁必须能证明自己扫到了东西**（带命中下限自检）并与故障注入配套 | [测试与门禁规范](../standards/testing.md) |
| **续版验收（验收单 v2）** | 返工后重交的验收单只含上一版的**未过项 + 未裁决项**；上一版无未过项时重新生成全新单（不进续版） | [各阶段职责规范](workflow-stages.md) |
