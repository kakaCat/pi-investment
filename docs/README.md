---
id: home
title: PI Investment Wiki（文档首页）
type: manual
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [wiki, index, home]
---

# PI Investment Wiki

> **怎么用这个 wiki**：想理解项目 → 先读 [项目说明书](architecture/project-manual.md)（L1）；
> 找某个主题的细节 → 用下面的**按类型页面索引**（L2）；只有追溯"当时为什么这么做"才下沉到
> 需求档案与工作日志（L3）。每一页都能独立读懂，并且链接回与它相关的页。

## 从哪开始

- [项目说明书](architecture/project-manual.md) —— 项目是什么 / 三层架构 / 术语表 / 怎么跑 / 去哪找细节
- [文档规范与 Wiki 约定](DOCUMENT-MANAGEMENT-PLAN.md) —— 页面模型、命名、归档与金字塔
- [系统架构总览](architecture/system-overview.md) —— 三层架构的细节
- [需求看板 RFC 014](../agent-dh/docs/rfcs/014-requirement-board.md) —— 需求流水线（立项→头脑风暴→写计划→拆分→执行→验收→完成→归档）

## 页面索引（按类型）

### 架构 architecture/

- [系统架构总览](architecture/system-overview.md)
- [通知网关设计](architecture/notification-gateway.md)
- [项目说明书](architecture/project-manual.md)
- [自主盈利引擎架构](architecture/profit-engine-autonomy-architecture.md)
- [信号分级](architecture/signal-grading.md)
- [策略状态语义](architecture/strategy-status-semantics.md)

### 决策 adr/

- [ADR-001: Agent OS 网关](adr/001-agent-os-gateway.md)
- [ADR-001: 六边形架构](adr/001-hexagonal-architecture.md)
- [ADR-002: 调度器归属拆分](adr/002-scheduler-ownership-split.md)

### 指南 guides/

- [通知系统迁移](guides/notification-migration.md)
- [监控部署](guides/monitoring-deployment.md)

### 提案 rfcs/

- [RFC-001: Agent 模板系统](rfcs/001-agent-template-system.md)
- [RFC-006: 回测有效性与策略验证](rfcs/006-backtest-validity-and-strategy-validation.md)
- [RFC-014: 需求看板](../agent-dh/docs/rfcs/014-requirement-board.md)

### 需求档案（L3，只读证据层）

- [需求归档索引](../agent-dh/docs/requirements/INDEX.md)
- [需求归档规范](../agent-dh/docs/architecture/requirement-archive.md)

### 子项目文档

- [agent-dh 文档](../agent-dh/CLAUDE.md)
- [agent-ts 文档](../agent-ts/CLAUDE.md)
- [quantsys-v2 文档](../quantsys-v2/CLAUDE.md)

## 最近改动（新知识从这里进来）

| 日期 | 页面 | 变更 | 来源 |
|---|---|---|---|
| 2026-09-13 | [项目说明书](architecture/project-manual.md) | 新建（金字塔 L1） | w-1cee2467 |
| 2026-09-13 | [文档规范](DOCUMENT-MANAGEMENT-PLAN.md) | 增「Wiki 化：页面模型」「文档金字塔」「需求归档」三节 | w-1cee2467 |
| 2026-09-13 | [需求归档规范](../agent-dh/docs/architecture/requirement-archive.md) | 归档=存底+合并；合并去向收敛到规范目录；说明书更新点强制 | w-1cee2467 |

## 待写页（stub，后续需求的候选）

> 这些主题已被反复引用但还没有独立页面。写需求时优先补它们（页面模型见文档规范）。

- `architecture/agent-ts-architecture.md` —— AI 员工的内部结构（当前散在 agent-ts/CLAUDE.md）
- `architecture/quantsys-v2-architecture.md` —— 后端分层与数据流
- `guides/troubleshooting.md` —— 故障排查手册（缺陷类归档的合并去向）
- `architecture/dsh-plugin-model.md` —— DSH profile / 插件 / 工具装载模型
- `game-theory-framework.md` —— 博弈框架（根 CLAUDE.md 已引用，实体缺失）
- `agent-autonomy.md` —— 自主运行机制（同上）

## Wiki 约定（机器也在检查）

- 每页开头有 front-matter：`id / title / type / status / updated / owners / tags`；
  `status` 取值：`living`（持续维护）/ `stub`（待写）/ `frozen`（冻结）/ `archived`（归档）；
- 页尾写「相关页面」把自己挂回页面图里；每个论断尽量给代码或下层文档的指针；
- 巡检（死链 / 孤儿页 / 待写页 / 缺 front-matter）：
  `python3 agent-dh/scripts/wiki_probe.py`（退出码 1 = wiki 页有问题）。
