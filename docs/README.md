# PI Investment 文档中心

欢迎来到 PI Investment 文档中心。本目录包含系统架构、技术决策和使用指南。

## 📖 快速导航

### 🏗️ 架构设计 ([architecture/](architecture/))

核心架构文档，描述系统整体设计和关键组件：

- [系统架构总览](architecture/system-overview.md) - Agent OS 三层架构、定位与职责
- [通知网关设计](architecture/notification-gateway.md) - 统一通知系统架构（参考 OpenClaw）
- [Agent 集成方案](architecture/agent-integration.md) - quantsys-v2 与 agent-ts 对接分析

### 📝 架构决策记录 ([adr/](adr/))

重大技术决策及理由（ADR - Architecture Decision Records）：

- [ADR-001: Agent OS 定位与网关架构](adr/001-agent-os-gateway.md) - 为什么选择网关架构？

### 📚 使用指南 ([guides/](guides/))

开发、部署和运维指南：

- [通知系统迁移指南](guides/notification-migration.md) - 如何从旧通知系统迁移到新网关

### 💡 RFC - 设计提案 ([rfcs/](rfcs/))

新特性设计提案（实施前讨论）：

- [RFC-001: Agent 模板系统](rfcs/001-agent-template-system.md) - Agent × 通知模板系统业务场景设计

### 📦 工作日志 ([work-logs/](work-logs/))

项目执行过程记录（按月归档，不纳入版本控制）：

- [2026-08/](work-logs/2026-08/) - 8月工作记录：Phase 4、WP-4、Batch 3 等

### 🦸 Superpowers ([superpowers/](superpowers/))

OpenClaw 相关文档：

- [specs/](superpowers/specs/) - 功能规格说明
- [plans/](superpowers/plans/) - 执行计划
- [implementation/](superpowers/implementation/) - 实施记录

---

## 📁 文档分类规则

### 何时创建文档？

| 场景 | 文档类型 | 位置 | 示例 |
|------|---------|------|------|
| 重大技术决策 | ADR | `adr/NNN-title.md` | 选择网关架构 |
| 新特性设计提案 | RFC | `rfcs/NNN-title.md` | Agent 模板系统 |
| 架构说明 | Architecture | `architecture/topic.md` | 通知网关设计 |
| 使用指南 | Guide | `guides/topic.md` | 部署指南 |
| 工作完成记录 | Work Log | `work-logs/YYYY-MM/` | Phase 4 完成报告 |

### 版本控制策略

- ✅ **纳入版本控制**：`architecture/`, `adr/`, `rfcs/`, `guides/`
- ❌ **不纳入版本控制**：`work-logs/`（归档用，避免污染 git 历史）

---

## 🔗 相关文档

- [agent-ts 文档](../agent-ts/CLAUDE.md) - Agent 模块专属文档
- [quantsys-v2 文档](../quantsys-v2/CLAUDE.md) - 后端服务专属文档
- [web-frontend 文档](../web-frontend/) - 前端监控面板文档

---

## 📋 文档模板

创建新文档时，请参考以下模板：

### ADR 模板
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

### Architecture 模板
```markdown
# <Component> Architecture

## Overview
组件概述

## Design Goals
设计目标

## Components
关键组件

## Interaction
交互方式
```

### Work Log 模板
```markdown
# <Project> - <Type>

Date: YYYY-MM-DD

## Objectives
目标

## What Was Done
完成的工作

## Challenges & Solutions
问题与解决方案
```

---

## 📞 联系与贡献

- 文档问题？请在项目 Issue 中反馈
- 文档改进？欢迎提交 Pull Request

**文档管理规范**：详见 [DOCUMENT-MANAGEMENT-PLAN.md](DOCUMENT-MANAGEMENT-PLAN.md)
