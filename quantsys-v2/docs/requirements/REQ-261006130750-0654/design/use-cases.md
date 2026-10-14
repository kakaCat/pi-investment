# REQ-261006130750-0654 · 设计：用例与场景

**读法**：每个场景写清「触发 → 期望行为 → 可核验面 → 与改前的差别」。
本设计的判定单点始终是同一句：`should_skip('trading-days', now)`。

## 1. 场景 A：休市日盘中（本次要治的病）（serves: FR-1, FR-2, FR-6）

- **触发**：`2026-10-07`（周三，国庆休市）`10:30`，编排线程第 N 轮 tick。
- **改前**：`_in_intraday_window` → `True` → 调 `check()` → 时段通过 → 取持仓（今天实测
  `rotation_main` 无持仓，止于 `no_positions`；有持仓则按冻结收盘价判止损/止盈并写
  `simulation_positions` / `simulation_account`）。同时 `daily_orchestrator_tick()` 每分钟被调一次、
  内层早退。
- **改后**：
  - `_in_intraday_window(10:30)` 仍 `True`（时段语义不变），但 A 层预过滤判 skip ⇒ **不调用**；
  - 若旁路直接调 `check(now=…)`，B 层权威门 ⇒ 返回 `{'status':'skipped','reason':'non-trading-day'}`，
    **不构造** `PaperTradingEngine`、**不读**持仓与价格、**不写**市值；
  - 编排 tick 同样在 A 层被拦，**不再**每分钟空转；
  - 留痕：`orchestrator_trading_day_skip`（两条 path 各一条/天，去噪后不刷屏），**不发通知**。
- **可核验面**：日志该事件 + `source='trading-calendar-holiday'` / `degraded=False`；
  `quant.simulation_positions` / `quant.simulation_account` 当日 `updated_at` 无监控刷新；
  盘中返回是 `non-trading-day`（而非 `no_positions`）。

## 2. 场景 B：复市首日（最怕被误跳的一天）（serves: FR-1, FR-3, FR-5）

- **触发**：`2026-10-08`（周四，假期后首个交易日）`09:30 / 12:30 / 15:00`。
- **期望**：`quant.trading_calendar` 命中该日 ⇒ `check('2026-10-08')`（**当天口径**）→
  `True / trading-calendar` ⇒ 两条路径**照常执行**：编排 tick 恢复每分钟推进、
  盘中监控走到既有流程（含 15:00 收盘那次止损/止盈）。
- **红线**：**不得**用"今天仍属未来"的口径判它（`check('2026-10-07')` 那种 `source='future'`
  在今天成立、在 `10-08` 当天自然消失）。用例 T5 把这条语义锁死。
- **可核验面**：`10-08` 当天日志**无** `orchestrator_trading_day_skip`；盘中返回 `status != 'skipped'`。

## 3. 场景 C：日历降级（数据源挂 / 覆盖断档）（serves: FR-3）

- **触发**：AKShare 不可达、或 `quant.trading_calendar` 覆盖不到当天（例如 `2027-01-04`
  这类覆盖断档日），判定链返回 `degraded=True`（`source` ∈ `weekday_fallback` /
  `unavailable` / `compute-error`）。
- **期望（fail-open）**：门判 **run**——两条路径**照跑**，绝不静默停摆；
  并留下 `degraded=True` 与来源（`TradingDayGuard` 既有响亮通道，按【日+来源】限流）。
- **为什么这样取舍**：门省的只是"一次无信息量的重算"；把它换成"日历一抖、T+1 与止损止盈全停"
  是不可接受的交换（`orchestrator_bootstrap.py:33-39` 记过同型事故）。
- **可核验面**：T3/T4 单测（桩注入降级与异常 → 均 run）。

## 4. 场景 D：旁路调用（脚本 / 其它窗口 / 将来的新调度）（serves: FR-1, FR-3）

- **触发**：有人写补跑脚本、或另一个窗口直接 `from application.services.intraday_monitor import
  get_intraday_monitor; get_intraday_monitor().check()`，在休市日跑。
- **期望**：**B 层权威门**在 `check()` 首部拦住（与 `WatchEngine.tick()` 2026-09-11 的同款做法：
  "任何旁路调用都会在盘后照样判定并推送通知 → 铁律：窗口外一律不产出事件"）。
- **可核验面**：T1（桩断言 `PaperTradingEngine` 未被构造）+ R3（调用方对账：当前唯一生产调用方
  是 `monitor_jobs.intraday_monitor_check()`）。

## 5. 场景 E：周末（既有行为，不因本需求改变）（serves: FR-4）

- **触发**：周六 `10:30`。
- **期望**：`_in_intraday_window` / `_in_orchestrator_window` 的既有 `weekday<5` 判断在**时段层**
  就返回 `False` ⇒ 两条路径都不调用（**与门无关**）。本需求**不**动这处既有语义（FR-4），
  若将来有人把它当"日级判据"用，属新需求。
- **可核验面**：T11（既有窗口断言原样通过）。

## 6. 场景 F：进程重启 / 跨日（serves: FR-1, FR-6）

- **触发**：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`（或崩溃被 `KeepAlive` 拉起），
  以及自然跨日 `23:59 → 00:00`。
- **期望**：门随代码生效，无需任何 reload/迁移；去噪状态 `_LAST_SKIP_LOG` 是**内存态**，
  重启即清（最坏后果 = 当天多一条跳过日志，无副作用）。跨日后 key 换成新一天 ⇒ 重新留痕一次。
- **可核验面**：T10（去噪）+ 重启后日志仍出现跳过年内一条。

## 7. 非目标：休市日的"人工强制"（明确不做，写清理由）（serves: FR-4）

- ② 库表调度那套有 `POST /api/scheduler/tasks/{id}/trigger`，并在 a315 的 FR-6 里明确
  "门只拦自动排班，人工仍可强制"。**④ 这条路径没有手动入口**（它是常驻线程，不是台账任务），
  本需求**不新增** `force=True` 之类的旁路参数。
- **理由**：当前没有任何调用方需要它（YAGNI）；一个"能绕过日级门"的开关本身就是新的风险面
  （谁在休市日调它，就会重演场景 A 的后果）。若真出现补检需求，应作为**新需求**评估
  （谁批、留痕到哪、怎么和 `no_positions` 区分），而不是顺手在本次加一个后门。
- **可核验面**：`grep -rn "force" application/services/intraday_monitor.py` → 0 命中（设计不含该参数）。
