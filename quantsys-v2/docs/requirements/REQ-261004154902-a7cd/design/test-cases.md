---
req_id: REQ-261004154902-a7cd
title: 测试用例与可执行验收（含"假绿灯"修正）
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
---

# 测试用例与验收（REQ-261004154902-a7cd）

> 总览见 [`design.md`](design.md)。**先修假绿灯，再加真断言**——否则"全绿"不构成证据。

## 0. 先修三处假绿灯（serves: FR-1, FR-5, FR-6）

| # | 位置 | 现状（实测） | 改成 |
|---|---|---|---|
| T0-1 | `tests/test_v13_scheduler.py` | 用例体是 `return True/False`（pytest 忽略返回值）→ 输出打印「❌ Job执行失败」「❌ 任务不存在」却 **3 passed** | 全部改 `assert`；断言失败必须让用例红 |
| T0-2 | `tests/regression/test_strategy_config_refactor.py:25-26` | `assert V13_CONFIG.model_path == "live_trading/models/xgboost_multi_factor_model.json"`（**该文件不存在**）→ 把 bug 锁死，10 passed | 改为 `assert Path(V13_CONFIG.model_path).exists()` |
| T0-3 | `tests/test_scheduled_jobs_account_value.py` | 用真实仓储**没有的**方法（`get_trades_by_date` / `count_rebalances`）做 Fake → 掩盖 AttributeError，3 passed | Fake 只提供真实存在的接口；补一条"Fake 与真实仓储签名一致"的断言 |

## 1. 单元/集成用例（serves: FR-1, FR-2, FR-7）

| # | 场景 | 触发 | 期望 |
|---|---|---|---|
| T1 | 调仓失败必须如实上报 | 让 `factor_calc.get_latest_factors` 返回空 DataFrame | `run_daily_check()` 返回 `ok=False, reason='factor_empty'`；**不得** `executed=True, action='rebalance'` |
| T2 | 模型异常必须如实上报 | 让 `model.predict` 抛 `ValueError` | `ok=False, reason='rebalance_failed'`，`error` 非空 |
| T3 | 通知方法必须存在 | `hasattr(SimulationTrader,'_send_rebalance_notification')` | `True`（当前 False） |
| T4 | 通知失败不得污染成功判定 | 让通知方法抛错 | `ok=True`（交易成功），`detail['notify_error']` 非空 |
| T5 | 合理跳过不得记 success | 周末运行 | `ok=False, reason='not_trading_day'`；`scheduler_runs.status='skipped'` |
| T6 | 挂单批量不中断 | 第一笔必抛非 `TradingError`，第二笔正常 | ①第一笔 `failed` + `fail_reason`；②第二笔被处理；③`errored>=1` |
| T7 | 非交易时段不误杀 | `now=16:41` 调用撮合 | `skipped_off_hours>0` 且 `failed==0`，挂单仍 `pending`（当前行为：批量 `failed`） |
| T8 | 超期挂单必须收口 | `pending` 且创建时间早于上一交易日 | `status='expired'` + `fail_reason` 非空 + 一条外发告警 |

## 2. 交易日判定用例（serves: FR-3）

```bash
venv/bin/python - <<'PY'
from application.services.trading_day_guard import TradingDayGuard
# 需注入"今天"= 对应日期（或直接调纯函数 judge_trading_day）
for d, exp in [('2026-10-05', False), ('2026-10-06', False), ('2026-10-07', False), ('2026-10-08', True)]:
    got = TradingDayGuard.check(d, use_cache=False).is_trading_day
    print(d, got, 'EXPECT', exp, 'OK' if got == exp else 'FAIL')
PY
```

| # | 断言 | 当前实测 |
|---|---|---|
| T9 | `2026-10-05/06/07 → False`（国庆休市） | **True**（误判，会调仓） |
| T10 | `2026-10-08 → True`（复市首日） | **False**（会被跳过） |
| T11 | 日历链降级时 `verdict.degraded is True` 且 `source` 标明 | 需新增 |
| T12 | `judge_trading_day(..., calendar_has_day=None)` 仍走旧逻辑（既有 8 条测试不破） | 现状 8 条全过 |

## 3. 时刻与漏跑用例（serves: FR-4, FR-8）

| # | 场景 | 期望 |
|---|---|---|
| T13 | cron 小时回归锁 | `build_cron_trigger('30 14 * * 1-5')` 的 `next_run_time.hour == 14`（本地语义）；防止再漂 8 小时 |
| T14 | NULL 宽限语义 | 加载器对 `misfire_grace_time_seconds IS NULL` 的任务**不套 300 秒**（按"必补跑"处理），显式值才用显式值 |
| T15 | 「该跑没跑」盘点 | 人为把某任务 cron 设为"1 分钟前" → 盘点器报 `missed`、退出码 2；重复调用**只告警一次**（节流） |
| T16 | 探活覆盖进程死 | `kill -9` API 进程后 ≤2 个探测周期内主动外发（**该项需人工在维护窗口执行，属验收阶段动作**） |

## 4. 配置、链路与账本用例（serves: FR-5, FR-6, FR-10）

| # | 场景 | 期望 |
|---|---|---|
| T17 | 声明 == 生效 | `tools/check_strategy_config_effective.py` 退出码 0（`rebalance_days` / `top_n` / `single_stop_loss` 三处一致；当前声明 8 只 vs 生效 5 只） |
| T18 | 未接线链路已修实 | `Path(V13_CONFIG.model_path).exists() and Path(V13_CONFIG.factors_path).exists()` |
| T19 | 不存在的仓储方法不再被调用 | `grep` 三个 job 文件不得出现 `get_trades_since` / `get_trades_by_date` / `trade.direction` |
| T20 | 超卖被拦 | 构造"卖出量 > 净持仓"的委托 → 拒绝 + `reason='oversell_blocked'`；对账器超卖清单 **0 行** |
| T21 | 现金可重放 | `tools/reconcile_sim_account.py` 的差额逐项可解释（历史 ¥49,425 的处置由人定，见 `use-cases.md` §6） |

## 5. 通知用例（serves: FR-9）

| # | 场景 | 期望 |
|---|---|---|
| T22 | `rebalance` 类型必须能到飞书 | `select_channels('rebalance')` 含 `feishu`（当前为 `['agent']`） |
| T23 | `risk_alert` 类型必须能到飞书 | 同上（当前为 `['agent']`） |
| T24 | Agent OS 死后仍送达 | 8080 不可达时触发一次失败通知 → 飞书收到；日志三行证据（agent 失败 → 降级 → `delivered=true`） |
| T25 | 无 formatter 不得静默 | 未注册 formatter 的类型必须留 `error` 级日志（当前 `ChannelResult.error` 会吞在返回值里） |

## 6. 验收命令汇总（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10）

```bash
venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py \
  tests/services/test_pending_orders.py tests/test_trading_day_guard.py \
  tests/regression/test_strategy_config_refactor.py -v     # 全绿，且 T0 三处已是真断言
venv/bin/python tools/check_strategy_config_effective.py    # exit 0
venv/bin/python tools/check_should_have_run.py              # exit 0（无漏跑）
venv/bin/python tools/reconcile_sim_account.py --account v13_simulation   # 超卖 0 行
```

- ⚠️ 本仓知识层未生成（`reqboard_kb(kind='standard')` 返回 0 条）⇒ 无法引用"规范条目"，
  已如实记录，不用猜测填补。
