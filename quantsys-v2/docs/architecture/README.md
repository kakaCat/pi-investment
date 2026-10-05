---
title: 架构文档索引
type: index
tags: [architecture, index]
updated: 2026-10-04
summary: 架构目录的索引与待写页清单——跨模块裁决与耐久结论放这里，新页必须登记，避免孤儿页。
---

# 架构文档索引（QuantSys V2）

> 本目录存放**跨模块的架构裁决与耐久结论**。新增页面请带 front-matter
> （`title` / `type` / `tags` / `updated`），并在本页登记，避免出现无人可寻的孤儿页。

## 已写

| 文档 | 一句话 |
|---|---|
| [模拟交易链路的三条真话原则](simulation-trading-integrity.md) | 只允许一种成功：真干了、没出错、不是被跳过；失败只有一个出口，账本只有一个真源 |
| [应有交易日与新鲜度判定](trading-day-freshness.md) | 「哪天该有数据」只有一个口径：`last_closed_trading_day()` |
| [调度架构](scheduler-architecture.md) | 调度归属与三条后台线程（APScheduler / DailyJobs / WatchEngine） |
| [通知测试守卫](notification-test-guard.md) | 测试期不得真实外发通知；打桩点必须在被调函数所在模块 |
| [盯盘规则](watch-rules.md) | WatchEngine 规则管理 |
| [功能总览](FUNCTIONALITY_OVERVIEW.md) | 各模块能力清单 |
| [性能优化](PERFORMANCE_OPTIMIZATION_README.md) | 性能相关改造记录 |
| [架构审计进度](AGENTS.md) | 审计与分层约束的执行记录 |
| [记忆子系统已下线](memory-subsystem-retired.md) | v2 不再承载记忆：15 个端点全 404，记忆归 agent-os（含删前基线三条判据） |

## 待写页

- **数据源降级链**：`DataProviderManager` 的多源回退与"取不到时该怎么响"（散落在各调用方）。
- **调度归属的边界**：v2 与 agent-os 各管什么、开关组合的语义（已散见于 scheduler-architecture 与 ADR-004）。
- **模拟账户的单一真源改造**：把持仓表降级为流水的派生视图（当前是双源，见上表第一条的残留）。
- **回测与实盘的口径一致性**：同一策略在两处的费用/滑点/停牌处理是否一致。
