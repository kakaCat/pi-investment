# 文档管理规范与整理计划

## 当前问题

根目录有 **33 个 MD 文档**，类型混杂，包括：
- 设计文档（DESIGN）
- 实施报告（REPORT/SUMMARY/COMPLETION）
- 架构决策（ARCHITECTURE/DECISION）
- 迁移指南（MIGRATION/GUIDE）
- 工作计划（PLAN）
- 验收报告（ACCEPTANCE）

这些文档都被 `.gitignore` 排除，导致：
1. ❌ 根目录混乱，难以导航
2. ❌ 无法版本控制重要的技术决策
3. ❌ 新成员难以理解项目演进历史
4. ❌ 文档重复命名（多个 PHASE/WP/BATCH 文档）

## 新的文档组织结构

```
pi-investment/
├── README.md                    # 项目入口（保留）
├── CLAUDE.md                    # AI 助手指令（保留）
│
├── docs/
│   ├── README.md               # 文档索引
│   │
│   ├── architecture/           # 架构设计
│   │   ├── system-overview.md
│   │   ├── gateway-decision.md
│   │   ├── agent-integration.md
│   │   └── notification-system.md
│   │
│   ├── guides/                 # 使用指南
│   │   ├── migration-guide.md
│   │   ├── deployment.md
│   │   └── troubleshooting.md
│   │
│   ├── adr/                    # Architecture Decision Records
│   │   ├── 001-notification-gateway.md
│   │   ├── 002-agent-os-positioning.md
│   │   └── 003-memory-provider-port.md
│   │
│   ├── work-logs/              # 工作记录（归档用，gitignore）
│   │   ├── 2026-08/
│   │   │   ├── wp-4-completion.md
│   │   │   ├── phase-4-report.md
│   │   │   └── batch-3-summary.md
│   │   └── archive/
│   │
│   ├── rfcs/                   # Request for Comments（重大特性设计）
│   │   ├── 001-unified-notification.md
│   │   └── 002-agent-template-system.md
│   │
│   └── superpowers/            # OpenClaw 相关（已有）
│       ├── specs/
│       ├── plans/
│       └── implementation/
│
├── agent-ts/
│   └── docs/                   # agent-ts 专属文档
│
└── quantsys-v2/
    └── docs/                   # quantsys-v2 专属文档
```

## 文档分类规则

### 1. Architecture (架构文档) - 纳入版本控制
**何时放这里**：
- 系统整体架构设计
- 重大技术决策及理由
- 组件交互关系图
- 长期有效的设计文档

**示例**：
- `system-overview.md` - 三层架构总览
- `gateway-architecture.md` - 网关层设计
- `agent-integration.md` - Agent 对接方式

**命名规范**：`<topic>-<type>.md`（kebab-case）

### 2. ADR (Architecture Decision Records) - 纳入版本控制
**何时放这里**：
- 重要技术选型决策
- 架构风格变更
- 重大重构决定

**格式**：
```markdown
# ADR-001: 统一通知网关

Date: 2026-08-14
Status: Accepted

## Context
当前多个通知渠道分散...

## Decision
建立统一的通知网关...

## Consequences
优点：...
缺点：...
```

**命名规范**：`NNN-short-title.md`（数字编号）

### 3. RFCs (Request for Comments) - 纳入版本控制
**何时放这里**：
- 新特性设计提案（实施前）
- 需要团队讨论的技术方案
- 实验性功能设计

**格式**：包含 Goals / Non-Goals / Design / Alternatives

**命名规范**：`NNN-feature-name.md`

### 4. Work Logs (工作日志) - .gitignore
**何时放这里**：
- 每个工作包的完成报告
- Phase/Batch/Sprint 总结
- 临时分析文档
- 执行过程记录

**目录结构**：按月归档
```
work-logs/
├── 2026-08/
│   ├── wp-4-completion.md
│   ├── phase-4-report.md
│   └── batch-3-summary.md
└── 2026-07/
    └── ...
```

**命名规范**：`<project>-<type>.md`

### 5. Guides (使用指南) - 纳入版本控制
**何时放这里**：
- 部署指南
- 迁移指南
- 故障排查手册
- 开发流程说明

**更新频率**：随功能演进更新

### 6. 根目录保留文件
只保留两个：
- `README.md` - 项目入口、快速开始
- `CLAUDE.md` - AI 助手指令

## 迁移计划

### Phase 1: 创建新结构（立即）
```bash
mkdir -p docs/{architecture,guides,adr,work-logs/2026-08,rfcs}
```

### Phase 2: 整理现有文档（按优先级）

**P0 - 架构文档（纳入版本控制）**
```bash
# 移动并重命名
GATEWAY-ARCHITECTURE-DECISION.md        → docs/adr/001-agent-os-gateway.md
SYSTEM-ARCHITECTURE-DIAGRAM.md          → docs/architecture/system-overview.md
NOTIFICATION-SYSTEM-DESIGN.md           → docs/architecture/notification-gateway.md
AGENT-INTEGRATION-ANALYSIS.md           → docs/architecture/agent-integration.md
MIGRATION-GUIDE.md                      → docs/guides/notification-migration.md
```

**P1 - 工作日志（gitignore，归档）**
```bash
# 移动到 work-logs/2026-08/
PHASE-*.md                              → docs/work-logs/2026-08/
WP-*.md                                 → docs/work-logs/2026-08/
BATCH-*.md                              → docs/work-logs/2026-08/
*-REPORT.md                             → docs/work-logs/2026-08/
*-SUMMARY.md                            → docs/work-logs/2026-08/
W1.*.md                                 → docs/work-logs/2026-08/
A0-*.md                                 → docs/work-logs/2026-08/
P1-*.md                                 → docs/work-logs/2026-08/
```

**P2 - 设计提案（转为 RFC 或归档）**
```bash
# 如果是未来仍需参考的设计
AGENT-TEMPLATE-INTEGRATION.md           → docs/rfcs/001-agent-template-system.md
FEISHU-UX-DESIGN.md                     → docs/rfcs/002-feishu-integration.md

# 如果是已完成的，移到 work-logs
FEISHU-INTEGRATION-RESEARCH.md          → docs/work-logs/2026-08/
FEISHU-NOTIFICATION-IMPLEMENTATION-PLAN.md → docs/work-logs/2026-08/
```

**P3 - 清理重复/过时文档**
```bash
# 合并相似主题的文档
AGENT-PERSPECTIVE-DESIGN-REVIEW.md \
AGENT-INTERACTION-PATTERNS.md      } → 合并到 docs/architecture/agent-design.md

# 删除过时的
OLD-CODE-MIGRATION-PLAN.md             → 已完成可删除
PR-READY.md                            → 已合并可删除
DELIVERY-SUMMARY.md                    → 归档到 work-logs
```

### Phase 3: 更新 .gitignore
```gitignore
# 工作日志不纳入版本控制
docs/work-logs/

# 根目录临时文档
/*.md
!README.md
!CLAUDE.md
```

### Phase 4: 创建文档索引
创建 `docs/README.md`：
```markdown
# PI Investment 文档中心

## 架构设计
- [系统架构总览](architecture/system-overview.md)
- [通知网关设计](architecture/notification-gateway.md)
- [Agent 集成方案](architecture/agent-integration.md)

## 架构决策记录 (ADR)
- [ADR-001: Agent OS 定位与网关架构](adr/001-agent-os-gateway.md)
- [ADR-002: 统一通知系统](adr/002-notification-gateway.md)

## 使用指南
- [部署指南](guides/deployment.md)
- [通知系统迁移指南](guides/notification-migration.md)

## RFC (设计提案)
- [RFC-001: Agent 模板系统](rfcs/001-agent-template-system.md)

## 项目文档
- [agent-ts 文档](../agent-ts/docs/)
- [quantsys-v2 文档](../quantsys-v2/docs/)
```

---

---

---

## Wiki 化：页面模型（2026-09-13 新增）

文档不是"一堆文件"，而是**一个 wiki**：页面是节点，链接是边，front-matter 让机器能索引。
金字塔（L1 说明书 / L2 领域篇 / L3 档案）说的是**认知的高度**；wiki 说的是**页面之间怎么连**——
两者一起用：向上提炼认知，横向互相链接。

**页面 = front-matter + 正文 + 相关页面**

```markdown
---
id: requirement-archive           # 全仓唯一，kebab-case（链接与检索用）
title: 需求归档规范
type: manual | architecture | guide | adr | rfc | research | archive
status: living | stub | frozen | archived
updated: 2026-09-13
owners: [w-1cee2467]
tags: [archive, reqboard]
---

# 标题（与人读到的第一句一致）
…正文…

## 相关页面
- [项目说明书](project-manual.md)
- [RFC 014 需求看板](../../../agent-dh/docs/rfcs/014-requirement-board.md)
```

**规则**

1. **一个概念一页**：同主题归并到一页，别开"XX（二）"；页面太长（约 >300 行）才拆分并互相链接；
2. **每页必有 front-matter**：`id / title / type / status / updated`（缺了机器索引不到 = 等于没写），
   `owners / tags` 可选但推荐；
3. **status 就是待办**：`stub` = 占位页（已被引用但还没写），它是**后续需求的候选**——
   首页「待写页」区列出它们，立项时优先补；
4. **双向可达**：新页必须从首页或上层页链到（否则是孤儿页）；页尾写「相关页面」把自己挂回页面图；
5. **链接用相对路径**（同目录可简写），不要绝对路径；
6. **巡检而不是靠自觉**：`python3 agent-dh/scripts/wiki_probe.py` 检查死链 / 孤儿页 / 待写页 /
   front-matter 缺失，退出码 1 = 有问题（可挂定时任务）。历史页面（无 front-matter）只计数、不计失败，
   迁一个是一个。

**与归档的关系**：归档时除了写 L3 档案与合并进 L2，还要**把新知识挂进页面图**——
新建页面 → 在首页/上层页登记；改了哪一页 → 在说明书「最近更新」与首页「最近改动」留一行；
被引用但还没写的主题 → 在首页「待写页」登记为 `stub` 候选。

## 文档金字塔与项目说明书（2026-09-13 新增）

文档不是平铺的目录，而是**金字塔**——越往上越少、越稳定、越常被读：

| 层 | 内容 | 放哪 | 谁读 |
|---|---|---|---|
| **L0 入口** | 一行指引：去哪儿找认知 | `CLAUDE.md`（根 / 子项目） | agent 每次启动 |
| **L1 说明书** | 项目是什么 / 三层架构 / 术语表 / 怎么跑 / 指针 / 最近更新 | `docs/architecture/project-manual.md` + `docs/README.md`（导航） | 人：新人；agent：接手任何任务之前 |
| **L2 领域篇** | 一个主题一篇：架构、指南、决策(ADR)、提案(RFC)、研究 | `architecture/`、`guides/`、`adr/`、`rfcs/`、`strategy-research/` | 做具体事情时按需读 |
| **L3 证据档案** | 需求档案（requirement/plan/verification/retro）、工作日志 | `requirements/REQ-xxxxxx/`、`work-logs/YYYY-MM/` | 只用于追溯"当时为什么" |

**生长规则（归档时执行，代码校验）**：

1. 每次归档 → **必写 L3**（需求档案）+ **至少一篇 L2**（把结论合并进既有领域文档）；
2. 改变项目级认知的需求（feature / refactor / spike）→ **必须申报 L1/L2 的更新点**
   （`manual_updates`：哪一份文档、哪一节、多了什么认知）；代码会拒绝没有更新点的这类归档；
3. L1 每次变更 → 在说明书「最近更新」表追加一行（日期 / 更新点 / 来源 REQ）；
4. 不改变项目认知的类型（bug / doc / chore）→ 材料里写 `manual_note` 说明"无认知变化"即可。

**读法（省 context）**：L1 能独立读懂；要细节才下钻 L2；只有追溯历史才碰 L3。
**反模式**：把 L3 细节抄进 L1（说明书变流水账）；结论只留在 L3（项目认知长不上去）；
新文档建了不挂进 L1/L2 索引（等于没写）。

## 需求归档（reqboard，2026-09-13 新增）

需求（REQ）是工作的最小闭环单位。**归档 = 存底 + 合并**，两条同时成立才算归档：

1. **存底（档案）**：`docs/requirements/REQ-xxxxxx/`（或子项目 `agent-dh/docs/requirements/REQ-xxxxxx/`）保留
   `requirement.md / plan.md / verification.md / retro.md / notes.md`——
   回答"当时为什么这么做"，**纳入版本控制**（它是"为什么"的唯一证据链）。
2. **合并（知识）**：把结论并进**本规范既有目录**（不新增目录），并写一条索引：
   - 索引：`agent-dh/docs/requirements/INDEX.md`（REQ id | 一句话结论 | 类型 | 日期 | 目录 | 合并去向）；
   - 合并去向按需求类型：
     功能→`architecture/`|`guides/`；缺陷→`guides/`（故障排查）|`architecture/`（机制性根因）；
     文档→`docs/` 对应子目录；重构→`adr/`|`architecture/`；调研→`rfcs/`|`architecture/`|`strategy-research/`；
     杂项→`work-logs/YYYY-MM/`。
   - **注意**：`work-logs/` 不纳入版本控制 → 耐久结论（架构/决策/排障）绝不允许只落在那里。

**铁律：归档不许自创平行目录**（`known-issues/`、`research/`、`archive/` 之类）。
要新增一类目录 = 先改本规范 + `docs/README.md`，再改 reqboard 的 `ARCHIVE_DOC_RULES`——
代码会拒绝落在规范外的合并去向（`REQBOARD_INVALID_INPUT`），不是提示词约定。

**流程**：窗口 `reqboard_archive_submit`（备材料：目录 + 文档清单 + 合并去向 + 索引条目）
→ 人在看板点「归档」→ 需求进 `archived`（写 archivePath 与时间线）。
**只登记不合并 = 没归档**：材料里写了的去向必须真的改到位。

细则与合并矩阵：`agent-dh/docs/architecture/requirement-archive.md`

## 新文档创建规范

### 何时创建文档？
1. **架构设计** - 设计新组件前先写 ADR
2. **重大特性** - 实施前写 RFC 征求意见
3. **工作完成** - 完成后写 work-log 记录过程
4. **发现问题** - 发现通用问题写 troubleshooting

### 文档放哪里？
```
决策树：

这是技术决策吗？
├─ 是 → docs/adr/NNN-title.md
└─ 否 ↓

这是新特性设计吗？
├─ 是 → docs/rfcs/NNN-title.md
└─ 否 ↓

这是架构说明吗？
├─ 是 → docs/architecture/topic.md
└─ 否 ↓

这是使用指南吗？
├─ 是 → docs/guides/topic.md
└─ 否 ↓

这是工作记录吗？
└─ 是 → docs/work-logs/YYYY-MM/title.md
```

### 文档模板

**Architecture 模板**：
```markdown
# <Component> Architecture

## Overview
简述组件职责和位置

## Design Goals
设计目标

## Components
关键组件说明

## Interaction
组件交互图

## Implementation Notes
实现要点
```

**ADR 模板**：
```markdown
# ADR-NNN: <Title>

Date: YYYY-MM-DD
Status: Proposed | Accepted | Deprecated

## Context
背景和问题

## Decision
决策内容

## Consequences
影响和权衡
```

**Work Log 模板**：
```markdown
# <Project> - <Type>

Date: YYYY-MM-DD
Author: <Name>

## Objectives
目标

## What Was Done
完成的工作

## Challenges & Solutions
遇到的问题和解决方案

## Next Steps
后续工作
```

## 执行计划

### 立即执行（10分钟）
```bash
# 1. 创建新目录结构
mkdir -p docs/{architecture,guides,adr,work-logs/2026-08,rfcs}

# 2. 移动 P0 架构文档
mv GATEWAY-ARCHITECTURE-DECISION.md docs/adr/001-agent-os-gateway.md
mv SYSTEM-ARCHITECTURE-DIAGRAM.md docs/architecture/system-overview.md
mv NOTIFICATION-SYSTEM-DESIGN.md docs/architecture/notification-gateway.md

# 3. 创建文档索引
touch docs/README.md
```

### 本周内完成（2小时）
- 整理所有 work-logs
- 合并重复文档
- 创建完整的 docs/README.md 索引

### 长期维护
- 每次架构变更 → 更新 architecture/
- 每次重大决策 → 新建 ADR
- 每个工作包完成 → work-logs 记录
- 每月归档 → work-logs/YYYY-MM/

## 预期效果

**Before**：
```
pi-investment/
├── AGENT-INTEGRATION-ANALYSIS.md
├── AGENT-INTERACTION-PATTERNS.md
├── AGENT-PERSPECTIVE-DESIGN-REVIEW.md
├── AGENT-TEMPLATE-INTEGRATION.md
├── ARCHITECTURE-SUMMARY.md
... (30+ files)
```

**After**：
```
pi-investment/
├── README.md
├── CLAUDE.md
├── docs/
│   ├── README.md (索引)
│   ├── architecture/ (5个核心架构文档)
│   ├── adr/ (3个重大决策)
│   ├── guides/ (2个使用指南)
│   └── work-logs/ (历史归档，gitignore)
```

## 收益

✅ **根目录清爽** - 只保留 2 个 MD 文件  
✅ **架构可追溯** - ADR 记录每个重大决策  
✅ **新人友好** - 清晰的文档索引  
✅ **历史归档** - work-logs 保留执行记录但不污染版本控制  
✅ **便于维护** - 明确的分类规则，新文档知道往哪放  
