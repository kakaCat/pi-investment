---
id: architecture-refactor-plan
title: Agent-DH 工具重构总计划
summary: 2026-08-28 的工具重构总计划（只落地 Phase 1 trading）；现行工具架构以工具开发规范为准。
type: architecture
status: frozen
updated: 2026-09-13
owners: [agent-dh]
tags: [architecture]
---

# Agent-DH 工具重构总计划

> **状态：frozen（2026-09-14 标注，不再推进）**：本文是 2026-08-28 的工具重构总计划，只完成了 Phase 1（trading）。
> 之后的工具架构以 [工具开发规范](../standards/tool-development.md)（三段式 / BaseTool）与 [core-tool 规范包](../../packages/core-tool/README.md) 为准；本文作为当时的决策依据保留。


**日期**: 2026-08-28  
**状态**: Phase 1 完成，Phase 2-4 待执行

## 目标

将所有 agent-dh packages 中的工具重构为 BaseTool 三阶段架构，实现：
- ✅ 统一的工具模式
- ✅ 类型安全和可测试性
- ✅ 清晰的职责分离
- ✅ 标准化的错误处理

## 重构范围

### ✅ Phase 1: Trading Package（已完成）

**Package**: `packages/trading`  
**状态**: ✅ 完成  
**工具数**: 8/8  
**完成日期**: 2026-08-28

| 工具 | 状态 | 复杂度 | 文件结构 |
|------|------|--------|----------|
| AccountInfoTool | ✅ | 简单 | index.ts |
| PositionListTool | ✅ | 简单 | index.ts |
| PortfolioTradeTool | ✅ | 复杂 | XxxTool.ts |
| TradeMonitorTool | ✅ | 简单 | index.ts |
| AlgoExecuteTool | ✅ | 简单 | index.ts |
| TradeVerifyTool | ✅ | 简单 | index.ts |
| SlippageReportTool | ✅ | 简单 | index.ts |
| M4CircuitBreakerTool | ✅ | 复杂 | XxxTool.ts |

**成果**:
- index.ts 从 554 行缩减到 92 行（83% 缩减）
- 12/12 测试通过
- 完整的重构文档（REFACTOR_GUIDE.md）

---

### 🔄 Phase 2: 核心业务 Packages（优先级 P0）

#### 2.1 Investment Package
**Package**: `packages/investment`  
**工具数**: ~9  
**优先级**: P0（核心投资决策工具）  
**估计时间**: 2-3 天

**工具列表**:
- pool_manage（股票池管理）
- pool_validate（股票池验证）
- signal_scan（信号扫描）
- position_adjust（仓位调整）
- risk_check（风险检查）
- performance_review（业绩回顾）
- 其他...

#### 2.2 Strategy Package
**Package**: `packages/strategy`  
**工具数**: ~8  
**优先级**: P0（策略管理）  
**估计时间**: 2 天

**工具列表**:
- strategy_list（策略列表）
- strategy_detail（策略详情）
- strategy_backtest（回测）
- strategy_optimize（优化）
- 其他...

#### 2.3 Market Package
**Package**: `packages/market`  
**工具数**: ~7  
**优先级**: P0（市场数据）  
**估计时间**: 1-2 天

**工具列表**:
- market_quote（行情）
- market_kline（K线）
- market_depth（深度）
- market_news（新闻）
- 其他...

#### 2.4 Risk Package
**Package**: `packages/risk`  
**工具数**: ~5  
**优先级**: P0（风险管理）  
**估计时间**: 1 天

---

### 🔄 Phase 3: 智能增强 Packages（优先级 P1）

#### 3.1 Lifecycle Package
**Package**: `packages/lifecycle`  
**工具数**: ~16  
**优先级**: P1（生命周期管理）  
**估计时间**: 3-4 天

**特点**: 工具数量最多，涉及自修复、窗口管理、状态管理等复杂逻辑

#### 3.2 Learning Package
**Package**: `packages/learning`  
**工具数**: ~9  
**优先级**: P1（学习系统）  
**估计时间**: 2 天

#### 3.3 Intelligence Package
**Package**: `packages/intelligence`  
**工具数**: ~5  
**优先级**: P1（博弈智能）  
**估计时间**: 1 天

#### 3.4 Evolution Package
**Package**: `packages/evolution`  
**工具数**: ~3  
**优先级**: P1（进化系统）  
**估计时间**: 1 天

#### 3.5 Evolver Package
**Package**: `packages/evolver`  
**工具数**: ~6  
**优先级**: P1（参数进化）  
**估计时间**: 1-2 天

#### 3.6 Genome Package
**Package**: `packages/genome`  
**工具数**: ~6  
**优先级**: P1（基因管理）  
**估计时间**: 1-2 天

---

### 🔄 Phase 4: 支撑系统 Packages（优先级 P2）

#### 4.1 Memory Package
**Package**: `packages/memory`  
**工具数**: ~4  
**优先级**: P2（记忆管理）  
**估计时间**: 1 天

#### 4.2 Factor Package
**Package**: `packages/factor`  
**工具数**: ~3  
**优先级**: P2（因子分析）  
**估计时间**: 1 天

#### 4.3 Data Manager Package
**Package**: `packages/data-manager`  
**工具数**: ~4  
**优先级**: P2（数据管理）  
**估计时间**: 1 天

#### 4.4 Quantsys-V2 Manager Package
**Package**: `packages/quantsys-v2-manager`  
**工具数**: ~4  
**优先级**: P2（后端管理）  
**估计时间**: 1 天

#### 4.5 Agent-OS Manager Package
**Package**: `packages/agent-os-manager`  
**工具数**: ~4  
**优先级**: P2（Agent OS 管理）  
**估计时间**: 1 天

#### 4.6 Window Manager Package
**Package**: `packages/window-manager`  
**工具数**: ~5  
**优先级**: P2（窗口管理）  
**估计时间**: 1 天

#### 4.7 Model Package
**Package**: `packages/model`  
**工具数**: ~4  
**优先级**: P2（模型管理）  
**估计时间**: 1 天

#### 4.8 Notification Package
**Package**: `packages/notification`  
**工具数**: ~4  
**优先级**: P2（通知系统）  
**估计时间**: 1 天

#### 4.9 Competition Package
**Package**: `packages/competition`  
**工具数**: ~4  
**优先级**: P2（竞争分析）  
**估计时间**: 1 天

#### 4.10 Scheduler Package
**Package**: `packages/scheduler`  
**工具数**: ~2  
**优先级**: P2（调度管理）  
**估计时间**: 0.5 天

---

## 总计

| 阶段 | Packages | 工具数 | 估计时间 | 优先级 |
|------|----------|--------|----------|--------|
| Phase 1 | 1 | 8 | ✅ 完成 | P0 |
| Phase 2 | 4 | ~29 | 6-8 天 | P0 |
| Phase 3 | 6 | ~45 | 9-12 天 | P1 |
| Phase 4 | 10 | ~38 | 9-11 天 | P2 |
| **总计** | **21** | **~120** | **24-31 天** | - |

---

## 重构策略

### 并行策略

由于工具间相对独立，可以并行重构多个 package：

1. **按优先级分批**：先 P0，后 P1，最后 P2
2. **按复杂度分配**：简单工具快速完成，复杂工具重点投入
3. **按依赖关系**：被依赖的 package 优先重构

### 质量门禁

每个 package 重构完成后必须通过：

- [ ] TypeScript 编译通过
- [ ] 现有测试套件通过
- [ ] 新增单元测试覆盖核心逻辑
- [ ] 手动测试至少 2 个关键工具
- [ ] 更新 package 的 README（如果存在）

### 风险控制

- 每完成一个 package 立即提交 git
- 保持主分支可运行状态
- 重构期间不添加新功能
- 遇到复杂业务逻辑时咨询用户

---

## 执行计划

### Week 1: Phase 2（核心业务）

**Day 1-2**: Investment Package（9 工具）
**Day 3-4**: Strategy Package（8 工具）
**Day 5**: Market Package（7 工具）
**Day 6**: Risk Package（5 工具）

### Week 2: Phase 3.1-3.3（智能增强 Part 1）

**Day 1-3**: Lifecycle Package（16 工具）
**Day 4-5**: Learning Package（9 工具）
**Day 6**: Intelligence Package（5 工具）

### Week 3: Phase 3.4-3.6（智能增强 Part 2）

**Day 1**: Evolution Package（3 工具）
**Day 2**: Evolver Package（6 工具）
**Day 3**: Genome Package（6 工具）
**Day 4-6**: 缓冲时间（处理技术债务、补充测试）

### Week 4: Phase 4（支撑系统）

**Day 1**: Memory + Factor（7 工具）
**Day 2**: Data Manager + Quantsys-V2 Manager（8 工具）
**Day 3**: Agent-OS Manager + Window Manager（9 工具）
**Day 4**: Model + Notification（8 工具）
**Day 5**: Competition + Scheduler（6 工具）
**Day 6**: 最终验证和文档整理

---

## 下一步

1. **确认执行顺序**：用户确认是否按 Phase 2 → Phase 3 → Phase 4 执行
2. **选择首个 Package**：建议从 `investment` 开始（核心业务，工具数适中）
3. **创建 Worktree**（按照 CLAUDE.md 规则）
4. **开始重构第一个 Package**

---

## 参考文档

- [工具开发规范（三段式 / BaseTool）](../standards/tool-development.md)
- [core-tool 规范包](../../packages/core-tool/README.md)
- [Trading Package 重构审查报告](../work-logs/2026-08/trading-refactor-review.md)（执行记录）

---

**最后更新**: 2026-08-28  
**维护者**: Agent DH Team

---

## 相关页面

- [工具开发规范](../standards/tool-development.md)
- [插件模型与装载](plugin-model.md)
- [工具审计清单](../protocols/tool-audit.md)
