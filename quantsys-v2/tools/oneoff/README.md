# tools/oneoff —— 已执行的一次性运维脚本（**归档，非生产**）

## 为什么在这里

用户 2026-09-13 裁定：**「脚本不能写到 v2 项目中，脚本只能测试用」**。
这些脚本是**一次性数据运维**（回补 / 清理 / 审计），**已经执行完毕**，
保留目的只有一个：**审计留痕**（当时到底对数据库做了什么、口径是什么）。

## 边界

· **不是生产链路的一部分**：没有任何定时任务或应用代码调用它们。
· 需要**重复执行**的数据运维能力，应当上迁为 v2 生产代码（`application/services/` + JobRegistry 任务），
  而不是在这里加脚本。已有先例：
  · core 建仓计划 → `application/services/core_plan_service.py` + `core_plan_generate`
  · 策略闭环复核 → `application/services/strategy_lifecycle_service.py` + `strategy_loop_weekly`
  · 数据卫生巡检 → `application/services/data_hygiene_service.py` + `data_hygiene_probe`
  · 净值快照稠密化 → `application/services/evolution/daily_snapshot_service.py` + `equity_snapshot_daily`
  · 事件回补 → `application/services/event_feed_service.py` + `ingest_events_history`
· 数据库结构变更请走 `scripts/migrations/*.sql`。

## 文件清单

| 脚本 | 做了什么 | 备注 |
|------|---------|------|
| `audit_fund_flow_flag.py` | 审计资金流 `quality_flag=close_mismatch_vs_kline` | 结论：**误报**（复权偏移），14,314 行已取消标记并留备份 |
| `backfill_event_type.py` | 回补事件类型 | 已被 `ingest_events_history` 任务取代 |
| `backfill_strategy_status.py` | 回填 strategy 的 structure/performance 两个状态轴 | 一次性 |
| `backfill_snapshots.py` | 回补历史净值快照 | 一次性；日常已由 `equity_snapshot_daily` 任务覆盖 |
| `cleanup_strategies.py` | 清理未过门槛的策略 | 一次性（89 → 1） |
| `event_backfill.py` | 研究级事件回补 | 已被 `ingest_events_history` 任务取代 |
