# 测试证据（REQ-261006130750-0654）

**测试入口（唯一）**：`tests/api/test_orchestrator_trading_day_gate.py`（12 条）
**命令与结果**：

```bash
$ ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q
12 passed
notify-guard intercepted=0 egress=0 offenders=[]

$ ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py \
      tests/api/test_orchestrator_bootstrap.py tests/test_market_session_policy.py \
      tests/test_trading_window_guard.py tests/test_scheduler_trading_day_gate.py \
      tests/test_daily_jobs_trading_day_gate.py -q
98 passed
```

## 1. 用例矩阵（design/test-cases.md T1–T13 → 实际用例）

| 设计编号 | 用例 | 断言要点 | 结果 |
|---|---|---|---|
| T1 | `test_intraday_holiday_skips_without_touching_positions` | 休市日 `check()` 返回 `non-trading-day`；**不构造** `PaperTradingEngine`；零通知 | ✅ |
| T2 | `test_intraday_trading_day_still_runs` | 交易日照跑（`no_positions`），引擎构造恰好 1 次 | ✅ |
| T3 | `test_intraday_degraded_is_fail_open` | 降级 → `should_skip` 返回 `(False, ·)` 且 `degraded=True`，照跑 | ✅ |
| T4 | `test_gate_own_exception_is_fail_open` | 门自身异常 → 照跑 + `source='gate-error'`，不抛 | ✅ |
| T5 | `test_future_date_is_not_a_holiday_verdict` | 动态未来日 → `source='future'`（反例锁） | ✅ |
| T6 | `test_orchestrator_loop_silent_on_holiday` | 休市日两条 tick **零调用**，且 `_LAST_SKIP_LOG` 证明循环真跑过 | ✅ |
| T7 | `test_orchestrator_loop_runs_on_trading_day` | 交易日照调 ≥1 次 | ✅ |
| T8 | `test_static_single_source_of_truth` | `should_skip` 出现 ≥2；`intraday_monitor` 零 `weekday(`；零直查日历 | ✅ |
| T9 | `test_stub_point_is_the_gate_module` | 桩打在 `trading_day_gate.TradingDayGuard` 生效；打在调用方只影响该模块 | ✅ |
| T10 | `test_skip_log_is_deduped_per_path_and_day` | 同 `(path, day)` 只 1 条；换天恢复 | ✅ |
| T11 | `test_window_semantics_unchanged` | 窗口函数时段语义逐条不变 | ✅ |
| T12 | `test_intraday_time_check_precedes_day_gate` | 时段外仍是既有 `not trading time`（严格增量） | ✅ |

## 2. 红→绿（反例锁：证明门会红）

| 注入 | 结果 | 复原 |
|---|---|---|
| **③** `trading_day_gate` 改成「degraded 也跳过」 | **2 红**：`test_intraday_degraded_is_fail_open`、`test_gate_own_exception_is_fail_open` | shasum 校验一致 |
| **⑤** 调用方判**错的一天**（`now` → 次日） | **2 红**：`test_orchestrator_loop_silent_on_holiday`、`test_skip_log_is_deduped_per_path_and_day` | shasum 校验一致 |
| **⑥** 把 B 层门改成 `if False:` | **2 红**：`test_intraday_holiday_skips_without_touching_positions`、`test_stub_point_is_the_gate_module` | shasum 校验一致 |

三次注入后 `grep INJECTED` 于四个源码文件均为 **0**（无残留）。

## 3. 真实运行观察（非单测）

- 部署：`2026-10-06 13:21:33` `launchctl kickstart -k`（PID 86953 → 61630），`/health` = ok。
- 留痕（`logs/api.log`，ASCII 事件名可直接 grep）：
  - `13:21:44` `orchestrator_trading_day_skip` path=`orchestrator_tick` source=`trading-calendar-holiday` degraded=false（第 9400 行）
  - `13:30:46` 同事件 path=`intraday_monitor`（第 9408 行）
- 去噪：休市日编排线程每分钟命中一次，实际每天每路径**只 1 条**。
- 写库面零变化：`quant.simulation_positions` 最新 `2026-10-04`、`rotation_main` 账户 `2026-07-25`、
  `daily_orchestrator_state`（10-06）0 行。
- ⚠️ **节奏坑**：循环按线程启动时刻对齐 60s 节拍，`13:30` 槽位实际在 `13:30:46` 判定
  ——复跑时别在 `:00:05` 查空就判"没生效"。

## 4. 待取窗口（t4 未完成项）

`2026-10-07`（休市）与 `2026-10-08`（复市首日）的复跑**尚未执行**（当天为 10-06），
清单见 [../notes/holiday-observation.md](../notes/holiday-observation.md) §3。
**不得**用本文件的 12 passed 顶替这两天的真实观察。

## 5. 卡覆盖标注（covers，供覆盖度门禁对账）

covers: t-37a691
covers: t-32ec6a
covers: t-6d2074
covers: t-164414
covers: t-bcbe54
covers: t-2ab0a5
covers: t-011042
covers: t-67db61
covers: t-45c620
covers: t-ea86ce
covers: t-1d7233
covers: t-bcf326
covers: t-22d1ba
covers: t-b554a3
covers: t-b87557
covers: t-047d90
