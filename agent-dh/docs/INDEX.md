---
id: docs-index
title: 全站页面索引（机器可读入口）
type: index
status: living
updated: 2026-09-24
owners: [agent-dh]
tags: [index, wiki]
---

# 全站页面索引

**这页回答**：这个 wiki 有哪些页、每页讲什么（一句话）——先读这张表，再决定打开哪页。

> 本页由 `python3 agent-dh/scripts/docs_index.py` 生成，**勿手改**；改了页面后跑一次生成，`--check` 会校验是否过期。日志明细见 [工作日志索引](work-logs/README.md)，需求档案见 [需求档案索引](requirements/INDEX.md)。

### 入口与发布说明 · `docs`（5 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [全站页面索引（机器可读入口）](INDEX.md) | index | living | 这个 wiki 有哪些页、每页讲什么（一句话）——先读这张表，再决定打开哪页。 | 2026-09-24 |
| [agent-dh Wiki（归档文档首页 / 大纲）](README.md) | manual | living | agent-dh 的 wiki 首页：10 卷大纲 + 从哪开始读 + 待写页——每个新会话先看这页。 | 2026-09-13 |
| [🎊 Agent-DH v0.1.1 发布说明](RELEASE-NOTES-v0.1.1.md) | doc | living | v0.1.1（2026-08-18）发布说明：稳定性与可靠性改进清单（历史版本记录）。 | 2026-09-14 |
| [workflow-ptc-fix.md](troubleshooting/workflow-ptc-fix.md) | — | — | PM 插件 (dsh-pmboard) 的自动任务执行链依赖 workflow-ptc 服务，但当前运行时 ctx.workflowEngine 服务不可用，导致所有子卡执行失败： | — |
| [工作日志索引（L3 证据档案）](work-logs/README.md) | index | living | 某个时间点「当时做了什么、为什么这么做、结论是什么」。按月份倒序列出全部工作日志。 | 2026-09-14 |

### 架构与生命周期 · `docs/architecture`（31 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [架构演进记录：prompt_evolver → agent自主变更](architecture/ARCHITECTURE_EVOLUTION_prompt_evolver.md) | architecture | frozen | 架构演进记录：专用 prompt_evolver 改为 agent 自主变更段（2026-08-28；现行门控见 RFC 008）。 | 2026-09-13 |
| [Agent-DH 自主能力体系](architecture/AUTONOMY-SYSTEM.md) | architecture | living | 自主能力体系总览：自管理/自学习/自进化三层能力矩阵与学习循环。 | 2026-09-14 |
| [Agent-DH 工具重构总计划](architecture/REFACTOR_PLAN.md) | architecture | frozen | 2026-08-28 的工具重构总计划（只落地 Phase 1 trading）；现行工具架构以工具开发规范为准。 | 2026-09-13 |
| [Agent-DH 工具清单](architecture/TOOLS_INVENTORY.md) | architecture | living | 工具清单快照（2026-08-28，约 120 个工具与归属插件）——核对某工具是否存在时用；数字可能滞后。 | 2026-09-14 |
| [为什么部分插件没有 dist 目录？](architecture/WHY-NO-DIST.md) | architecture | living | 为什么有的包有 dist、有的没有（tsx 直载），以及怎么判断某个包走哪条路。 | 2026-09-14 |
| [a-grade-signal-auto-execution.md](architecture/a-grade-signal-auto-execution.md) | — | — | 解决当前"信号产生但不执行"的问题，建立A级信号到交易执行的自动化闭环，提高信号转化率从<2%到>50%。 | — |
| [账户模型与边界](architecture/accounts-and-boundaries.md) | architecture | living | 系统里有哪些账户、是谁的、我怎么知道自己该操作哪个。 | 2026-09-13 |
| [agent-dh 是什么（子项目说明书）](architecture/agent-dh-overview.md) | manual | living | agent-dh 在系统里的位置、运行时长什么样、代码怎么组织、改动怎么生效。 | 2026-09-13 |
| [auto-reduce-position-system.md](architecture/auto-reduce-position-system.md) | — | — | 自动识别并执行减仓操作，防止亏损扩大，锁定盈利。 | — |
| [数据契约与新鲜度](architecture/data-contracts-and-freshness.md) | architecture | living | 数据从哪来、契约长什么样、怎么判断"这批数能不能用"。 | 2026-09-13 |
| [数据库表设计对比分析报告](architecture/database-table-comparison.md) | architecture | living | v2 数据库表设计与文档的对比分析（结论：simulation_* 表设计更好），2026-08-25。 | 2026-09-14 |
| [文档规范融入插件实施指南](architecture/documentation-standard-integration-guide.md) | — | draft | 调用时机（源码注释原话）：在 assertReqTransition 之后、真正写盘之前。 | — |
| [项目文档规范（需求→设计→实施→测试全链路）](architecture/documentation-standard.md) | — | draft | 即：前后端与测试用例不是独立的层，而是「怎么做」的组成部分——它们是方案，不是步骤。 | — |
| [闸门确认后置链（切面 + 责任链）](architecture/gate-post-chain.md) | architecture | living | 人工闸门被作答之后机器自动做什么：唯一点 join point、两相执行 H1..H5、短路/降级/幂等不变量、新加一道门要改哪里。 | 2026-09-20 |
| [agent-dh 术语表](architecture/glossary.md) | manual | living | 这些词分别指什么、去哪看细节。术语按"最容易混"排序。 | 2026-09-13 |
| [身份系统与 agents.json](architecture/identity-and-agents-json.md) | architecture | living | 我是谁、账户从哪来、多窗口与多实例怎么区分。 | 2026-09-13 |
| [旧订单体系废弃计划](architecture/legacy-system-deprecation-plan.md) | architecture | living | 旧 orders/holdings 体系的安全废弃计划与已删端点清单（2026-08-25）。 | 2026-09-14 |
| [记忆与召回](architecture/memory-and-recall.md) | architecture | living | 结论写进哪、下次怎么被想起来、怎么知道检索有没有在工作。 | 2026-09-13 |
| [页面插件契约](architecture/page-plugin-contract.md) | architecture | living | 做一个 DSH 页面插件（GUI）要满足哪些契约；改动怎么生效。 | 2026-09-16 |
| [插件模型与装载](architecture/plugin-model.md) | architecture | living | agent-dh 的插件是什么、怎么被加载、改完怎么才能生效、常见坑在哪。 | 2026-09-14 |
| [pmboard-code-flow.md](architecture/pmboard-code-flow.md) | — | — | dsh-pmboard 是一个 DSH 双半插件（host + client）：host 半把「需求流水线」实现成 | — |
| [pmboard-ui-glossary.md](architecture/pmboard-ui-glossary.md) | — | — | 下拉条目状态徽标用词（刻意与泳道不同，2026-09-21 用户裁定保留）：实施中 / 待验收 / 完成；其余与泳道一致。 | — |
| [六立项类型的流程差异（reqboard）](architecture/reqboard-category-flows.md) | architecture | living | feature/bug/refactor/spike/doc/chore 六类需求各自走什么节点、过哪些门、哪里生效哪里是缺口——以代码为准的实测记录。 | 2026-09-23 |
| [reqboard-design-stage.md](architecture/reqboard-design-stage.md) | — | — | 根据 REQ-2d1c74 扩展，feature 需求的设计阶段必须交付以下文档： | — |
| [reqboard-doc-path-contract.md](architecture/reqboard-doc-path-contract.md) | — | — | 登记产物/文档路径时必须归一，历史遗留的下列写法由归一层在读取时兜底： | — |
| [节点详情面板（锚定式 node-panel）](architecture/reqboard-node-panel.md) | architecture | living | 会话流程条节点点开后的就地面板：锚定在流程条下方右侧、无遮罩无底栏；「基础信息」按节点给该看的，「执行流程」把该阶段提示词的纪律与真实台账做规定 vs 实际对照；实施节点改 DAG·泳道双视… | 2026-09-23 |
| [需求节点详情系统（stage-detail）](architecture/reqboard-stage-detail.md) | architecture | living | 会话框流程条节点点开看详情：StageDetail 契约 + 模板模式双端装配 + 分类流程档案 + 产物闸门 + 追溯链 + 接力任务卡 + 前端工作记录渲染器；含子任务层与自动链控制面（… | 2026-09-21 |
| [需求看板的 Token 消耗（过程消耗 + 提示词成本）](architecture/reqboard-token-usage.md) | architecture | living | 看板怎么记录与展示「每个流程节点/每个任务」的 token 消耗，以及固定系统提示词与 reqboard 注入提示词的成本；含缺失语义与自检命令。 | 2026-09-18 |
| [需求归档规范（reqboard 执行细则）](architecture/requirement-archive.md) | architecture | living | 需求归档执行细则：归档要备哪些材料、合并去向怎么定、代码在哪校验。 | 2026-09-13 |
| [self_restart 工具行为说明](architecture/self-restart-behavior.md) | architecture | living | self_restart 工具的行为说明与失败排查（状态文件、门控、常见误判）。 | 2026-09-14 |
| [workflow-stages.md](architecture/workflow-stages.md) | — | — | （STAGE_ARTIFACT_REQUIREMENTS.design = ['plan']、ARTIFACT_CONFIRM_GATES['design>decomposing'] = '… | — |

### 技术要求规范（强制卷） · `docs/standards`（9 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [账户与交易纪律（边界 / 下单前检查 / reason）](standards/account-and-trading.md) | standard | living | 动钱之前必须满足什么；账户名从哪来。 | 2026-09-13 |
| [留痕与文档规范（写哪里 / 不写哪里）](standards/audit-and-docs.md) | standard | living | 一次工作做完，结论该写进哪个系统；什么内容不该写。 | 2026-09-13 |
| [构建与发版规范（改了不等于生效）](standards/build-and-release.md) | standard | living | 改完代码怎么让它真正生效；哪些"看起来部署了"其实没有。 | 2026-09-14 |
| [编码与协作规范（命名 / 放置 / worktree / 注释写为什么）](standards/coding.md) | standard | living | 写代码与文档时的命名、放置、协作约定；违反会造成什么。 | 2026-09-13 |
| [数据与降级规范（契约 / 新鲜度 / 不许静默降级）](standards/data-and-degradation.md) | standard | living | 数据从哪来、什么样的数据不能用来决策、降级时怎么写才算诚实。 | 2026-09-13 |
| [插件与页面插件规范（Service / 两半 / 样式令牌）](standards/plugin-and-pages.md) | standard | living | 写一个新的 agent-dh 插件（或有 GUI 的页面插件）要遵守什么。 | 2026-09-13 |
| [边界与安全规范（多实例 / 只读 / 显式降权）](standards/security-and-boundaries.md) | standard | living | 同机多实例、多账户、多窗口并行时，什么动作会伤到别人。 | 2026-09-13 |
| [测试与门禁规范（真实数据 / 故障注入 / 线上证据）](standards/testing.md) | standard | living | 什么算"测过了"；哪些自证清白的方式其实不算数。 | 2026-09-13 |
| [工具开发规范（defineTool / schema 铁律 / 诚实失败）](standards/tool-development.md) | standard | living | 给 agent 加一个工具时，哪些是硬约束、违反会怎样、怎么自检。 | 2026-09-13 |

### 工具与协议 · `docs/protocols`（2 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [工具审计清单](protocols/tool-audit.md) | protocol | living | 怎么查一个工具"说到的"是不是"做到的"（定期抽查 / 接手陌生插件时用）。 | 2026-09-13 |
| [交易执行协议（Trade Execution Protocol）](protocols/trade-execution-protocol.md) | protocol | living | 交易打标协议 v1.0：每笔交易如何带 genome_version / rules_used 进经验库。 | 2026-09-14 |

### 指南（怎么做 / 怎么排障） · `docs/guides`（23 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [Agent-DH 快速参考卡片](guides/QUICKREF.md) | guide | living | 常用命令速查卡片：启停实例、看日志、跑巡检（含「别用 kill」红线）。 | 2026-09-14 |
| [Agent-DH 快速开始指南](guides/QUICKSTART.md) | guide | living | 5 分钟把 agent-dh 跑起来：前置依赖、启动步骤、验证方法。 | 2026-09-13 |
| [Agent-DH 启动指南](guides/STARTUP.md) | guide | living | 运行目录与 profile 现状（DSH_HOME=.dsh-data）、启停与 launchd，含 GUI 401 根因与迁移/布局合并的坑。 | 2026-09-14 |
| [Agent-DH 使用指南](guides/USAGE-GUIDE.md) | guide | living | v0.1.1 时代的使用说明：可用性状态与日常操作入口（历史，部分已被新规范取代）。 | 2026-09-14 |
| [事件查询最佳实践（P1-4）](guides/event-query-best-practices.md) | guide | living | 事件查询最佳实践：盘前用两个事件工具查什么、怎么查、别踩什么坑。 | 2026-09-14 |
| [事件查询统一指南（P1-4）](guides/event-query-guide.md) | guide | living | 两个事件查询工具怎么选、字段怎么读（统一指南）。 | 2026-09-13 |
| [git-worktree-workflow-simple.md](guides/git-worktree-workflow-simple.md) | — | — | 就这么简单：立项建 worktree → 开发中随时 commit → 完成后合并删除 | — |
| [git-worktree-workflow.md](guides/git-worktree-workflow.md) | — | — | 在 PI Investment 项目中，多个 Claude 会话或人工可能同时工作： | — |
| [从 agent-ts（PI 投资顾问·TS版）会话学习报告](guides/learnings-from-agent-ts.md) | guide | living | 从 agent-ts（TS 版投顾）的会话里学到的回答模板与经验。 | 2026-09-14 |
| [订单 API 使用指南](guides/order-api-guide.md) | guide | living | 两套订单 API 的区别与正确用法（新 API 优先，2026-08-25）。 | 2026-09-14 |
| [quantsys-v2 能力诚实评估：真能解决问题吗？](guides/quantsys-v2-capability-assessment.md) | guide | living | v2 后端能力诚实评估：哪些真能用、哪些是「接口通但链路死」（2026-09-02 全链路实测）。 | 2026-09-14 |
| [reqboard-capture-troubleshooting.md](guides/reqboard-capture-troubleshooting.md) | — | — | ⚠️ 不要只依赖 stdout/控制台日志（REQ-f6307c 的核心教训）。stdout 在以下情形全部蒸发： | — |
| [需求看板实操（从立项到归档）](guides/reqboard-workflow.md) | guide | living | 一个需求从冒出来到归档，具体敲哪些工具、卡在哪、错了怎么办。 | 2026-09-24 |
| [重启防丢 Session 操作手册（Restart Session Safety Runbook）](guides/restart-session-safety.md) | guide | living | 重启（含 self_restart）后会话历史为什么不丢、怎么保证——附 PID 与源码级证据。 | 2026-09-14 |
| [定时巡检清单（有问题才打扰）](guides/routine-checks.md) | guide | living | 哪些检查该定期跑、跑什么命令、什么算有问题、出了问题找谁。 | 2026-09-13 |
| [技能装载机制（Skill Loading）——排障实录与标准流程](guides/skill-loading.md) | guide | living | 技能为什么看不见：两个 dsh home + skill registry 分层，以及正确的装载姿势。 | 2026-09-14 |
| [task-execution-migration.md](guides/task-execution-migration.md) | — | — | 本指南说明如何从旧的任务执行方式迁移到基于 DSH Workflow 的新系统。 | — |
| [工具 render 人话首行约定（renderSmart）](guides/tool-render-human-summary.md) | — | — | 工具的 output.render 返回文本必须是： | — |
| [交易约束速查](guides/trading-constraints.md) | guide | living | 下单前要过的硬约束，一张表查完（完整纪律见 账户与交易纪律）。 | 2026-09-13 |
| [故障排查手册（症状 → 根因 → 处置）](guides/troubleshooting.md) | guide | living | 遇到这些症状，先看哪里、大概率是什么、怎么修。 | 2026-09-15 |
| [M6 周报推送使用指南](guides/weekly-report-push-guide.md) | guide | living | 周报推送到飞书的配置与使用步骤。 | 2026-09-13 |
| [workflow-migration-guide.md](guides/workflow-migration-guide.md) | — | — | 本指南说明如何从旧的任务执行方式迁移到基于 DSH Workflow 的新系统。 | — |
| [workflow-tools-guide.md](guides/workflow-tools-guide.md) | — | — | 本指南说明如何使用基于 DSH Workflow 的新任务执行工具。 | — |

### 设计与实施方案（历史） · `docs/design`（11 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [dashboard 页面插件 · 详细实施方案（数据链路实测版）](design/dashboard-implementation-detail.md) | design | living | 看板页面插件的数据链路实测细化（端点/参数/返回字段，2026-09-03 curl 打样）。 | 2026-09-14 |
| [看板插件实现方案 · dashboard-holdings / dashboard-execution（双插件）](design/dashboard-implementation-plan.md) | design | archived | 双看板（holdings/execution）方案稿（已落地，形态后被纠正为双半插件；历史设计）。 | 2026-09-13 |
| [page1 账户持仓看板（dashboard-holdings）实施方案](design/page1-holdings-implementation-plan.md) | design | archived | holdings 独立包补齐方案（已实施）：当时「包从未创建」缺口是怎么闭合的。 | 2026-09-13 |
| [pmboard-final-status.md](design/pmboard-final-status.md) | — | — | 用户反馈："项目任务页的变化我没看见" | — |
| [pmboard-node-content-design.md](design/pmboard-node-content-design.md) | — | — | 当前点击 DAG 图中的任何节点，都显示相同的任务详情页面（执行记录、评论、时间线等）。这种"一刀切"的展示方式不够直观，无法突出不同节点类型的核心信息。 | — |
| [pmboard-task-page-delivery.md](design/pmboard-task-page-delivery.md) | — | — | ✅ 统计卡片区 | — |
| [pmboard-task-page-implementation-complete.md](design/pmboard-task-page-implementation-complete.md) | — | — | 1. toggle-section - 折叠/展开章节 | — |
| [pmboard-task-page-implementation-summary.md](design/pmboard-task-page-implementation-summary.md) | — | — | 需要修改 packages/pages/dsh-pmboard/src/client/board-mount.ts： | — |
| [pmboard-task-page-test-plan.md](design/pmboard-task-page-test-plan.md) | — | — | 1. 打开 http://127.0.0.1:13080 | — |
| [pmboard-task-page-ui-improvement.md](design/pmboard-task-page-ui-improvement.md) | — | — | 基于用户反馈，当前任务页存在以下问题： | — |
| [pmboard-task-page-ui-preview.md](design/pmboard-task-page-ui-preview.md) | — | — | — | — |

### RFC 设计提案 · `docs/rfcs`（15 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [RFC 003: Agent Self-Learning and Distillation System](rfcs/003-self-learning-distillation.md) | rfc | living | RFC 003：经验追踪 → 知识蒸馏 → 规则转正的自学习系统设计。 | 2026-09-14 |
| [RFC 005: 自进化投资 Agent（Self-Evolving Investment Agent）](rfcs/005-self-evolving-agent.md) | rfc | living | RFC 005：自进化 Agent 设计（Phase 1-3 已落地，Phase 4 元学习待启动）。 | 2026-09-14 |
| [RFC 006: P0-1 提示词基因组切分（宪法层 / 可进化段）实现计划](rfcs/006-prompt-genome-sections.md) | rfc | living | RFC 006：提示词基因组分段（宪法/原则/规则/教训）设计提案。 | 2026-09-14 |
| [RFC 007: P0-2 genome_manager 工具化（版本快照 / 段更新 / 回滚 / changelog）实现方案](rfcs/007-genome-manager.md) | rfc | living | RFC 007：genome_manager 工具化设计提案（段读写、版本与候选）。 | 2026-09-14 |
| [RFC 008: P2 验证门（Validation Gate）——回测 + 模拟盘 A/B + 自动裁决](rfcs/008-validation-gate.md) | rfc | living | RFC 008：验证门——候选段观察期后对比基准决定转正或回滚（已实施并验收）。 | 2026-09-14 |
| [RFC 009：盯盘推送双通道方案（direct 直推 / agent 判断分流）](rfcs/009-watch-push-dual-channel.md) | rfc | living | RFC 009：盯盘推送双通道设计（草案）。 | 2026-09-14 |
| [RFC 011：工具 Web 自定义卡片（Tool Web Cards）统一实现规范](rfcs/011-tool-web-cards.md) | rfc | living | RFC 011：工具调用在 GUI 里的 Web 卡片展示（草案）。 | 2026-09-14 |
| [RFC 013：公告板页面（dashboard-bulletin）](rfcs/013-bulletin-board-page.md) | rfc | living | RFC 013：公告板页面插件设计（双半插件，与 board_* 工具同源）。 | 2026-09-14 |
| [P1-3: 判断结果自动对账系统 DDD 重构设计](rfcs/013-decision-evaluation-ddd-refactor.md) | rfc | living | RFC 013：决策评估 DDD 重构（decision_audit 评估引擎 + agent_decisions 表）。 | 2026-09-14 |
| [RFC 014 需求看板](rfcs/014-requirement-board.md) | rfc | living | RFC 014：需求看板（reqboard）设计——状态机、人工闸门与归档。 | 2026-09-13 |
| [015-dsh-structure-alignment-plan.md](rfcs/015-dsh-structure-alignment-plan.md) | — | — | 期望：完全无输出（工作区干净）。若有输出 → 停，等对应会话收尾后再来。 | — |
| [015-dsh-structure-alignment.md](rfcs/015-dsh-structure-alignment.md) | — | — | dsh 框架仓库的组织方式是 apps/{cli,desktop,web} 应用入口 + packages/<domain>/<pkg> 技术域两级归类 | — |
| [016-quick-restart.md](rfcs/016-quick-restart.md) | — | — | 2026-09-22 用户裁定 :13080 重启入口收敛为 scripts/stop.sh + start.sh 唯一一套（launchd 全部退役）。 | — |
| ["实施过程中展示代码 diff（pmboard）"](rfcs/REQ-260922204751-cb0f/requirement.md) | — | brainstorming | 相关代码：src/application/use-cases/ReportTask.ts、src/http/routers/artifacts.ts（文件白名单 classify()）、sr… | — |
| [RFC 010 Phase 1 - Window-OS Lifecycle Management](rfcs/RFC-010-README.md) | rfc | living | RFC 010 Phase 1：多窗口协同（窗口注册、角色化派单、窗口间消息、心跳容错）。 | 2026-09-14 |

### 示例 · `docs/examples`（1 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [事件查询使用示例（P1-4）](examples/event-query-examples.md) | doc | living | 事件查询两个工具的实战示例（盘前例行、个股排雷等）。 | 2026-09-14 |

### 包内入口页（怎么用这个包） · `packages`（118 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [@pi-investment/core-tool-tool](../packages/core/core-tool/README.md) | package | living | core-tool 规范包：只定义三段式工具接口规范，不含具体实现。 | 2026-08-30 |
| [@pi-investment/learning](../packages/tools/learning/README.md) | package | living | learning 插件：经验追踪 / 模式挖掘 / 知识蒸馏 / 规则转正（RFC 003 落地）。 | 2026-08-20 |
| [@pi-investment/dashboard-bulletin（公告板页面，RFC 013）](../packages/web/bulletin/README.md) | package | living | 公告板页面包（双半插件）：与 board_post/board_read 工具同源的看板。 | 2026-09-05 |
| [CHANGELOG-req-id-timestamp.md](../packages/web/dsh-pmboard/CHANGELOG-req-id-timestamp.md) | — | — | 将需求ID格式从 REQ-xxxxxx (6位随机hex) 升级为 REQ-YYMMDDHHmmss-xxxx (时间戳+4位随机hex)，提升可读性和可追溯性。 | — |
| [CHANGELOG.md](../packages/web/dsh-pmboard/CHANGELOG.md) | — | — | All notable changes to this project will be documented in this file. | — |
| [CONFLICT-REPORT.md](../packages/web/dsh-pmboard/CONFLICT-REPORT.md) | — | — | 发现 6 种需求类型 存在模板与门禁规则不一致的问题。 | — |
| [FIX-REPORT.md](../packages/web/dsh-pmboard/FIX-REPORT.md) | — | — | 根据你的决策，已完成以下修改： | — |
| [README.md](../packages/web/dsh-pmboard/README.md) | — | — | 把「用户在对话里提出一个想法」到「需求立项 → 评审 → 拆分 → 实施 → 验收 → 归档」的完整生命周期， | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/bug.md) | — | — | — | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/chore.md) | — | — | — | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/doc.md) | — | — | — | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/feature.md) | — | — | — | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/heavy.md) | — | — | If you haven't run the verification command in this message, you cannot claim it passes. | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/heavy/overrides.md) | — | — | — | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/light.md) | — | — | （命令 + 输出摘要 / 测试报告路径）。 | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/refactor.md) | — | — | — | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/accepting/spike.md) | — | — | — | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/bug.md) | — | — | — | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/chore.md) | — | — | — | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/doc.md) | — | — | — | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/feature.md) | — | — | — | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/heavy.md) | — | — | Run the project's full test suite (npm test / cargo test / pytest / go test ./...). | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/heavy/overrides.md) | — | — | — | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/light.md) | — | — | （requirement / plan / verification / retro 等）。 | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/refactor.md) | — | — | — | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/archived/spike.md) | — | — | — | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/bug.md) | — | — | 先复现再改——根因不清不许动手： | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/chore.md) | — | — | 需求文档里的每条功能点/条款必须写成 G2 clause 门禁认得的定义行，否则解析不到、条款接收状态全红： | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/doc.md) | — | — | 需求文档里的每条功能点/条款必须写成 G2 clause 门禁认得的定义行，否则解析不到、条款接收状态全红： | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/feature.md) | — | — | 需求文档里的每条功能点/条款必须写成 G2 clause 门禁认得的定义行，否则解析不到、条款接收状态全红： | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/heavy.md) | — | — | Help turn ideas into fully formed designs and specs through natural collaborative dialogue. | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/heavy/overrides.md) | — | — | — | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/light.md) | — | — | 判定标准（跑什么、看到什么算完成）。禁止"优化一下""体验更好"这类不可验证的话。 | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/refactor.md) | — | — | 需求文档里的每条功能点/条款必须写成 G2 clause 门禁认得的定义行，否则解析不到、条款接收状态全红： | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/brainstorming/spike.md) | — | — | 需求文档里的每条功能点/条款必须写成 G2 clause 门禁认得的定义行，否则解析不到、条款接收状态全红： | — |
| [iron-rules.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/common/iron-rules.md) | — | — | — | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/bug.md) | — | — | — | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/chore.md) | — | — | — | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/doc.md) | — | — | — | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/feature.md) | — | — | — | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/heavy.md) | — | — | ＋ 怎么算完（可证伪 acceptance）＋ 依赖。 | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/light.md) | — | — | （key / title / phase / side / depends_on / implementation / acceptance）， | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/refactor.md) | — | — | — | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/decomposing/spike.md) | — | — | — | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/bug.md) | — | — | — | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/chore.md) | — | — | — | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/doc.md) | — | — | — | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/feature.md) | — | — | — | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy.md) | — | — | （缺交会在提交拆分计划时被代码级拦下）。 | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md) | — | — | — | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light.md) | — | — | 落盘后会被自动登记为 design 产物——若确认时报"没有 kind=design 的产物"， | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md) | — | — | — | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/refactor.md) | — | — | — | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/design/spike.md) | — | — | — | — |
| [bug.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/bug.md) | — | — | — | — |
| [chore.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/chore.md) | — | — | — | — |
| [doc.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/doc.md) | — | — | — | — |
| [feature.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/feature.md) | — | — | — | — |
| [heavy.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/heavy.md) | — | — | Load plan, review critically, execute all tasks, report when complete. | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/heavy/overrides.md) | — | — | — | — |
| [light.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/light.md) | — | — | 直接改，不临时加功能、不扩范围。 | — |
| [overrides.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/light/overrides.md) | — | — | — | — |
| [refactor.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/refactor.md) | — | — | — | — |
| [spike.md](../packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/spike.md) | — | — | — | — |
| [ATTRIBUTION.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/ATTRIBUTION.md) | — | — | 本目录下的 14 份 <skill>/SKILL.md 是 obra/superpowers 的原文（逐字节落盘、不改写）， | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/brainstorming/SKILL.md) | — | — | Help turn ideas into fully formed designs and specs through natural collaborative dialogue. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/dispatching-parallel-agents/SKILL.md) | — | — | You delegate tasks to specialized agents with isolated context. By precisely crafting their ins… | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/executing-plans/SKILL.md) | — | — | Load plan, review critically, execute all tasks, report when complete. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/finishing-a-development-branch/SKILL.md) | — | — | Run the project's full test suite (npm test / cargo test / pytest / go test ./...). | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/receiving-code-review/SKILL.md) | — | — | Code review requires technical evaluation, not emotional performance. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/requesting-code-review/SKILL.md) | — | — | Dispatch a code reviewer subagent to catch issues before they cascade. The reviewer gets precis… | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/subagent-driven-development/SKILL.md) | — | — | Execute plan by dispatching a fresh implementer subagent per task, a task review (spec complian… | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/systematic-debugging/SKILL.md) | — | — | If you haven't completed Phase 1, you cannot propose fixes. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/test-driven-development/SKILL.md) | — | — | Write the test first. Watch it fail. Write minimal code to pass. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/using-git-worktrees/SKILL.md) | — | — | Ensure work happens in an isolated workspace. Prefer your platform's native worktree tools. Fal… | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/using-superpowers/SKILL.md) | — | — | — | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/verification-before-completion/SKILL.md) | — | — | If you haven't run the verification command in this message, you cannot claim it passes. | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/writing-plans/SKILL.md) | — | — | Write comprehensive implementation plans assuming the engineer has zero context for our codebas… | — |
| [SKILL.md](../packages/web/dsh-pmboard/src/domain/prompt/vendor/superpowers/writing-skills/SKILL.md) | — | — | You write test cases (pressure scenarios with subagents), watch them fail (baseline behavior), … | — |
| [README.md](../packages/web/dsh-pmboard/templates/README.md) | — | — | 生成器映射规则就一行：templates/<stage>/<doc>.md → 需求目录 docs/requirements/<REQ>/…， | — |
| [verification.md](../packages/web/dsh-pmboard/templates/accepting/verification.md) | — | — | （本节由窗口根据 requirement.md 功能点表 + decomposition.md 覆盖对照生成： | — |
| [index.md](../packages/web/dsh-pmboard/templates/archived/index.md) | — | — | — | — |
| [retro.md](../packages/web/dsh-pmboard/templates/archived/retro.md) | — | — | — | — |
| ["{{TITLE}}"](../packages/web/dsh-pmboard/templates/brainstorming/bug.md) | — | brainstorming | （为什么现在要做：用户原话用 > 引用块 / 线上现象 / 数据证据。标注来源与时点。 | — |
| ["{{TITLE}}"](../packages/web/dsh-pmboard/templates/brainstorming/chore.md) | — | brainstorming | （为什么现在要做：用户原话用 > 引用块 / 线上现象 / 数据证据。标注来源与时点。 | — |
| ["{{TITLE}}"](../packages/web/dsh-pmboard/templates/brainstorming/doc.md) | — | brainstorming | （为什么现在要做：用户原话用 > 引用块 / 线上现象 / 数据证据。标注来源与时点。 | — |
| [feature.md](../packages/web/dsh-pmboard/templates/brainstorming/feature.md) | — | — | （一句话说清楚这个产品是什么、核心价值是什么——电梯演讲版本。） | — |
| ["{{TITLE}}"](../packages/web/dsh-pmboard/templates/brainstorming/refactor.md) | — | brainstorming | （为什么现在做：坏味道 / 演进需要 / 外部驱动，给数据支撑——复杂度、构建耗时、故障次数、 | — |
| ["{{TITLE}}"](../packages/web/dsh-pmboard/templates/brainstorming/spike.md) | — | brainstorming | （为什么现在要做：用户原话用 > 引用块 / 线上现象 / 数据证据。标注来源与时点。 | — |
| [notes.md](../packages/web/dsh-pmboard/templates/common/notes.md) | — | — | — | — |
| [decomposition.md](../packages/web/dsh-pmboard/templates/decomposing/decomposition.md) | — | — | （覆盖对照靠编号跨文档拉齐；引用必须能在对方文档里查到——查不到 = 悬空引用，等同于没写。） | — |
| [architecture.md](../packages/web/dsh-pmboard/templates/design/architecture.md) | — | — | （3 句以内：做什么、怎么做、为什么这么做——评审者 20 秒读完） | — |
| [backend.md](../packages/web/dsh-pmboard/templates/design/backend.md) | — | — | 1. 触发事件：什么事件触发这个流程（用户操作/定时任务/钩子） | — |
| [data-model.md](../packages/web/dsh-pmboard/templates/design/data-model.md) | — | — | （ASCII ER 图：实体 + 关系基数，一眼看清谁连谁。） | — |
| [frontend.md](../packages/web/dsh-pmboard/templates/design/frontend.md) | — | — | （可视化原型：prototypes/<name>.html（由 prototype.html 模板生成，每功能点一个锚点区块）； | — |
| [interfaces.md](../packages/web/dsh-pmboard/templates/design/interfaces.md) | — | — | （编号 I-x——拆分计划的覆盖对照按它引用；改本表后回查 decomposition.md 覆盖对照。） | — |
| [migration.md](../packages/web/dsh-pmboard/templates/design/migration.md) | — | — | （逐步可执行：每步给验证命令，给失败时的回滚动作。编号 M-x：用例/故障注入引用步骤时用。） | — |
| [test-cases.md](../packages/web/dsh-pmboard/templates/design/test-cases.md) | — | — | （每条功能点 × 测试类型：哪些层要测，空格 = 该层不测，写理由。） | — |
| [use-cases.md](../packages/web/dsh-pmboard/templates/design/use-cases.md) | — | — | （编号 UC-x：test-cases「被测对象」、任务卡「设计落点」引用场景时用。） | — |
| [architecture.example.md](../packages/web/dsh-pmboard/templates/examples/architecture.example.md) | — | — | — | — |
| [backend.example.md](../packages/web/dsh-pmboard/templates/examples/backend.example.md) | — | — | 1. 拼接查询 key：将 stage 和 category 用点号连接，如 "brainstorming.feature" | — |
| [data-model.example.md](../packages/web/dsh-pmboard/templates/examples/data-model.example.md) | — | — | （根据 template_key 是否为空推断类型） | — |
| [decomposition.example.md](../packages/web/dsh-pmboard/templates/examples/decomposition.example.md) | — | — | T/UC/M 是按需扩展——涉及数据模型/场景/迁移时才编号；本例未涉及，故下方对照未出现。 | — |
| [feature.example.md](../packages/web/dsh-pmboard/templates/examples/feature.example.md) | — | — | 1. 当前问题：每次手动创建空白 md 文件，忘记必填章节导致验收时返工（实测：平均每个需求返工 2 次，浪费 1 小时） | — |
| [frontend.example.md](../packages/web/dsh-pmboard/templates/examples/frontend.example.md) | — | — | 原型文件：prototypes/template-preview.html | — |
| [interfaces.example.md](../packages/web/dsh-pmboard/templates/examples/interfaces.example.md) | — | — | — | — |
| [migration.example.md](../packages/web/dsh-pmboard/templates/examples/migration.example.md) | — | — | 1. M-3 执行后 5 分钟内，错误日志 "kind constraint violation" > 10 次 | — |
| [requirement.feature.example.md](../packages/web/dsh-pmboard/templates/examples/requirement.feature.example.md) | — | — | 需求文档模板系统：PM 和开发在创建需求时，系统根据需求类型（feature/bug/refactor/spike/doc/chore）自动生成对应的文档骨架，包含必填章节、填写提示和示例，… | — |
| ["示例：注入段装配器重构（三处各拼 → 统一装配）"](../packages/web/dsh-pmboard/templates/examples/requirement.refactor.example.md) | — | brainstorming | 三个阶段提示词注入点（系统提示词段、闸门后置链 H3、节点输入包）各自拼一次注入文本， | — |
| [test-cases.example.md](../packages/web/dsh-pmboard/templates/examples/test-cases.example.md) | — | — | （说明：FR-6 的设计对象为 —（CI 脚本，无运行时 S-x）；TC-7 的被测对象写为 check-templates.mjs。） | — |
| [use-cases.example.md](../packages/web/dsh-pmboard/templates/examples/use-cases.example.md) | — | — | 1. PM 在项目看板点击左上角"新建需求"按钮 → 系统弹出需求创建表单 | — |
| [review.md](../packages/web/dsh-pmboard/templates/implementing/review.md) | — | — | （打回项的修订记录；复审结论。验收评审须留利益相关方确认记录。） | — |
| [task-card.md](../packages/web/dsh-pmboard/templates/implementing/task-card.md) | — | — | （一句话 + 改哪些文件） | — |
| [test-evidence.md](../packages/web/dsh-pmboard/templates/implementing/test-evidence.md) | — | — | （分支 / commit / 依赖版本——没有环境的「跑通了」不可复现。） | — |
| [@pi-investment/dashboard-execution](../packages/web/execution/README.md) | package | living | 双线执行确认看板包：v2/os 健康 + 调度任务 + 检查点与时间轴。 | 2026-09-04 |
| [@pi-investment/dashboard-genome · 自主进化看板](../packages/web/genome/README.md) | package | living | 自主进化看板包：基因组目录、候选状态与进化链路的可视化。 | 2026-09-13 |
| [@pi-investment/dashboard-holdings](../packages/web/holdings/README.md) | package | living | 账户持仓看板包：多账户摘要、持仓明细、合规监控、盯盘中心。 | 2026-09-04 |
| [@pi-investment/web-liveness · 页面自愈（重启后标签页不再变砖）](../packages/web/web-liveness/README.md) | package | living | 监听框架免鉴权的 /plugins/events SSE，发现服务端换过进程就自动刷新已打开的标签页。 | 2026-09-16 |

### 示例目录 · `examples`（1 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [Agent-DH 示例](../examples/README.md) | example | living | agent-dh 使用示例目录：从最简 agent loop 到工具调用的可运行样例。 | 2026-08-30 |

### 仓库入口 · `root`（1 页）

| 页 | type | status | 一句话 | 更新 |
|---|---|---|---|---|
| [Agent-DH](../README.md) | manual | living | agent-dh 是什么、代码怎么组织、怎么启动——仓库入口页。 | 2026-09-11 |
