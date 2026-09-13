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
- **动手前必读（强制）**：[卷 1 技术要求规范](README.md#卷-1--技术要求规范engineering-standards强制)——
  工具 schema 铁律、构建/发版（改完不一定生效）、测试门禁、数据契约、留痕与文档规范。
  违反它们的改动不算完成。
- **改动怎么生效**：源码改完不一定生效——多数包从 `dist/` 加载，发版走
  `scripts/restart-with-build.sh`（relink → build → kickstart）。见卷 8。
- **工作怎么组织**：需求看板（reqboard）两级流水线 + 计划模式 + 验收人工审核 + 归档文档合并。见卷 7。
- **我的身份与纪律**：身份来自 `agents.json`，纪律来自基因组（宪法/原则/规则/教训）。见卷 5。
- **钱怎么动**：账户与约束（T+1、仓位上限、止损、现金≥10%）在宪法层；下单走工具 + trade_guard。见卷 3。
- **数据从哪来**：quantsys-v2（:5001）与多源降级链；数据新鲜度是硬前提。见卷 4。
- **出问题找谁**：先跑巡检/看日志，常见故障与恢复步骤在卷 8。

## 大纲：10 卷

> 状态：✅ = 已有页面（给出链接）；🟡 = 待写页（已登记，按优先级补）。
> 优先级 P0 = 高频且素材齐；P1 = 常用；P2 = 按需。

### 卷 0 · 说明书（Overview）

- ✅ [项目说明书（项目级 L1）](../../docs/architecture/project-manual.md)
- 🟡 P0 `overview/agent-dh-what-is.md` —— agent-dh 是什么：profile / 插件树 / 目录地图 / 运行形态（素材：CLAUDE.md）
- 🟡 P0 `overview/glossary.md` —— agent-dh 术语表（profile、插件、工具、基因组、reqboard、页面插件…）

### 卷 1 · 技术要求规范（Engineering Standards，**强制**）

> **性质**：本卷是**规范**（normative）不是介绍。它们来自宪法/CLAUDE.md/门禁脚本与实盘事故，
> 违反的后果是**代码审查拒绝、门禁失败或线上静默失效**。每页必须写清"依据是什么、怎么自检"。
> 改任何代码之前先读完本卷的相关页。

- 🟡 **P0** `standards/tool-development.md` —— 工具开发规范：`defineTool` + Service 模式；
  **schema 铁律**（每个 `type: 'object'` 节点显式 `additionalProperties`；必填只用 `required: true`；
  只允许 type/properties/additionalProperties+注解键；违反 → DSH 启动即崩）；
  返回结构/错误码（`code` + 消息自带 code 文本）；**诚实失败**（禁止静默兜底把"没生效"伪装成"在工作"）；
  写完跑 `npx vitest run tests/plugin-schema.smoke.test.ts`
- 🟡 **P0** `standards/build-and-release.md` —— 构建与发版：**`pnpm build` 不是部署、`pnpm install` 更不是**；
  多数包从 `dist/` 加载（只有 evolver/learning/core-tool/agent-os-manager/quantsys-v2-manager/solve-kit 走 src）；
  `scripts/relink-profile.py`（硬链接断链 = 静默停在旧版本）；`scripts/restart-with-build.sh`；
  :13080 由 launchd 托管（禁 `kill`，只能 `kickstart -k`）；构建后**校验产物**（文件在 + 关键符号 grep 命中）
- 🟡 **P0** `standards/testing.md` —— 测试与门禁：单测（vitest）+ schema 冒烟；
  **字段假设必须用真实数据核实**；**故障注入**（只测成功路径等于没测）；
  **源码级绿灯 ≠ 线上生效**（必须取线上证据：工具能绑定/接口返回/页面渲染）
- 🟡 **P0** `standards/coding.md` —— 编码与协作：TS 约定、命名（kebab-case / `NNN-title.md`）、
  文件放置（文档决策树）、注释写"为什么"（事故与取舍）；**worktree 隔离**（不在共享主工作区做 feature 提交、
  不覆盖他人脏改动）；提交信息格式
- 🟡 **P0** `standards/data-and-degradation.md` —— 数据规范：派生数据登记进
  `quantsys-v2/config/data_contracts.json`；**新鲜度必须先校验**（跨源交叉验证/窗口一致性/与账户事实对照）；
  降级必须显式标注、禁止冒充实时；引用数据标注**来源 + 时点**（R-013）
- 🟡 **P1** `standards/account-and-trading.md` —— 账户与交易纪律：账户边界（`agents.json` 单一事实源，
  账户名不得硬编码）；下单前 R-001/R-002（价格/可卖/额度/止损）；`reason` 必填（规则 ID + 理由）；
  regime 仓位映射与三重钳制（R-006）
- 🟡 **P1** `standards/audit-and-docs.md` —— 留痕与文档规范：`decision_audit` / `memory_write` /
  `board_post` 分档（什么该写哪里、什么不要写）；文档放置决策树；wiki 页面模型；
  归档合并矩阵（不同需求类型去哪、不许自创目录）
- 🟡 **P1** `standards/plugin-and-pages.md` —— 插件与页面插件规范：Service/`inject`/Config；
  页面插件 host 半（tsx 直载，改完重启）与 client 半（tsdown 打包 `lib/`，刷新即生效）的分工与产物校验；
  样式复用全站令牌（不造第二套按钮/色板）
- 🟡 **P2** `standards/security-and-boundaries.md` —— 边界与安全：多实例停止铁律（禁模糊 `pkill`、
  必带 `-sTCP:LISTEN`）；只读账户不得写入；沙箱与权限降级路径必须显式

### 卷 2 · 架构与生命周期

- 🟡 P0 `architecture/plugin-model.md` —— 插件模型与装载：cordis、service/inject、schema 铁律、页面插件 host/client 两半
- ✅ [自修复重启行为](architecture/self-restart-behavior.md)
- ✅ [某些包为何没有 dist](architecture/WHY-NO-DIST.md)
- ✅ [工具清单](architecture/TOOLS_INVENTORY.md)
- 🟡 P1 `architecture/profile-and-dsh-home.md` —— profile / DSH_HOME / 软链与发版（relink-profile、dist 陈旧陷阱）
- 🟡 P1 `architecture/identity-and-agents-json.md` —— 身份系统：agents.json、窗口编码、多实例边界

### 卷 3 · 工具与协议

- ✅ [工具清单](architecture/TOOLS_INVENTORY.md)
- 🟡 P0 `protocols/tool-contract.md` —— 工具契约：defineTool、schema 铁律、返回结构、错误码、降级与"诚实失败"
- 🟡 P1 `protocols/tool-audit.md` —— 工具审计清单：声明与实现是否一致、默认账户值、dry_run 真假
- ✅ [交易执行协议](protocols/trade-execution-protocol.md)

### 卷 4 · 账户与交易

- 🟡 P0 `architecture/accounts-and-boundaries.md` —— 账户模型与边界（agent_brain 自营 / agent_virtual 只读 / 策略线账户）
- 🟡 P0 `guides/trading-constraints.md` —— 交易约束速查：T+1、100 股整数倍、仓位/行业/现金上限、止损档位
- ✅ [下单 API 指南](guides/order-api-guide.md)

### 卷 5 · 数据与后端

- 🟡 P0 `architecture/data-contracts-and-freshness.md` —— 数据契约、新鲜度与降级（R-020、静默失效的教训）
- ✅ [quantsys-v2 能力评估](guides/quantsys-v2-capability-assessment.md)
- ✅ [事件查询最佳实践](guides/event-query-best-practices.md)
- ✅ [数据库表对照](architecture/database-table-comparison.md)

### 卷 6 · 自主能力（基因组 / 记忆 / 学习 / 进化）

- ✅ [自主能力总览](architecture/AUTONOMY-SYSTEM.md)
- ✅ [RFC-005 自进化 Agent](rfcs/005-self-evolving-agent.md)
- ✅ [RFC-006 基因组分段](rfcs/006-prompt-genome-sections.md)
- ✅ [RFC-007 基因组管理](rfcs/007-genome-manager.md)
- ✅ [RFC-008 验证门](rfcs/008-validation-gate.md)
- ✅ [RFC-003 学习蒸馏](rfcs/003-self-learning-distillation.md)
- 🟡 P1 `architecture/memory-and-recall.md` —— 记忆写入/召回与注入率（含 R-008 决策前检索）

### 卷 7 · 页面插件（GUI）

- ✅ [看板实现细节](design/dashboard-implementation-detail.md)
- ✅ [RFC-011 工具 Web 卡片](rfcs/011-tool-web-cards.md)
- ✅ [RFC-013 公告板页面](rfcs/013-bulletin-board-page.md)
- 🟡 P1 `architecture/page-plugin-contract.md` —— 页面插件契约：host/client 两半、打包与刷新时机、全站样式令牌

### 卷 8 · 需求流水线与归档（本 wiki 的供料线）

- ✅ [RFC 014 需求看板](rfcs/014-requirement-board.md)
- ✅ [需求归档规范](architecture/requirement-archive.md)
- ✅ [需求归档索引](requirements/INDEX.md)
- 🟡 P0 `guides/reqboard-workflow.md` —— 从立项到归档的实操（含计划模式、验收人工审核、归档材料怎么备）

### 卷 9 · 运维与排障

- ✅ [自修复重启行为](architecture/self-restart-behavior.md)
- ✅ [启动](guides/STARTUP.md) · [速查](guides/QUICKREF.md) · [使用指南](guides/USAGE-GUIDE.md)
- ✅ [重启与会话安全](guides/restart-session-safety.md) · [技能装载](guides/skill-loading.md)
- 🟡 P0 `guides/troubleshooting.md` —— 故障排查手册（缺陷类归档的既定落点）
- 🟡 P1 `guides/routine-checks.md` —— 定时巡检清单（数据卫生探针、wiki 探针、调度看门狗…）

### 卷 10 · 附录（L3 证据层）

- ✅ [需求档案索引](requirements/INDEX.md) · [归档规范](architecture/requirement-archive.md)
- ✅ [历史遗留系统下线计划](architecture/legacy-system-deprecation-plan.md)
- ✅ [agent-ts 经验](guides/learnings-from-agent-ts.md)
- L3 正文是各需求目录与 `work-logs/`（只读证据，不在此逐条登记）

## 最近改动

| 日期 | 页面 | 变更 | 来源 |
|---|---|---|---|
| 2026-09-13 | 本页 | 建立 agent-dh wiki 首页与大纲（9 卷） | w-1cee2467 |
| 2026-09-13 | 本页 | 补 **卷 1 技术要求规范（强制）**，大纲扩为 10 卷并重编号 | w-1cee2467 |

## 怎么维护

- 页面模型、front-matter 字段、stub 约定见 [文档规范](../../docs/DOCUMENT-MANAGEMENT-PLAN.md)；
- 新页面写完后：① 挂进本页对应卷；② 在本页「最近改动」加一行；③ 跑
  `python3 agent-dh/scripts/wiki_probe.py` 确认无死链/孤儿页；
- **写页的时机是归档**：需求完成归档时把结论合并进对应卷的页面（归档闸门会校验"说明书更新点"），
  所以这个 wiki 是**长出来的**，不是一次性写完的。
