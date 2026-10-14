---
req_id: REQ-261005203907-2b8c
title: 使用场景——休市日跳过 / 交易日照跑 / 降级兜底 / 人工强制
doc: design/use-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 使用场景（REQ-261005203907-2b8c）

> 判定与字段见 [`interfaces.md`](interfaces.md)；落点理由见 [`architecture.md`](architecture.md)。

## UC-1 休市日：整段跳过（serves: FR-1, FR-3, FR-4）

**前置**：`2026-10-06`（周二，国庆休市；上一交易日 09-30，下一交易日 10-08），
宿主线程正常运行，`quant.inprocess_job_runs` 当天无该任务记录。

**触发**：19:05 轮询命中 `pool_daily_refresh`（`is_due` 只看工作日 → True）。

**流程**：`_run_job` → `_mark_running` → `skip_non_trading_day()`
→ `TradingDayGuard.check(2026-10-06)` → `is_trading_day=False`、`degraded=False` → **skip=True**
→ 写 `status='skipped'` + `result.{skipped,reason,trading_day}` → 记 info 日志 → 早退。

**结果（可观测）**：
1. `quant.inprocess_job_runs` 出现 `pool_daily_refresh / 2026-10-06 / skipped`；
2. **飞书无该任务的开始/完成消息**（今天 22 秒空跑 + 2 条通知的形态消失）；
3. `pool_change_log` 当天无该池的 refresh 行（不产生非交易日换血）。
4. `chip_distribution`（21:10）、`evolution_fitness`（20:35）同形。

## UC-2 交易日：行为逐字不变（serves: FR-1, FR-4, FR-6）

**前置**：`2026-10-08`（周四，复市首日）。

**流程**：`skip=False` → 照原路径执行 handler → `find_result_failure` → `status='success'`
（照跑路径额外把 `result.trading_day` 注上，`degraded=false`）。

**结果**：`pool_daily_refresh` 正常换血并 sync 名称；`evening_pipeline` 的 K 线段与因子段都执行。
**验收锚点**：与改造前同日的 `result` 形状相比，只多 `trading_day` 一个键。

## UC-3 日历不可用：fail-open 不静默（serves: FR-2）

**前置**：`quant.trading_calendar` 不覆盖当天且 provider 不可达 → 解析链降到 `weekday_fallback`
（`degraded=True`）；或判定器抛 `compute-error` / 出现门模块自身异常。

**流程**：`skip_non_trading_day()` → `degraded=True` → **skip=False（照跑）**。

**结果（可观测）**：
1. 任务照常执行，`status` 按真实结果记 `success` / `failed`；
2. `result.trading_day.degraded=true` 且 `source` 标明降级来源；
3. 日志一条 `inprocess_job_trading_day_degraded`（不许静默）；
4. **最坏情况 = 现在的行为（多跑一次），不会出现"该跑没跑"**。

## UC-4 复市首日不得被跳过（serves: FR-5）

**前置**：长假最后一个休市日是 `2026-10-07`，`2026-10-08` 为交易日。

**流程**：`skip_non_trading_day(2026-10-08)` → `is_trading_day=True` → 照跑。

**结果**：`pool_daily_refresh` 与 `evening_pipeline` 当天均 `success`；
这正对着 a7cd 定下的口径「休市日不开火、**复市首日不跳过**」。

## UC-5 休市日的人工触发（serves: FR-5）

**前置**：`pool_daily_refresh / 2026-10-06` 已有 `skipped` 行；运维或 agent 调
`trigger_job('pool_daily_refresh')`。

**流程与结果（两条既有语义，本设计一起锁死）**：
1. **不因 `skipped` 而被拒绝**：`trigger_job` 的拒绝条件只有 `running` / `success`
   （`runtime.py:283-285`），`skipped` 不在其中 → 放行并起线程；
2. **但休市日语义仍然成立**：门在 `_run_job` 内，人工触发**同样命中**门 →
   再次写回一行 `skipped`（幂等更新同一 `(job_id, run_date)` 行），**不会**凭空放开休市日的重算。

**即**：`skipped` 不是"已跑过"的拒绝理由，但也不是"绕过门"的通行证。

**决策留痕**：**刻意不新增"休市日强制重算"参数或开关**——那等于给门开一条无人审计的旁路。
真要补算，用显式命令直接跑具体作业（如 `python -m infrastructure.jobs.chip_distribution_update_job`，
不写 DailyJobs 台账）比加开关更诚实；这与 [`architecture.md`](architecture.md)「回滚路径」
拒绝 `DISABLE_*` 开关是同一条纪律。

## UC-6 休市日 K 线被修复 → 因子照跑（serves: FR-4）

**前置**：休市日 `evening_pipeline` 的 K 线段发现覆盖度不足（例如有人回填了一批标的），
`update_gem_klines` 返回 `status='success', success=137`。

**流程**：`non_trading=True`，但 `kline_changed=True` → **因子段照跑**
（把修复出来的数据算进因子，避免留空洞）。

**结果**：`result.factor_compute` 为真实的因子计算结果；任务按既有判定记 success/failed。

## UC-7 休市日 K 线段照跑、因子段跳过（serves: FR-4）

**前置**：休市日，K 线覆盖度 99.8% ≥ 门槛 → `kline_sync.status='skipped'`。

**流程**：`non_trading=True and kline_changed=False and status!='error'` → **因子段跳过**。

**结果（可观测）**：
1. `result.factor_compute = {'status':'skipped','skipped':true,'reason':'非交易日…且 K 线本次无更新'}`；
2. 任务整体仍 `success`（K 线段真的跑了），完成通知的摘要里带 `skipped=True`（属期望行为）；
3. 全市场因子计算（今天实测 ≥10 分钟且仍在跑）在休市日不再发生。

## UC-8 回滚（serves: FR-1, FR-4）

**前置**：上线后发现某任务在休市日仍需执行（或判定器行为异常）。

**流程**：撤掉该任务的 `trading_days_only=True`（或撤掉 `evening_pipeline` 的因子段判定）→ 重启服务。

**结果**：行为逐字回到改造前；历史 `skipped` 行无需清理（无消费者把它当异常态）。
