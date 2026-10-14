# a3 · 只读库表事实 + 验收命令复跑

> 需求：REQ-261006010812-cd19（t3）｜ 被审设计的验收清单：`design.md` §12（7 条）与 `test-cases.md` §6。
> 执行时刻：2026-10-06 09:2x ~ 09:4x（CST）｜ 生产库 `quant_investment` **只读**；pytest 落 `quant_test`（成对测量见 §4）。
> 原始日志：`/tmp/cd19/C{1..7}.log` 与 `/tmp/cd19/summary.txt`（本机路径，非仓库内）。

## 1. 复跑总表（7 条逐条）

| # | 命令 | 实跑? | 退出码 | 输出摘要 | 设计期望 | 结论 |
|---|---|---|---|---|---|---|
| C1 | `venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py -q` | 实跑 | **0** | `36 passed in 1.42s`；`notify-guard intercepted=0 egress=0` | 全绿 | 达成 |
| C2 | `venv/bin/python tools/check_trading_day_judgment.py --dates 2026-10-05,...,2026-10-08` | **不可跑** | - | `can't open file '.../tools/check_trading_day_judgment.py': [Errno 2] No such file or directory` | 期望 False/False/False/True | **未达成**（工具不存在，见 §5-A1-6；替代判据见 §2.1） |
| C3 | `venv/bin/python tools/check_should_have_run.py` | 实跑 | **2** | `启用任务：11；漏跑：1；无法判定：0；改动豁免：10`；漏跑 = `daily-strategy-validation`（应跑 2026-10-05 21:00，实际最近 run 2026-10-02 21:02） | 退出码 0、无「应跑未跑」 | **未达成**（当前存在 1 条真实漏跑） |
| C4 | `venv/bin/python tools/check_strategy_config_effective.py` | 实跑 | **0** | `✅ 声明 == 生效`：`rebalance_days` 声明5/环境7/生效5；`top_n` 5/5/5；`single_stock_stop_loss` -0.15/-0.12/-0.15 | 退出码 0 | 达成 |
| C5 | `venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py -q` | 实跑 | **0** | `10 passed in 0.57s` | 全绿 | 达成 |
| C6 | `venv/bin/python -m pytest tests/services/test_pending_orders.py -q` | 实跑 | **0** | `28 passed, 1 warning in 2.04s` | 全绿 | 达成 |
| C7 | `venv/bin/python tools/reconcile_sim_account.py --account v13_simulation` | 实跑 | **0** | `结论：✅ 自洽（已排除 4 只已登记的脏数据）`；现金 ¥57,171.96 + 持仓 ¥75,813.00 = ¥132,984.96（累计 32.99%） | 超卖清单 **0 行** | **部分达成**：工具判 0，raw SQL 仍 4 行（§2.3） |

**汇总**：实跑 6 条、不可跑 1 条；退出码 0 的 5 条、退出码 2 的 1 条；与设计期望直接相符 **5/7**。

## 2. 关键命令明细

### 2.1 C2 的替代判据（L1 实跑，非推演）

- [L1] `venv/bin/python - <<'PY'` 调 `TradingDayGuard.check(d, use_cache=False)`：
  ```
  2026-10-05 -> False (expect False) OK | source=trading-calendar-holiday degraded=False
  2026-10-06 -> False (expect False) OK | source=trading-calendar-holiday degraded=False
  2026-10-07 -> False (expect False) OK | source=future            degraded=False
  2026-10-08 -> False (expect True ) FAIL | source=future           degraded=False
  ```
- 结论：三条休市判定**达成**；10-08 判 False，但 `source=future` —— 不是因为休市，而是因为**该日期还在未来**。
- 该现象与设计**自身**冲突：`design.md:126` 的判定顺序第 2 条明写「未来日期 → False（`SOURCE_FUTURE`）」，
  而 `design.md:135` 的定标却要求 `check('2026-10-08') == True`。**同一文档两条自相矛盾**
  （10-04 写设计时 10-08 也是未来 → 该定标当时同样无法成立）。这是 t1 未抓到的第 16 条自洽性问题，由本卡实跑暴露。
- 可用的正确判据（替代判据，已实跑）：用纯函数 `judge_trading_day(day, kline_exists_on_date=…, latest_kline_date=…, today=…, calendar_has_day=…)`
  （入参是 `datetime.date`，传字符串会 `AttributeError`）并**冻结 today**：
  ```
  pure judge 2026-10-05 -> False OK | 2026-10-06 -> False OK | 2026-10-07 -> False OK | 2026-10-08 -> True OK
  ```
  → 设计的**意图可达成**，不可达成的是「对**未来日期**直接调 `TradingDayGuard.check()`」这一写法。
  现有单测走的正是纯函数路径（`tests/live_trading/test_trading_day_judge.py:17-59`），
  其中 `test_future_weekday_is_not_trading_day` 与 design.md:135 的定标正好相反。

### 2.2 C3 的漏跑明细

- [L1] 漏跑 1 条：`daily-strategy-validation`，`cron=0 21 * * 1-5`，应跑 `2026-10-05 21:00`，实际最近 run `2026-10-02 21:02:52`。
- [L1] 另有 10 条被判「改动豁免」（其中含 `v13-simulation-trading`：因该行 2026-10-05 14:37 有 run，判为「自改动以来尚未到期」）。
- 口径提示：`2026-10-05` 是国庆休市日（`quant.trading_calendar` 无行）。盘点器按 **cron 工作日语义**推演「应跑」，
  **不查交易日历** → 休市日的排班缺失会被报成「漏跑」。这属于设计 §8 未覆盖的口径冲突（见 a4 缺口清单）。

### 2.3 C7 的双口径

- [L1] 工具口径：exit 0，结论「自洽」，做法是**排除 4 只已登记脏数据**（`config/known_dirty_simulation_data.json` +
  `notes/legacy-cash-disposition.md`，用户 2026-10-04 裁定「标记为脏并从统计排除」）。
- [L3] raw 口径（不采信排除清单）：`select symbol, sum(case when action='BUY' then shares else -shares end) … having …<0`
  → **仍有 4 行**：300045 -1000 / 300469 -200 / 300561 -700 / 300765 -300。
- 结论：设计/需求写的判据是「超卖清单必须 **0 行**」（`design.md:322`、`requirement.md:258`）；
  实际用「排他清单」把 exit code 做成了 0。**判据被替换但文档未同步** → 按原文验证的人会判失败。

## 3. 库表事实（只读，逐条带库名/语句/时刻）

- [L3] `quant_investment @2026-10-06T09:3x`｜`select id,name,command,cron_expression,misfire_grace_time_seconds,is_enabled from quant.scheduler_tasks where id in (249,257)`：
  → `249 | v13-simulation-trading | v13_daily_check | 30 14 * * 1-5 | NULL | t`；`257 | v13-daily-check | v13_trading | 30 14 * * 1-5 | NULL | f`
- [L3] 同上库｜`… where name like '%pending%' or command like '%pending%'` → **0 行**（设计 §7 的新任务行未落地）
- [L3] 同上库｜`select is_enabled,count(*),count(*) filter (where misfire_grace_time_seconds is null) from quant.scheduler_tasks group by 1`
  → 启用 11 条中 **1 条**宽限为 NULL；禁用 22 条全部 NULL（即宽限 300 秒的 10 条全在启用集合里）
- [L3] 同上库｜`select id,status,started_at from quant.scheduler_runs where task_id=249 order by started_at desc limit 6`
  → 6 条全部 `success`；最近一次 **2026-10-05 14:37:10**（休市日）；其 `result.details.details.check.status='skipped'`、`reason='not_trading_day'`
- [L3] 同上库｜`select status,count(*) from quant.scheduler_runs group by 1` → `success 2999 / failed 155 / cancelled 1`（**无 skipped、无 missed 行**）
- [L3] 同上库｜`select id,account_name,symbol,status,fail_reason,created_at,updated_at from quant.simulation_pending_orders order by id`
  → 7 行：executed 3（id 2/3/4）、failed 2（id 5/6，`fail_reason` 均为「非交易时段（16:41）…」）、expired 2（id 7/8，`fail_reason='frozen: 2026-10-04 止血 …'`）；**当前无 pending**
- [L3] 同上库｜`select account_name,cash_available,last_rebalance_date from quant.simulation_account where account_name='v13_simulation'`
  → `57171.96 | 2026-08-31`（**上次调仓停在 8/31**，此后无调仓）
- [L3] 同上库｜`select trade_date,exchange from quant.trading_calendar where trade_date between '2026-10-01' and '2026-10-09'`
  → 仅 `10-08`、`10-09` 有行（SSE/SZSE/ALL），`10-05/06/07` 无行 → 设计 §3 的事实基础成立
- [L3] 同上库｜`select count(*) from quant.simulation_trades where trade_date >= '2026-10-01'` → **0 行**（10-01 起全账户零成交）

## 4. pytest 写入面成对测量（证明只写测试库）

| 表 | 跑前 `quant_investment` | 跑后 `quant_investment` | 跑前 `quant_test` | 跑后 `quant_test` |
|---|---|---|---|---|
| `scheduler_runs` | 3155 | **3155** | 0 | 0 |
| `scheduler_tasks` | 33 | **33** | 0 | 0 |
| `simulation_trades` | 78 | **78** | 0 | 0 |
| `simulation_pending_orders` | 7 | **7** | 0 | 0 |

- [L1] 方法：计数 → `venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py -q`（`10 passed`）→ 再计数；
  生产库四表**逐字不变**，测试库四表保持 0 行（该用例集不写这四张表）。
- 结论：本审计的实跑动作未触碰生产库；D-3 边界（只读生产 + 允许跑测试）成立。

## 5. 引用有效性的现场复核（对应 t1 的 A1-6 / A1-7）

- [L1] A1-6 复核：`ls tools/check_trading_day_judgment.py` → 不存在；C2 实跑报 `[Errno 2] No such file or directory`（两条独立证据一致）。
- [L1] A1-7 复核：`git check-ignore -v tools/check_should_have_run.py` → `.gitignore:85:check_*.py`；
  `git ls-files --error-unmatch` → `pathspec … did not match any file(s) known to git`。
  即 C3/C4 这两条**实际能跑通**的判据，其实现文件不在版本控制内。

## 6. 复跑暴露的新问题（3 条，供缺口清单与改进项引用）

- [L1] **R-1（高）** 设计的 4 日期定标自相矛盾（`design.md:126` 未来→False vs `design.md:135` 要求 10-08→True）；
  实测 10-08 → False（`source=future`）。若照 design.md:135 原样写单测，**在 10-08 之前必然失败**。
- [L1] **R-2（高）** 存在 1 条真实漏跑（`daily-strategy-validation`，10-05 21:00 未跑），
  且盘点器不查交易日历 → 休市日的「未跑」会被计成漏跑，与「休市不开火」的口径未对齐。
- [L1] **R-3（中）** C7 用排他清单把「超卖 0 行」做成 exit 0，raw 口径仍 4 行；判据被替换但 `design.md:322` /
  `requirement.md:258` 未同步 → 按文档复核的人会误判为失败。

## 7. 与 a1/a2 的交叉引用

- a1 / A1-6、A1-7 ↔ 本卡 §5（引用失效的现场复核）。
- a2 / M-06、M-10、M-12、M-14、M-23 ↔ 本卡 §2.2、§3（同源事实，代码侧与库侧互相印证）。
- a2 / M-07（交易日真源已实现）↔ 本卡 §2.1：**实现正确、定标写错**——两者不矛盾。

## 8. 置信度、适用边界与被证伪假设（可执行复核）

> 全部命令在 `quantsys-v2/` 下可直接粘贴执行；本文件的原始日志在 `/tmp/cd19/C{1..7}.log`（本机路径，非仓库内）。

### 8.1 置信度分级与复核方式

| 置信度 | 本文件中的条目 | 复核命令 | 期望 |
|---|---|---|---|
| 高（L1 实跑） | C1、C5、C6、C4、C7、§2.1 替代判据、§4 计数测量 | `venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py -q; echo exit=$?`；`venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py tests/services/test_pending_orders.py -q; echo exit=$?`；`venv/bin/python tools/check_strategy_config_effective.py; echo exit=$?`；`venv/bin/python tools/reconcile_sim_account.py --account v13_simulation; echo exit=$?` | 分别：`36 passed` exit 0；`38 passed` exit 0；exit 0；exit 0 |
| 高（L1 实跑 + 结论可复现） | C3、§2.2 | `venv/bin/python tools/check_should_have_run.py; echo exit=$?` | exit **2**，摘要含 `漏跑：1` |
| 中（L3 快照） | §3 全部库证据 | 各条目已附「库名 + SQL + 时刻」；复核按同样 SQL 重跑并对照时刻 | 数值可能随时间变化，**结论方向**不得变（如 249 的 cron 仍为 `30 14 * * 1-5`） |

### 8.2 适用边界（怎么验边界本身）

- **时点边界**：库事实是 2026-10-06 09:2x–09:5x 的快照。复核前先 `select max(started_at) from quant.scheduler_runs`；若之后有新 run，C3 的漏跑计数会变化。
- **连接边界**：复核前先 `select current_database()`，必须是 `quant_investment`（生产库只读）；本文件的 §4 已证明 pytest 不会写它。
- **替代判据的边界**：§2.1 的结论只能用**纯函数**（`judge_trading_day`）+ 冻结 `today` 复现；直接对**未来日期**调 `TradingDayGuard.check()` 必然得到 `False`（`source=future`），这不是缺陷。

### 8.3 被证伪的假设 → 支撑命令

| 被证伪的假设 | 复核命令（可直接粘贴） | 期望输出 |
|---|---|---|
| 「design.md §12 的 7 条命令都能跑」 | `venv/bin/python tools/check_trading_day_judgment.py --dates 2026-10-05,2026-10-06; echo exit=$?` | `[Errno 2] No such file or directory`，exit 2 |
| 「当前不存在应跑未跑」 | `venv/bin/python tools/check_should_have_run.py; echo exit=$?` | exit 2，`漏跑：1`（`daily-strategy-validation`，应跑 2026-10-05 21:00） |
| 「超卖清单已 0 行」 | SQL `select count(*) from (select symbol from quant.simulation_trades where account_name='v13_simulation' group by 1 having sum(case when action='BUY' then shares else -shares end)<0) t` | `4`（工具口径 exit 0 是"排除已登记脏数据"后的结果） |
| 「设计 §3 定标 check('2026-10-08')==True 可满足」 | `venv/bin/python -c "from application.services.trading_day_guard import TradingDayGuard as G; v=G.check('2026-10-08', use_cache=False); print(v.is_trading_day, v.source)"`；再跑纯函数版：`venv/bin/python -c "from datetime import date; from application.services.trading_day_guard import judge_trading_day as j; print(j(date(2026,10,8), kline_exists_on_date=False, latest_kline_date=date(2026,9,30), today=date(2026,10,8), calendar_has_day=True))"` | 前者 `False future`；后者 `True`（判据须走纯函数路径） |
