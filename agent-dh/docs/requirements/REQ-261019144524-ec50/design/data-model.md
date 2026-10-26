# 数据模型说明（spike 口径）

> 本 spike 不新建/修改任何表结构。本文件登记调研中**实测过的数据面**及其口径，作为报告数据的复核依据。

## 调研触及的数据表（全部只读）

| 表 | 库 | 实测口径（2026-10-19） |
|---|---|---|
| `memories`（category='experience'） | quant_investment | 343 条；五桶分类：真实标的 73 / 伪代码 000000 计 8 / SYSTEM 13 / distiller JSON 信封 64 / 无 symbol 文本 185。分桶 SQL 见 [../w4-experience-cleanup.md](../w4-experience-cleanup.md) §1 |
| `quant.strategy_configs` | quant_investment | 5 条（163/178/179/193/202），全 unmeasured；数量时间线 89→14→101→5（后两次无台账） |
| `quant.backtest_results` | quant_investment | 540 行孤儿（属 12 个已删策略名） |
| `public.evolution_runs` / `quant.evolution_strategy_runs` | quant_investment | 19/32 行、87/91 行悬空引用 |
| `tasks` / `task_runs` / `task_delivery_backlog` | quant_investment | W1 用：58 启用任务全配 webhook_url、17 条占位 command `/usr/bin/true`；backlog 90 条（31 delivered / 59 failed 永久丢失） |
| `quant.signal_tracking`（信号库） | quant_investment | 82 条（2026-09-19~10-19）：A3/B26/C53；C 级有 5/10 日回填胜率 |

## 口径陷阱（本需求实证，引用数据前必读）

1. **experience_stats 工具 limit 即截断**：limit=200 返回恰 200 条 ≠ 库内总数（343）；统计结论以 psql 全量为准。
2. **decision_scores 无账户过滤参数**：必须逐条看 `items[].context.account`；27 条全为策略线回填，本账户 0 条。
3. **回测 totalTrades 只在平仓时计数**：「开仓未平仓」回测 totalTrades=0，不能当"无信号"判据（W4 §4.3 实证：-23.18% 被判无信号）。
4. **reqboard 工具读投影可能滞后于 queue.json**：task_tree/status 曾显示 in_progress 而 queue.json 已 done（自动链刚闭环）；以 queue.json 为准。
