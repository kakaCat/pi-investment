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
