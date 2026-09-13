---
id: data-contracts-and-freshness
title: 数据契约与新鲜度
type: architecture
status: living
updated: 2026-09-13
owners: [w-1cee2467]
tags: [architecture, data, contracts]
---

# 数据契约与新鲜度

**这页回答**：数据从哪来、契约长什么样、怎么判断"这批数能不能用"。

## 结论先行

1. **数据源面**：quantsys-v2（:5001）为主（行情/K线/财务/因子/回测），部分工具走 akshare 多源降级链（龙虎榜、涨停池、资金流、分红…）。
2. **派生/审计数据必须在 `quantsys-v2/config/data_contracts.json` 登记**：owner / kind（派生 or 审计）/ 上游 / TTL / 删除策略 / 软引用检查；未登记 = 无人负责的数据陷阱。
3. **引用任何数字先问三句**：来自哪个工具？什么时点？口径是实时还是缓存？（R-013）
4. **风控与决策前必须校验新鲜度**：跨源交叉验证 / 窗口一致性 / 与账户事实对照——三者任一不过，结论降级为"待复核"。
5. **降级必须显式**：工具返回里的 `degraded` / `stale` / `as_of` / `source` / `attempted_sources` 要如实阅读并**写进结论**，不能默默当作正常值。

## 数据契约字段（登记时照抄）

| 字段 | 含义 |
|---|---|
| `owner` | 谁负责这张表（人/窗口/插件） |
| `kind` | `derived`（派生）或 `audit`（审计流水） |
| `upstream` | 上游来源（表/接口/任务） |
| `ttl` | 多久算过期 |
| `delete_policy` | 删除/改名时怎么处理（审计用 ON DELETE SET NULL + 冗余身份字段；派生先清或级联；生产优先状态位） |
| `soft_ref_check` | 悬空引用检查方式（每周 `data_hygiene_probe.py`） |

## 新鲜度三招（实操）

1. **跨源交叉验证**：`risk_metrics` 与 `regime_position_limit` 是两个独立实现，同一指标应给同一个数；不等就先怀疑数据。
2. **窗口一致性**：30/90/180/250 日窗口结果**完全相同** → 序列太短或冻结，单值不可信。
3. **与账户事实对照**：现金占比 87%、总盈亏 +1.13% 却报 -10.71% 回撤 —— 明显不相称，先查数据再行动。

## 依据

- K 线静默冻结期间假熔断：读 60 日回撤 -10.71%（真实 -6.77%）→ 越过 -8% 阈值并自动挂减仓单；
- `strategy_stock_matching` 800/800 行指向已删策略、105 天未更新且全仓零引用（R-020 的由来）；
- 多次"解析失败 → 空结果落库 → 幂等把空当有效"导致永久挡住重扫。

## 相关页面

- [数据与降级规范](../standards/data-and-degradation.md) · [定时巡检清单](../guides/routine-checks.md)
- [quantsys-v2 能力评估](../guides/quantsys-v2-capability-assessment.md) · [事件查询最佳实践](../guides/event-query-best-practices.md)
