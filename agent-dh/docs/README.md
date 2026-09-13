---
id: agent-dh-home
title: agent-dh Wiki（归档文档首页 / 大纲）
type: manual
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [wiki, index, home, agent-dh]
---

# agent-dh Wiki

> **以 agent-dh 为准的归档文档 wiki**。上层是项目级 wiki（[docs/README.md](../../docs/README.md)），
> 本页是 **agent-dh 子项目**的认知入口与**大纲**。
>
> 读法：本页 → 对应卷的页面（L2）→ 只有追溯"当时为什么"才下钻需求档案与工作日志（L3）。
> 每页可独立读懂，页尾有「相关页面」把自己挂回页面图。规范见
> [文档规范](../../docs/DOCUMENT-MANAGEMENT-PLAN.md) 的「Wiki 化：页面模型」章。

## 一页速览（读完这 8 行再动手）

- **agent-dh 是什么**：DSH（DeepSeek Harness）的一个 Profile——插件树 + 系统提示词 + 工具，
  以投资 agent 的身份跑在 :13080（launchd 托管）。
- **代码在哪**：`agent-dh/packages/*`（插件）、`agent-dh/skills/*`（技能）、`agent-dh/scripts/*`（运维脚本）、
  `agent-dh/docs/*`（本 wiki）。
- **改动怎么生效**：源码改完不一定生效——多数包从 `dist/` 加载，发版走
  `scripts/restart-with-build.sh`（relink → build → kickstart）。见卷 8。
- **工作怎么组织**：需求看板（reqboard）两级流水线 + 计划模式 + 验收人工审核 + 归档文档合并。见卷 7。
- **我的身份与纪律**：身份来自 `agents.json`，纪律来自基因组（宪法/原则/规则/教训）。见卷 5。
- **钱怎么动**：账户与约束（T+1、仓位上限、止损、现金≥10%）在宪法层；下单走工具 + trade_guard。见卷 3。
- **数据从哪来**：quantsys-v2（:5001）与多源降级链；数据新鲜度是硬前提。见卷 4。
- **出问题找谁**：先跑巡检/看日志，常见故障与恢复步骤在卷 8。

## 大纲：9 卷

> 状态：✅ = 已有页面（给出链接）；🟡 = 待写页（已登记，按优先级补）。
> 优先级 P0 = 高频且素材齐；P1 = 常用；P2 = 按需。

### 卷 0 · 说明书（Overview）

- ✅ [项目说明书（项目级 L1）](../../docs/architecture/project-manual.md)
- 🟡 P0 `overview/agent-dh-what-is.md` —— agent-dh 是什么：profile / 插件树 / 目录地图 / 运行形态（素材：CLAUDE.md）
- 🟡 P0 `overview/glossary.md` —— agent-dh 术语表（profile、插件、工具、基因组、reqboard、页面插件…）

### 卷 1 · 架构与生命周期

- 🟡 P0 `architecture/plugin-model.md` —— 插件模型与装载：cordis、service/inject、schema 铁律、页面插件 host/client 两半
- ✅ [自修复重启行为](architecture/self-restart-behavior.md)
- ✅ [某些包为何没有 dist](architecture/WHY-NO-DIST.md)
- ✅ [工具清单](architecture/TOOLS_INVENTORY.md)
- 🟡 P1 `architecture/profile-and-dsh-home.md` —— profile / DSH_HOME / 软链与发版（relink-profile、dist 陈旧陷阱）
- 🟡 P1 `architecture/identity-and-agents-json.md` —— 身份系统：agents.json、窗口编码、多实例边界

### 卷 2 · 工具与协议

- ✅ [工具清单](architecture/TOOLS_INVENTORY.md)
- 🟡 P0 `protocols/tool-contract.md` —— 工具契约：defineTool、schema 铁律、返回结构、错误码、降级与"诚实失败"
- 🟡 P1 `protocols/tool-audit.md` —— 工具审计清单：声明与实现是否一致、默认账户值、dry_run 真假
- ✅ [交易执行协议](protocols/trade-execution-protocol.md)

### 卷 3 · 账户与交易

- 🟡 P0 `architecture/accounts-and-boundaries.md` —— 账户模型与边界（agent_brain 自营 / agent_virtual 只读 / 策略线账户）
- 🟡 P0 `guides/trading-constraints.md` —— 交易约束速查：T+1、100 股整数倍、仓位/行业/现金上限、止损档位
- ✅ [下单 API 指南](guides/order-api-guide.md)

### 卷 4 · 数据与后端

- 🟡 P0 `architecture/data-contracts-and-freshness.md` —— 数据契约、新鲜度与降级（R-020、静默失效的教训）
- ✅ [quantsys-v2 能力评估](guides/quantsys-v2-capability-assessment.md)
- ✅ [事件查询最佳实践](guides/event-query-best-practices.md)
- ✅ [数据库表对照](architecture/database-table-comparison.md)

### 卷 5 · 自主能力（基因组 / 记忆 / 学习 / 进化）

- ✅ [自主能力总览](architecture/AUTONOMY-SYSTEM.md)
- ✅ [RFC-005 自进化 Agent](rfcs/005-self-evolving-agent.md)
- ✅ [RFC-006 基因组分段](rfcs/006-prompt-genome-sections.md)
- ✅ [RFC-007 基因组管理](rfcs/007-genome-manager.md)
- ✅ [RFC-008 验证门](rfcs/008-validation-gate.md)
- ✅ [RFC-003 学习蒸馏](rfcs/003-self-learning-distillation.md)
- 🟡 P1 `architecture/memory-and-recall.md` —— 记忆写入/召回与注入率（含 R-008 决策前检索）

### 卷 6 · 页面插件（GUI）

- ✅ [看板实现细节](design/dashboard-implementation-detail.md)
- ✅ [RFC-011 工具 Web 卡片](rfcs/011-tool-web-cards.md)
- ✅ [RFC-013 公告板页面](rfcs/013-bulletin-board-page.md)
- 🟡 P1 `architecture/page-plugin-contract.md` —— 页面插件契约：host/client 两半、打包与刷新时机、全站样式令牌

### 卷 7 · 需求流水线与归档（本 wiki 的供料线）

- ✅ [RFC 014 需求看板](rfcs/014-requirement-board.md)
- ✅ [需求归档规范](architecture/requirement-archive.md)
- ✅ [需求归档索引](requirements/INDEX.md)
- 🟡 P0 `guides/reqboard-workflow.md` —— 从立项到归档的实操（含计划模式、验收人工审核、归档材料怎么备）

### 卷 8 · 运维与排障

- ✅ [自修复重启行为](architecture/self-restart-behavior.md)
- ✅ [启动](guides/STARTUP.md) · [速查](guides/QUICKREF.md) · [使用指南](guides/USAGE-GUIDE.md)
- ✅ [重启与会话安全](guides/restart-session-safety.md) · [技能装载](guides/skill-loading.md)
- 🟡 P0 `guides/troubleshooting.md` —— 故障排查手册（缺陷类归档的既定落点）
- 🟡 P1 `guides/routine-checks.md` —— 定时巡检清单（数据卫生探针、wiki 探针、调度看门狗…）

### 卷 9 · 附录（L3 证据层）

- ✅ [需求档案索引](requirements/INDEX.md) · [归档规范](architecture/requirement-archive.md)
- ✅ [历史遗留系统下线计划](architecture/legacy-system-deprecation-plan.md)
- ✅ [agent-ts 经验](guides/learnings-from-agent-ts.md)
- L3 正文是各需求目录与 `work-logs/`（只读证据，不在此逐条登记）

## 最近改动

| 日期 | 页面 | 变更 | 来源 |
|---|---|---|---|
| 2026-09-13 | 本页 | 建立 agent-dh wiki 首页与大纲（9 卷） | w-1cee2467 |

## 怎么维护

- 页面模型、front-matter 字段、stub 约定见 [文档规范](../../docs/DOCUMENT-MANAGEMENT-PLAN.md)；
- 新页面写完后：① 挂进本页对应卷；② 在本页「最近改动」加一行；③ 跑
  `python3 agent-dh/scripts/wiki_probe.py` 确认无死链/孤儿页；
- **写页的时机是归档**：需求完成归档时把结论合并进对应卷的页面（归档闸门会校验"说明书更新点"），
  所以这个 wiki 是**长出来的**，不是一次性写完的。
