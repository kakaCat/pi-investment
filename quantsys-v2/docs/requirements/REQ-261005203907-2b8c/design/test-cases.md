---
req_id: REQ-261005203907-2b8c
title: 测试策略与用例——门、留痕、逐任务范围、真实观察
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 测试用例设计（REQ-261005203907-2b8c）

> 契约见 [`interfaces.md`](interfaces.md)；落点见 [`architecture.md`](architecture.md)。

## 0. 打桩纪律（本仓踩过的坑，先钉死）（serves: FR-3, FR-4, FR-6）

1. **桩必须打在被调函数所在模块**：
   - `_run_job` 里的通知/落库走 `daily_jobs.runtime` 的模块全局名 →
     必须 `monkeypatch.setattr(host_runtime, '_send_feishu' / '_mark_done' / '_mark_running', ...)`；
     打在 `daily_jobs.alerting` 或转发壳 `daily_jobs_bootstrap` 上**名字存在但不生效**、真函数照发
     （实证：2026-10-02 因此真发 4 张飞书卡片，见 `tests/test_false_success_guard.py:150-160`）。
   - `_job_evening_pipeline` 调 `is_non_trading_day()` → 打 `daily_jobs.pipeline.is_non_trading_day`。
   - 该函数内的 `handle_factor_compute` / `update_gem_klines` 是**函数内局部 import** →
     打 `application.services.scheduler_tasks.handle_factor_compute` /
     `infrastructure.jobs.kline_update_job.update_gem_klines`（源头模块），不是 pipeline 模块。
2. **不得真实外发**：根 `conftest.py` 的 `tests/notify_guard.py` 处于 `fail` 模式——
   未声明的真实通知外发会让该用例**失败**。跳过路径的断言之一就是"没有通知"，
   故 `_send_feishu` 必须被打桩并断言调用次数。
3. **日期显式传入**：`skip_non_trading_day(now)` 接收显式时刻；`_run_job` 不接受日期参数，
   故 `_run_job` 的用例改为打桩 `daily_jobs.runtime.skip_non_trading_day` 返回 `(True, info)`。
4. **零网络零 DB**：全部单元测试用打桩，不连库、不连 provider（`TradingDayGuard` 被替换为假判定）。

## TC-1 判定真值表（serves: FR-1, FR-2）

`tests/test_daily_jobs_trading_day_gate.py`

| 用例 | 输入（`now`） | 期望 |
|---|---|---|
| `test_holiday_skips` | `2026-10-05 / 10-06 / 10-07` | `skip=True`，`source='trading-calendar-holiday'`、`degraded=False` |
| `test_trading_day_runs` | `2026-09-30`、`2026-10-08` | `skip=False`，`is_trading_day=True` |
| `test_weekend_skips` | `2026-10-03`（周六） | `skip=True`，`source='weekend'`（与排班叠加为双保险） |
| `test_degraded_runs_fail_open` | 假判定 `is_trading_day=False, degraded=True, source='weekday_fallback'` | **`skip=False`**（判据与，不是或） |
| `test_gate_error_runs` | 让 `TradingDayGuard.check` 抛异常 | **`skip=False`**、`source='gate-error'`、不抛给调用方 |
| `test_returns_annotation_shape` | 任意 | 注解含 `day/is_trading_day/source/degraded/reason` 五键且类型正确 |

**打桩**：`monkeypatch.setattr(daily_jobs.gate, 'TradingDayGuard', _FakeGuard(verdict))`。

## TC-2 `_run_job` 跳过留痕与静默（serves: FR-3）

| 用例 | 断言 |
|---|---|
| `test_skip_writes_skipped_row_and_no_notify` | `_mark_done` 收到 `status='skipped'`、`result['skipped'] is True`、`result['trading_day']` 五键齐；`_send_feishu` 调用次数 **== 0**；`_mark_running` 先于 `_mark_done` |
| `test_skip_does_not_invoke_handler` | handler 被替换为 `Mock(side_effect=AssertionError)` → 未被执行 |
| `test_skip_does_not_observe_duration` | `scheduler_job_duration_seconds.labels(...).observe` 未被调用（与 FR-3 的指标契约一致） |
| `test_degraded_run_annotates_result` | 门判"照跑"且 `degraded=True` → `result['trading_day']['degraded'] is True` 且发出 `inprocess_job_trading_day_degraded` 日志 |

## TC-3 逐任务范围（serves: FR-4）

| 用例 | 断言 |
|---|---|
| `test_registry_flags_exactly_three` | `JOBS` 中 `trading_days_only=True` 的集合**恰好** = `{pool_daily_refresh, chip_distribution, evolution_fitness}` |
| `test_unflagged_jobs_default_false` | 其余 6 个任务该字段为 `False`；`JobDef('x', t, (0,), h, 'd')` 位置参数构造仍可用（默认值生效） |
| `test_evening_pipeline_not_flagged` | `evening_pipeline` 的该字段为 `False`（它靠 handler 内局部判定） |

## TC-4 `evening_pipeline` 因子段真值表（serves: FR-4）

`tests/test_evening_pipeline_holiday_gate.py`（打桩 `daily_jobs.pipeline.is_non_trading_day`
+ `pipeline._kline_coverage` + `pipeline._probe_kline_sources` + 源头模块的
`update_gem_klines` / `handle_factor_compute`）

| 用例 | `non_trading` | `kline_sync` | 期望 |
|---|---|---|---|
| `test_holiday_fresh_kline_skips_factor` | True | `{'status':'skipped'}` | `handle_factor_compute` **未被调用**；`result['factor_compute']['skipped'] is True` |
| `test_holiday_repaired_kline_runs_factor` | True | `{'status':'success','success':137}` | `handle_factor_compute` **被调用一次** |
| `test_holiday_zero_success_skips_factor` | True | `{'status':'success','success':0}` | 因子段跳过；且既有"假成功"判失败逻辑不受影响 |
| `test_holiday_kline_error_still_computes_then_raises` | True | `{'status':'error','error':'boom'}` | 因子段**照跑**；随后**仍 raise**（失败上抛语义不变） |
| `test_trading_day_never_skips_factor` | False | `{'status':'skipped'}` | 因子段**照跑**（防"交易日漏算因子"回归） |
| `test_result_passes_failure_classifier` | True | `{'status':'skipped'}` | `find_result_failure(result) is None`（嵌套 `skipped=True` 不算失败） |

## TC-5 不触发补跑与人工触发（serves: FR-5）

| 用例 | 断言 |
|---|---|
| `test_skipped_row_blocks_rerun_same_day` | `is_due(job, now, {'status':'skipped','started_at':now}) is False` |
| `test_skipped_row_not_catchup` | `catchup_due(job, now, has_recent_failure=True) is False`（排班日分支）且 `_jobs_loop` 在 `last is not None` 时不进补跑评估 |
| `test_trigger_job_allows_skipped` | `trigger_job(job_id, force=False)` 不返回"今日已有记录"拒绝 |
| `test_regression_is_due_semantics` | 既有 `tests/test_daily_jobs_bootstrap.py::TestIsDue` **全过**（不回归 success/running/failed 三分支） |

## TC-6 真实观察（不写代码，验收时执行）（serves: FR-6）

休市日（`2026-10-06` 或 `10-07`，21:20 之后跑）：

```sql
SELECT job_id, status, result->>'reason' AS reason
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' ORDER BY job_id;
-- 期望：pool_daily_refresh / chip_distribution / evolution_fitness = skipped；
--       watch_rule_health / event_calendar_check / freshness_guard 仍 success
```

```sql
SELECT job_id, status, result->'factor_compute'->>'status' AS factor
FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' AND job_id='evening_pipeline';
-- 期望：factor = 'skipped'（若当天 K 线段确有更新则应为真实计算）
```

复市首日（`2026-10-08`）：

```sql
SELECT job_id, status FROM quant.inprocess_job_runs
WHERE run_date = DATE '2026-10-08' AND job_id IN ('pool_daily_refresh','evening_pipeline');
-- 期望：两行都是 success（复市首日不跳过）
```

**静默验证**：休市日当天飞书侧**不应**收到这 3 个任务的开始/完成消息
（对照 2026-10-05：`pool_daily_refresh` 发了开始+完成两条）。

## 7. 命令与期望（可执行验收）（serves: FR-6）

```bash
# ① 新增：门与宿主分支
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q          # 期望：全过
# ② 新增：晚间管线因子段真值表
./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q       # 期望：全过
# ③ 既有回归（调度语义 + 真发通知守卫 + 池刷新）
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py \
    tests/test_pool_refresh_daily.py -q                                          # 期望：全过，无新增失败
# ④ 通知零外发：会话末打印 notify-guard 计数
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q -s | tail -3
#    期望：notify-guard intercepted=N egress=0 offenders=[]
```

## 8. 边界与不测（serves: FR-1, FR-4）

- **不测** `TradingDayGuard` / `trading_day_resolver` 自身（已有 47 条既有用例，本需求不改它们）。
- **不测** APScheduler 路径（不在范围）。
- **不测**真实飞书（打桩 + 通知守卫即证据）；**不测**真实数据源。
- `weekend` 用例只锁门模块行为——周末本就不在 3 个任务的 `weekdays` 内，
  两道防线叠加属有意（防将来有人把某任务改成含周末排班）。
