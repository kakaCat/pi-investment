---
req_id: REQ-261004102115-d3de
title: 交易日历表契约与回填口径
doc: design/data-model
serves: FR-1, FR-2
---

# 数据模型设计（REQ-261004102115-d3de）

**先说结论**：**不新增表、不新增字段、不改 ORM 模型、不写迁移脚本**。
被触及的数据只有两样：既有的 `quant.trading_calendar`（**只读**）与探针/守卫的输出字典（**加键**）。

## 既有表契约（serves: FR-1）

`quant.trading_calendar`（实测 2026-10-04）：

| 列 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `trade_date` | `date` | NO | 日期 |
| `exchange` | `varchar` | NO | `SSE` / `SZSE` / `ALL` |
| `is_trading_day` | `boolean` | YES | **回填时只写 TRUE/FALSE**，不写 NULL |

**现状**：0 行；主键实测为 `(trade_date)` 单列——回填脚本 `_ensure_composite_pk()` 会在
**空表**时改成 `(trade_date, exchange)`（本需求实施时表仍为空，正是它设计时的前提）。

**本需求对该表的动作**：**只读**。不做写入、不做 DDL 变更。
（回填由既有命令人工执行一次：`./venv/bin/python tools/refresh_trading_calendar.py`；
其数据源改造见下。）

## 刷新脚本的数据源改造（serves: FR-1）

`tools/refresh_trading_calendar.py` 现从 `daily_klines` 的 `DISTINCT trade_date` 灌表——
**K 线没有未来交易日**，这条源永远让表"刚填好就过期"。

改造：源改为 ② provider（`get_trading_calendar`，实测含未来日期），
保留原有 UPSERT（`ON CONFLICT DO NOTHING`）与复合主键确保逻辑；
`daily_klines` 源**作为并集保留**（历史深水区的兜底），二者取并集写入。

**不新增排班**：本次不给该脚本加 launchd/cron（属调度层决定，越界即升级重档）。
代价如实登记——表一旦不覆盖 `anchor`，探针每次运行都会走一次 provider，
在 Redis 可用时由 provider 侧缓存吸收，否则为每 5 分钟一次的外部调用；
这是**已知且响亮**的状态（`expected_source=provider`），不是静默降级。

## 读取口径与兼容影响（serves: FR-1）

表被填上后，有一个**必须写在明处的连带影响**：

`application/services/data_pipeline_service.py:load_trading_calendar_from_db(exchange)`
现在的路径是"表为空 → 记 `trading_calendar_empty_fallback_to_klines` error → 回退 K 线真源"。
表被填上后它会**走表**（不再打那条 error 日志）——**这正是该函数注释里要求的修复方向**
（注释原文："请检查日历刷新任务"），且回退路径与异常处理**一行不改**，故为可控变更。
判定：属于"表被正确填充"的正常后果，**登记而非规避**；若需回退，清空该表即回到现状。

## 需要迁移/回填的东西（serves: FR-1）

| 项 | 是否需要 | 做法 |
|---|---|---|
| 表回填 | 需要（一次性） | `./venv/bin/python tools/refresh_trading_calendar.py`（幂等） |
| DDL 迁移 | **不需要** | 不改表结构 |
| 数据回填（K 线） | **不需要** | 09-30 数据完整（5276 只，与 09-28/29 一致） |
| 输出契约迁移 | 增量键，无需迁移 | 消费方按存在性读取新键 |

## 探针/守卫输出结构（serves: FR-2）

```jsonc
// tools/health_probe.py --dry-run 的 kline_freshness 检查项（新增键以 ★ 标出）
{
  "name": "kline_freshness",
  "ok": true,
  "expected": "2026-09-30",        // 语义修正：最近一个已收盘交易日
  "expected_source": "calendar",   // ★ calendar | provider | weekday_fallback
  "expected_degraded": false,      // ★ bool
  "kline_latest": "2026-09-30",
  "factor_latest": "2026-09-30",
  "lag_days": 0,
  "max_lag_days": 1
}
```

`quant.inprocess_job_runs.result`（jsonb）新增 `expected_source` 键，**不需要**迁移。
