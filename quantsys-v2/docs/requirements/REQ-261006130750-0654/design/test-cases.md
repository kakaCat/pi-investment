# REQ-261006130750-0654 · 设计：测试策略与用例

**测试目标**：把"休市日不空转"从**口头结论**变成**可证伪的断言**，并证明三件不许发生的事：
① 钱路执行次数变少；② 日历降级时静默停摆；③ 有人拿"未来日"当休市日判据。

**新增用例文件（唯一）**：`tests/api/test_orchestrator_trading_day_gate.py`
**打桩点（本仓 CLAUDE.md 规则，一次性写对）**：`application.services.trading_day_gate.TradingDayGuard`
（打在 `orchestrator_bootstrap` / `intraday_monitor` 的同名符号上**静默失效**——T9 专门证伪这条）。

## 1. 用例矩阵（定死日期与期望）（serves: FR-1, FR-2, FR-3, FR-5）

| 编号 | 用例 | 输入 | 期望（可断言的具体值） |
|---|---|---|---|
| T1 | 休市日 · 盘中监控被拦 | `now=2026-10-06 10:30`（实测 `check('2026-10-06')` → `False / trading-calendar-holiday / degraded=False`） | ① `IntradayMonitor.check(now=…)` → `{'status':'skipped','reason':'non-trading-day'}`，且 `trading_day` 五键齐全；② `PaperTradingEngine` **未被构造**（桩计数 = 0）；③ `update_position_prices` 调用次数 = 0 |
| T2 | 交易日 · 照跑（对照） | `now=2026-09-30 10:30`（`True / trading-calendar`） | `check()` 走到既有流程（`status` ∈ {`no_positions`,`no_prices`,`completed`}），**不是** `'skipped'`；`PaperTradingEngine` 被构造 1 次 |
| T3 | 降级 · fail-open | 桩令 `TradingDayGuard.check` 返回 `degraded=True, is_trading_day=False, source='unavailable'` | `should_skip('trading-days', now)` → `(False, info)`；A 层 `_should_run_today` → `run=True`；B 层 `check()` **不**返回 `non-trading-day`；日志（若产生）含 `degraded=True` |
| T4 | 门自身异常 · 仍照跑 | 桩令 `check` 抛异常 | `should_skip` 返回 `(False, {'source':'gate-error','degraded':True,…})`；两处调用点均 **run**；不得抛出到 tick 线程 |
| T5 | 反例锁 · 未来日口径 | `TradingDayGuard.check('2026-10-07')`（今天是 10-06 → 未来） | `source == 'future'` 且 `is_trading_day is False`（锁住"未来日不得当休市日判据"；休市日用例一律取 `10-01/02/06`） |
| T6 | 编排 tick · 休市日零调用 | 桩两个 tick 函数；`now=2026-10-06 12:30` | `daily_orchestrator_tick` 调用次数 = 0；`_in_orchestrator_window(now)` 仍为 `True`（证明拦它的是**日级门**，不是时段） |
| T7 | 编排 tick · 交易日照调 | `now=2026-09-30 12:30` | `daily_orchestrator_tick` 调用次数 = 1（净效果 = 只少了休市日那 600 次） |
| T8 | 静态对账 · 唯一真源 | 读源码文本 | ① `orchestrator_bootstrap.py` 中 `should_skip` 出现次数 ≥2；② `intraday_monitor.py` 中 `weekday(` 出现 0 次；③ 两文件均**不**出现 `trading_calendar` 直查（`SELECT`/`query`） |
| T9 | 打桩点证伪 | 两个桩：一个打在 `trading_day_gate.TradingDayGuard`，一个打在 `orchestrator_bootstrap` 的同名名字上 | 前者改变结论；后者**毫无影响**（证伪"桩打错地方也以为通过"） |
| T10 | 去噪 | 连续两次调用 A 层（同一 `path` + 同一 `day`） | 跳过日志只 1 条；`day` 换成次日 → 恢复记录 |
| T11 | 窗口语义回归 | `2026-08-13 9:25/17:59` True、`7:59/18:00` False、`2026-08-15` False、`:00/:30` 节拍、`9:31` False、`12:00` False | 逐条与既有 `tests/api/test_orchestrator_bootstrap.py:20-49` 断言**完全一致**（该文件原样通过） |
| T12 | 时段优先（严格增量） | `now=2026-10-06 20:00`（休市日 + 盘后） | `check()` 返回既有 `{'status':'skipped','reason':'not trading time'}`（**不是** `non-trading-day`）——证明新分支只覆盖"原本会真干活"的时刻 |
| T13 | 通知零外发 | 跑 T1/T3/T6 | `notify-guard intercepted=N egress=0`（CLAUDE.md 口径） |

**不做的用例**（防为凑覆盖率而虚增）：不测 `TradingDayGuard` / `should_skip` 自身（②③ 已有回归；
本需求只是新调用方）；不测 `daily_orchestrator` 的阶段机（本需求不碰它）。

## 2. 可跑命令与判定（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

```bash
# 1) 本需求新增用例（唯一入口）
./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q
# 判定：全部通过；T1/T2/T3/T5 的断言打印出具体 source 与返回形状

# 2) 既有契约回归（不得有 1 条变红）
./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py \
    tests/test_market_session_policy.py tests/test_trading_window_guard.py -q

# 3) 同族三条路径的回归（②③ 的门不许被本需求带坏）
./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py \
    tests/test_daily_jobs_trading_day_gate.py -q

# 4) 静态对账
grep -c "should_skip" adapters/inbound/fastapi_app/orchestrator_bootstrap.py     # ≥2
grep -c "weekday(" application/services/intraday_monitor.py                      # 0

# 5) 真实观察（当天口径，不需重启以外的前置）
grep -c "orchestrator_trading_day_skip" logs/api.log        # 休市日 ≥1，交易日 =0
```

## 3. 真实观察窗口（验收的外部证据）（serves: FR-1, FR-3, FR-5）

| 日期 | 性质 | 期望观察 |
|---|---|---|
| `2026-10-06`（今天） | 休市（周二） | **改前基线**：`_in_intraday_window(10:30)=True`、`check()` 返回 `no_positions`、日志无跳过留痕 |
| `2026-10-07` | 休市（周三） | 日志出现 `orchestrator_trading_day_skip`（`source='trading-calendar-holiday'`）；`quant.simulation_positions` / `quant.simulation_account` 当日 `updated_at` 无监控刷新 |
| `2026-10-08` | **复市首日**（周四） | 两条路径恢复：编排 tick 照调、盘中监控走到既有流程（`status != skipped`）——**不得**被门跳过 |

- 该窗口**不可重放**（日期驱动），故 T1–T13 的单测是主证据，真实观察是**外部佐证**；
  若观察窗已过（例如实施晚于 `10-08`），须在验收材料里如实写明"窗口未取到"，
  不得用单测冒充观察（本仓「失败要响亮」纪律）。

## 4. 假绿防线（每个门都要能红）（serves: FR-3, FR-5）

| 防线 | 注入什么故障 | 期望变红 |
|---|---|---|
| 反向注入 ① | 把 `_should_run_today` 改成恒 `return True, {}` | T1/T6 红（休市日仍调用） |
| 反向注入 ② | 把 B 层日级门删掉 | T1 红（返回 `no_positions` 而非 `non-trading-day`） |
| 反向注入 ③ | 把门改成 `degraded` 也跳过 | T3/T4 红（fail-open 被破坏） |
| 反向注入 ④ | 有人在门里改用 `now.weekday()` 当判据 | T1 红（`2026-10-06` 是周二 → 会判 run） |
| 反向注入 ⑤ | 拿 `check('2026-10-07')` 当休市日判据写用例 | T5 红（`source='future'`，语义被锁死） |
