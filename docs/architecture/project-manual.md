---
id: project-manual
title: PI Investment 项目说明书（金字塔 L1）
type: manual
status: living
updated: 2026-09-17
owners: [w-1cee2467]
tags: [manual, l1, overview]
---

# PI Investment 项目说明书（金字塔 L1）

> **这份文档是什么**：读它，你能在 5 分钟里知道这个项目是什么、由哪几块组成、关键概念叫什么、
> 去哪儿找细节。它是**文档金字塔的顶点**：本页只给认知与指针，细节在领域篇（L2），
> 证据在档案层（L3）。
>
> **给 agent 的读法**：先读本页 → 需要细节再点进对应 L2 文档 → 只有追溯"当时为什么这么做"才下钻 L3。
> 本页任何论断都能在代码或 L2 文档里核实；发现不一致时，改本页或改代码，别让两者各说各话。

## 最近更新（新知识从这里进来）

| 日期 | 更新点 | 来源 |
|---|---|---|
| 2026-09-18 | **盯盘引擎重构为「待办化闭环」**（已上线）：触发落成有 owner/SLA/终态的待办（L1→L2→L3 + 进程外 SLA 机械晋升 + 三段回执）；判据 metric 化根治"现价当量比"；历史五类自动升级删除；规则自愈把反复触发收敛为"修规则"待办；运行态跨重启持久化 | REQ-c9f899 |
| 2026-09-17 | **阶段提示词按「节点 × 难度 × 类型」路由注入**：分片库 + 5 级回退链（**难度优先于类型**）+ 单次 24000 字符预算；heavy 档用 superpowers 原文（v6.3.0 / MIT），light 档自写；六条门禁每条可红 | REQ-422af1 |
| 2026-09-17 | **项目看板流程节点统一定义**：立项→需求分析→技术设计→拆分→实施→验收→归档（7 态），唯一事实源 `workflow-stages.md`，前后端/原型/文档禁止散落定义 | REQ-6f39b5 |
| 2026-09-14 | **多源 provider 框架是取数唯一入口**：新增数据能力应加在 `providers/<域>/` + `manager`（自动获得故障转移/熔断/诚实标记），不要另写单例数据源；sentiment 域 7 个端点据此去 mock | REQ-48d896 |
| 2026-09-13 | 文档金字塔与需求归档规范确立（存底 + 合并 + 说明书更新点） | 需求看板归档线（w-1cee2467） |

## 1. 项目是什么

PI Investment 是一个**由 AI agent 自主运行的投资系统**：agent 在真实市场里做分析、决策、下单，
用「能否持续赚到钱」这一件事衡量自身智能。系统哲学、博弈框架与自主运行机制的完整页面**尚未写成**
（根 CLAUDE.md 引用的 \`docs/game-theory-framework.md\`、\`docs/agent-autonomy.md\` 目前不存在）——
已登记进 [Wiki 首页](../README.md) 的「待写页」，需要时按页面模型补页。

## 2. 三层架构（谁负责什么）

| 层 | 位置 | 职责 | 怎么跑 |
|---|---|---|---|
| **agent-ts**（AI 员工） | @Q@agent-ts/@Q@ | 定时任务、盯盘、自主决策、学习；60+ 投资工具 | Node/TS 独立进程 |
| **quantsys-v2**（量化后端） | @Q@quantsys-v2/@Q@ | 行情/K线/财务/回测/因子；操作全落审计 | Flask + PostgreSQL，:5001 |
| **前端 / DSH 页面插件**（监控与交互） | @Q@web-frontend/@Q@、@Q@agent-dh/packages/pages/@Q@ | 看板与可视化（持仓/执行/看板/基因组…） | Vue 3 或 DSH 页面插件 |

**agent-dh**（@Q@agent-dh/@Q@）是 DSH Profile：@Q@agent-dh/packages/@Q@ 下的插件包由 cordis 装载，
向 agent 提供工具与页面插件；运行实例在 :13080（launchd 托管，重启走 @Q@launchctl kickstart -k@Q@）。

## 3. 关键概念（术语表）

| 术语 | 一句话解释 | 细节在哪 |
|---|---|---|
| Profile / 插件 | DSH 的装载单元；插件用 @Q@defineTool@Q@ 注册工具 | [agent-dh/CLAUDE.md](../../agent-dh/CLAUDE.md) |
| 需求看板（reqboard） | 需求 → 任务两级流水线：立项 → 需求分析 → 技术设计 → 拆分 → 实施 → 验收 → 归档（7 态，REQ-9f4a44 起验收通过直归档，无 done 中转） | [workflow-stages.md](../../agent-dh/docs/architecture/workflow-stages.md)（唯一事实源）、[RFC 014](../../agent-dh/docs/rfcs/014-requirement-board.md) |
| **提示词加载路由** | 状态机选中哪个节点，就注入哪份阶段提示词（**节点即选择器，无需 skill 匹配**；披露 = 按节点注入）：按 `stage/difficulty/category` 解析、5 级回退（难度优先于类型）、单次注入 ≤ 24000 字符 | [workflow-stages.md「提示词加载路由」](../../agent-dh/docs/architecture/workflow-stages.md) |
| 计划模式（plan mode） | 拆分前置闸门：先写实施计划（含任务表）、人批准、才能落库任务卡 | [RFC 014 §5b](../../agent-dh/docs/rfcs/014-requirement-board.md) |
| 基因组（genome） | agent 的宪法/原则/规则/教训四段提示词，可进化、有版本与验证门 | [agent-dh/CLAUDE.md](../../agent-dh/CLAUDE.md) |
| 文档金字塔 | L1 说明书 / L2 领域篇 / L3 证据档案；归档让认知自下而上生长 | [DOCUMENT-MANAGEMENT-PLAN.md](../DOCUMENT-MANAGEMENT-PLAN.md) |
| **多源 provider 框架** | quantsys-v2 取数的**唯一入口**：`_try_providers()` 做故障转移/熔断/健康排序，并返回 `source/attempted_sources/empty_sources` 诚实标记；「空结果≠故障」 | `quantsys-v2/adapters/outbound/datasources/manager.py` |
| 诚实降级 | 无数据→显式 `empty:true`；上游损坏→拒绝返回；传输故障→`None`（进熔断）；**任何情况下都不返回无来源标记的数据** | [work-log](../work-logs/2026-09/v2-sentiment-real-data-source.md) |

## 4. 怎么跑起来

1. 后端：quantsys-v2（@Q@python start_all.py@Q@，:5001）
2. 前端（可选）：web-frontend（@Q@npm run dev@Q@）
3. agent / 看板：DSH profile（@Q@~/.dsh/profiles/.../start.sh@Q@，:13080；该端口由 launchd 托管）

## 5. 去哪儿找细节（L2 领域篇）

- 架构：[docs/architecture/](.)（本目录）
- 决策：[docs/adr/](../adr/)、提案：[docs/rfcs/](../rfcs/)
- 指南/排障：[docs/guides/](../guides/)
- 策略研究：[docs/strategy-research/](../strategy-research/)
- 子项目文档：[agent-dh/docs/](../../agent-dh/docs/)、[agent-ts/docs/](../../agent-ts/docs/)、[quantsys-v2/docs/](../../quantsys-v2/docs/)

## 6. 怎么维护（谁在什么时候改这一页）

- **改这一页的时机**：新增子系统 / 关键概念改名 / 入口或端口变化 / 金字塔结构变化；
- **谁改**：完成该需求的人（或 agent）在**归档时**申报（归档材料的 @Q@manual_updates@Q@），
  改了哪一节就在「最近更新」表追加一行；
- **不许写什么**：实现细节、临时决定、过程记录（那些属于 L2/L3）。保持这一页 5 分钟能读完。