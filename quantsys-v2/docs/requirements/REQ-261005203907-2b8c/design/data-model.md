---
req_id: REQ-261005203907-2b8c
title: 数据模型——零 DDL、状态取值扩展与 result JSONB 契约
doc: design/data-model
serves: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 数据模型设计（REQ-261005203907-2b8c）

> 接口签名见 [`interfaces.md`](interfaces.md)；落点见 [`architecture.md`](architecture.md)。

## 1. 结论：本次**零 DDL、零迁移、零回填**（serves: FR-1, FR-3）

- 不新增/删除表、列、索引、约束；不改 ORM 映射（`InProcessJobRun` 保持原样）。
- 唯一的数据面变化是**既有列的取值集合扩展**（`status` 多一个 `'skipped'`）与
  **既有 JSONB 列的键增量**（`result`）。两者都被现有结构容纳：
  `quant.inprocess_job_runs.status` 是 `text NOT NULL`（**无 CHECK 约束**）、`result` 是 `jsonb`。
- 因此**不存在**"旧数据要不要迁"的问题：历史行语义不变，新行只是多一种终态。

## 2. `quant.inprocess_job_runs.status` 取值集合（serves: FR-3）

| 取值 | 谁写 | 含义 | 消费者判据 |
|---|---|---|---|
| `running` | `_mark_running` | 已起线程、未收尾 | 僵死 >3h 允许重跑（`_RUNNING_STALE_HOURS`）；孤儿判死只看它 |
| `success` | `_mark_done` | handler 正常返回且无内层失败 | 当日不重跑 |
| `failed` | `_mark_done` | 抛异常 / 内层失败（`find_result_failure`） | 2h 冷却后重试；失败巡检只看它；跨日补跑看它 |
| **`skipped`** | **`_mark_done`（新增早退分支）** | **判定为休市日 → 本次不执行** | **当日不重跑、不补跑、不告警；允许人工 `trigger_job` 重跑** |

**列约束**：`text NOT NULL`，无枚举校验，故新增取值**不需要迁移**；
`JobRunRepository.mark_done(job_id, run_date, status, result=None, error=None)`
原样接受任意状态字符串（`job_run_repository.py:144-171`）。

## 3. `result` JSONB 契约（serves: FR-2, FR-3, FR-4）

### 3.1 整段跳过（`pool_daily_refresh` / `chip_distribution` / `evolution_fitness`）（serves: FR-3, FR-4）

```json
{
  "skipped": true,
  "reason": "非交易日（2026-10-06）：该日不在交易日历中",
  "trading_day": {
    "day": "2026-10-06",
    "is_trading_day": false,
    "source": "trading-calendar-holiday",
    "degraded": false,
    "reason": "该日不在交易日历中"
  }
}
```

- `skipped: true`（**bool**）沿用仓内既有约定：显式跳过不算失败（`job_executor.py:157`）。
- `reason` 为人类可读原文（≤200 字符），进 `_summarize_result` 的 `skipped` 摘要键。
- `trading_day` 为判定注解（字段表见 [`interfaces.md`](interfaces.md) §1）。

### 3.2 照跑但日历降级（fail-open 的留痕）（serves: FR-2）

`result.trading_day` 出现且 `degraded=true`（如 `source='weekday_fallback'`），
同时日志有 `inprocess_job_trading_day_degraded` 一条 warning —— **"这次按工作日口径跑了"必须看得见**。

### 3.3 `evening_pipeline` 的因子段局部跳过（serves: FR-4）

```json
{
  "kline_sync": { "status": "skipped", "reason": "K线覆盖 5265/5277（99.8%）≥ 基准日 2026-09-30",
                  "coverage": { "total": 5277, "covered": 5265, "coverage": 0.998, "stale": 12,
                                "oldest_stale": "2026-09-29" } },
  "factor_compute": { "status": "skipped", "skipped": true,
                      "reason": "非交易日（2026-09-30 基准）且 K 线本次无更新" }
}
```

**`kline_sync` 形状的两条既有事实**（本设计依赖它们做判据，务必按原件理解）：
1. 新鲜路径由 `pipeline.py:76-88` 产出：`status='skipped'` + `coverage`；
2. 同步路径是 `update_gem_klines()` 的原样返回：`status='success'` 且
   **`success` 是"成功只数"（int），不是布尔**（`kline_update_job.py:235-255`）；
   失败路径 `status='error'` + `error`。

⚠️ **命名撞车提示（真实陷阱）**：`kline_sync.skipped` 是**跳过只数（int）**，
而本设计新增的 `factor_compute.skipped` 是**布尔**。二者嵌套层级不同，互不影响；
`find_result_failure` 的判据是 `result.get("skipped") is True`（严格布尔），
故 `kline_sync` 里的 int 不会被误判——**改动这两处时不得互换语义**。

### 3.4 与 `find_result_failure` 的交互（不变量）（serves: FR-3, FR-4）

| 结果形状 | 判定 |
|---|---|
| 顶层 `skipped: true`（整段跳过） | 走独立早退分支，不入判定器 |
| 嵌套 `factor_compute.skipped: true` | 判定器下钻时遇 `is True` → 判"非失败" ⇒ 任务记 `success` |
| `kline_sync.skipped: 12`（int） | `is True` 为假 → 参与既有判定，行为不变 |

## 4. 迁移、兼容与回滚（serves: FR-1, FR-3, FR-5）

- **迁移**：无。`status` 无约束、`result` 无 schema 校验。
- **回滚**：撤掉 3 处 `trading_days_only=True` 与 `evening_pipeline` 的因子段判定即可
  （见 [`architecture.md`](architecture.md) 「回滚路径」）。已写入的 `skipped` 行**无需清理**：
  没有任何消费者把 `skipped` 当异常态。
- **兼容**：`_summarize_result` 已把 `skipped` 纳入摘要键（`alerting.py:195`），
  完成通知里会显示 `skipped=True`——但**跳过路径不发通知**，该键只在"照跑但因子段跳过"
  （`evening_pipeline`）时出现在完成通知里，属**期望行为**（这条任务真的跑了 K 线段）。
- **可观测查询**（运维/验收用）：

```sql
-- 某休市日：哪些任务被跳过（应只见声明了标志的 3 个）
SELECT job_id, status, result->>'reason' AS reason, result->'trading_day'->>'source' AS source
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' ORDER BY job_id;

-- 复市首日：两个关键任务应恢复 success
SELECT job_id, status, started_at FROM quant.inprocess_job_runs
WHERE run_date = DATE '2026-10-08' AND job_id IN ('pool_daily_refresh','evening_pipeline');
```
