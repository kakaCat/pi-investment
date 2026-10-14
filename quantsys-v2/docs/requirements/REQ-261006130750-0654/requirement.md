# REQ-261006130750-0654 · 休市日盘中空转收口：IntradayMonitor 与编排线程接入交易日门

**需求ID**: REQ-261006130750-0654
**类型**: feature
**作用域**: `quantsys-v2/`（`adapters/inbound/fastapi_app/orchestrator_bootstrap.py`、`application/services/intraday_monitor.py`、`application/services/trading_day_gate.py`（只读复用）、`tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: expert（立项弹框问答所得：需求类型 feature / 提示词难度 expert；困难点见「档位依据」）

## TL;DR

**治理报告**：休市日盘中任务空转——cron 的 `1-5` 不认节假日，「今日已空跑 27 次调度」，且伴随报错。

**核查结论（2026-10-06 下午实测）**：报告点名的那一类**大部分已在今天/昨天收口**——

```
                    v2 的四条「日级判据」路径
  +--------------------------+--------------------------+---------------------------+
  | ② 库表调度 APScheduler   | ③ DailyJobs 宿主         | ④ 编排/盘中线程（本需求） |
  | 今天 11:05 补门(a315)    | 昨天补门(2b8c)           | 门 = weekday 近似（未补） |
  | 休市日 -> skipped ✅     | 休市日 -> 不跑 ✅        | 休市日照跑 ⚠️             |
  +--------------------------+--------------------------+---------------------------+
      台账可证：261 skipped      台账可证：inprocess 0 行    台账不可见（无留痕）
```

**本需求要做的**：给剩下的第 ④ 条路径补上**同一道日级门**（复用既有唯一真源
`application/services/trading_day_gate.should_skip`）：休市日不再调用 `IntradayMonitor.check()`、
不再每分钟空调 `daily_orchestrator_tick()`；门 **fail-open**（日历降级 → 照跑）；
**复市首日不得跳过**；跳过要留痕；钱路（T+1 结转 / 止损止盈）的既有语义一行不改。

**不在本次范围（用户裁定 A）**：agent-ts 侧 `*/15 9-11,13-14 * * 1-5` 盘中决策任务（跨仓）、
今日 00:01–00:04 的 7995 条 `data_validator` 报错与 294 条回补失败（独立缺陷）。

## L1 一句话目标 + 可证伪判定标准

**目标**：v2 的两条常驻盘中线程（编排 tick / 盘中监控）改成**按真实交易日历**决定今天该不该干活，
而不是按「今天是不是周一~周五」；休市日**不发生**盘中检查与持仓市值刷新，
判定注解（`source` / `degraded` / `reason`）随留痕带出，日历降级时**照跑**。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **日期驱动单测（新增）**：**已过去或当天的**休市日（`2026-10-06`、`2026-10-01/02`，
   实测 `source='trading-calendar-holiday'` / `degraded=False`）→ 两条路径判 **skip**；
   交易日（`2026-09-30`、`2026-08-13`，实测 `source='trading-calendar'`）→ 判 **run**。
   ⚠️ **不得**拿"今天仍属未来"的 `2026-10-07` 当此判据（今天它 `source='future'`，见第 3 条）。
2. **降级单测**：桩打在 `application.services.trading_day_gate.TradingDayGuard`，
   令 `check()` 返回 `degraded=True` → 两条路径均判 **run**（fail-open），注解随留痕带出。
3. **反例锁（口径不许写反）**：断言当天口径可用——`check('2026-10-06')` → `False` /
   `source='trading-calendar-holiday'` / `degraded=False`；同时锁住
   `check('2026-10-07')` / `check('2026-10-08')` 今天 → `source='future'` 这一**写入型保守语义
   不得被当成"休市日/复市首日该不该跳过"的依据**（当日口径见 FR-5；
   休市日用例一律取**已过去或当天**的节假日，如 `2026-10-01/02/06`）。
4. **既有契约不破**：`tests/api/test_orchestrator_bootstrap.py` 的窗口断言（含
   `2026-08-13 9:25 → True`、`2026-08-15 → False`、`:00/:30` 节拍）**逐条不变**通过；
   `tests/test_scheduler_trading_day_gate.py`、`tests/test_daily_jobs_trading_day_gate.py` 全过。
5. **真实观察**：`2026-10-07`（休市）当天**没有** `intraday_monitor_check` 的实际执行留痕，
   `quant.positions.updated_at` 不因盘中监控被刷新；`2026-10-08`（复市首日）恢复正常执行。
6. **静态**：`adapters/inbound/fastapi_app/orchestrator_bootstrap.py` 里出现
   `trading_day_gate` 的调用点 **≥ 2**（两条路径各一），且**不新增**第二份日级判定实现。

## 边界

### 做什么

- 在 `orchestrator_bootstrap._monitor_loop` 的两条调用支路前加**同一道日级门**：
  复用 `application/services/trading_day_gate.should_skip('trading-days', now)`，
  与 ②③ 两条路径**同源同口径**（`trading_day_gate.py:118-153`）。
- 判「今天」一律用**当日口径**（`now` 缺省 = `datetime.now()`），永不把未来日期喂给守卫。
- 留痕：跳过时记一条 info 日志，带五键注解 `day / is_trading_day / source / degraded / reason`；
  **不发送**任何通知（跳过 ≠ 打扰）。
- 若设计阶段判定需要**内层兜底**（`IntradayMonitor.check()` 自己也看一眼日级），
  只允许调**同一份** `should_skip`，二选一由设计定稿；**禁止**在 `intraday_monitor.py`
  或 `orchestrator_bootstrap.py` 里另写一份 `weekday()` / 日历查询。
- 回归锁：新增日期驱动 + 降级 + 反例锁三类用例；既有窗口契约用例逐条保留。

### 不做什么

1. **不改** `_in_orchestrator_window` / `_in_intraday_window` 的**时段语义与签名**
   （既有契约：窗口函数表达"允许跑 tick 的时段"，日级不是它的职责；见 FR-4 与 R2）。
2. **不改** `TradingDayGuard` 的 **fail-closed** 语义，也**不改** `should_skip` 的三值策略
   （`always` / `trading-days` / `holidays`）——本需求只是**多一个调用方**。
3. **不碰钱路判据**：`daily_orchestrator.tick()`（`:133-137`）与 `resume_from_breakpoint()`（`:866-868`）
   的内层门保持原样（fail-closed）；外层新门**不得**让它们在原该跑的日子变少。
4. **不改** agent-ts 的 `*/15 9-11,13-14 * * 1-5` 盘中决策任务（跨仓，另案/另窗口）。
5. **不修**今日 `00:01–00:04` 的 7995 条 `data_validator` 报错（`检测异常值失败: cannot select elements using Sequence with elements of type 'str'`）
   与 294 条 `data_backfiller` `All data providers failed`——这是独立缺陷（异常值检测的选择器用法 + 休市日回补必失败），
   本需求只登记（E11）。
6. **不新增**台账表 / DDL / 开关；跳过只写日志，不写 `quant.*` 新状态。
7. **不做**交易日历的自动补刷（覆盖度过期属独立工作线，见 E9 与「后续线」）；
   本次只确保它**不静默**。

### 边界理由

- **为什么只加"外层门"而不动内层**：内层 `tick()` 的 fail-closed 是**钱路**要的语义
  （日历不可用 → 宁可不做）；外层职责只有"省一次无信息量的重算"，故必须 fail-open。
  两者语义相反、**刻意不同**，混成一个就会重演"日历一抖、T+1 静默停摆"的事故（
  `orchestrator_bootstrap.py:33-39` 已把该事故写进注释）。
- **为什么不把门塞进窗口函数**：窗口函数被既有测试当作纯时段函数（`tests/api/test_orchestrator_bootstrap.py:31-48`），
  塞进去等于同时改语义与契约，且会让"时段"与"日级"两件事重新纠缠。
- **为什么不做日历自动补刷**：它是"数据维护"，不是"接门"；本次范围由用户裁定为 A（见 D-2）。

## 产品定义

### 一句话

让 v2 剩下的两条常驻盘中线程**按真实交易日历**决定"今天要不要干活"——
休市日不再对冻结的收盘价跑止损止盈、不再每分钟醒来空转一次；
日历答不了的时候照跑并留下 `degraded` 痕迹；复市首日照常开火。

### 为什么现在做

1. **同类收口的最后一条缝**：②③ 两条路径今天/昨天刚补上门，只剩 ④；
   留着它，"v2 休市日不开火"这句话就**只对三条路径里的两条成立**。
2. **有实测触发证据**：今天（休市）`_in_intraday_window(2026-10-06 10:30)` → `True`，
   `IntradayMonitor.check()` 外层闸门放行（E1/E2）。
3. **不是纯成本问题，且风险随持仓出现会升级**：今天实测止步于 `no_positions`（受监控账户
   `rotation_main` 无持仓、未写库），但同一分支在有持仓账户上会按**冻结收盘价**判止损止盈、
   并写 `quant.simulation_positions` 与 `quant.simulation_account`（E3）——休市日的误触发
   会直接落成"钱路动作"。
4. **现成件齐备，缺的只是接线**：`should_skip` 已提供 fail-open + 五键注解（E6）；
   既有 ②③ 已给出写法参照；打桩点规则明确（E7）。

### 成功长什么样

- 休市日（`10-07`）：日志里**没有**盘中监控的实际执行；`quant.simulation_positions` /
  `quant.simulation_account` 的 `updated_at` 不因盘中监控被刷新（受监控账户 `rotation_main`
  当前无持仓，故同时用"返回 `non-trading-day` 而非 `no_positions`"与"写库计数为 0"两条口径核验）；
  编排线程**不再**每分钟调 `daily_orchestrator_tick()`。
- 复市首日（`10-08`）：两条路径恢复正常，止损止盈与 T+1 结转照旧。
- 日历源挂掉那天：两条路径**照跑**，日志里有 `source` / `degraded=True` / `reason`。
- 既有契约：`test_orchestrator_bootstrap.py` 的窗口断言逐条不变通过。

## 用户与角色

- **项目所有者（人类）**：判断标准是"休市日安静、复市首日照常，而且我能从日志里看出为什么安静"。
- **窗口 AI Agent（本需求实施者）**：改动集中在**一个文件的两处调用点 + 一组用例**；
  复用既有唯一真源，不发明判定器。
- **后续维护者 / 新会话**：需要一条明确规则——**"今天该不该跑"只许有一个来源**
  （`application/services/trading_day_gate.py`）；任何新线程/新定时器接日级时，
  一律调 `should_skip`，**禁止**再写 `now.weekday() < 5`。

## 功能点（G2 条款）

**FR-1: 盘中监控接日级门（休市日不调 `IntradayMonitor.check()`）**
`orchestrator_bootstrap._monitor_loop` 在满足 `_in_intraday_window(now)` 之后、调用
`monitor_jobs.intraday_monitor_check()` 之前，先过日级门；判"该跳过"时**不得调用**该函数，
并记一条 info 留痕（五键注解）。
实测依据：`_in_intraday_window(2026-10-06 10:30)` 与 `(13:00)` 均为 `True`，而当日
`TradingDayGuard.check('2026-10-06')` → `False / trading-calendar-holiday / degraded=False`（E1）。

**FR-2: 编排 tick 接日级门（休市日不再每分钟空转调用）**
同一循环里 `_in_orchestrator_window(now)` 成立时，`daily_orchestrator_tick()` 的调用同样先过日级门。
现状是"外层放行 + 内层早退"（内层见 E4），即休市日每 60 秒仍发生一次无信息量调用；
本 FR 把它变成"外层直接不调"，**且不改变内层行为**。

**FR-3: 门必须 fail-open，且复用唯一真源**
两条路径一律调 `application/services/trading_day_gate.should_skip('trading-days', now)`：
**仅当 `is_trading_day=False` 且 `degraded=False`** 才判跳过；任何降级（`weekday_fallback` /
`unavailable` / `compute-error` / `gate-error`）一律**判照跑**，并把 `day / is_trading_day /
source / degraded / reason` 带进日志。门自身异常**不得**让 tick 线程退出。
打桩点（本仓 CLAUDE.md 规则）：桩必须打在 **`application.services.trading_day_gate`**，
打在 `orchestrator_bootstrap` 里的符号上不生效。

**FR-4: 窗口语义与既有契约不回归**
`_in_orchestrator_window(now)` / `_in_intraday_window(now)` 的**签名与返回语义逐字不变**
（仍是"允许跑 tick 的时段"）；`tests/api/test_orchestrator_bootstrap.py` 的既有断言
（`2026-08-13 9:25 → True`、`17:59 → True`、`7:59/18:00/周六 → False`、`:00/:30` 节拍、
`9:31` 与午休 `12:00 → False`）**全部保持通过**；`test_start_orchestrator_calls_ticks`
（打桩两个 tick 函数并断言被调用）仍通过——若因新增门而需要在该用例里提供"今天是交易日"的桩，
属允许的最小改动，但**不得**删除或弱化其原意。

**FR-5: 判据口径锁（当日口径 · 复市首日不跳）**
门只判**当天**：`now` 缺省 `datetime.now()`，永不把未来日期喂给守卫。
"复市首日不得跳过"的验收**不得**用 `check(未来日)` 当判据（今天 `check('2026-10-08')` →
`source='future'` / `False`，那是写入型路径的刻意保守，见 E9）；须用当日口径或
`resolve_trading_day(date).date == date`。本 FR 以一条**反例锁用例**固定该语义。

**FR-6: 留痕与可观测（跳过 ≠ 静默，也 ≠ 打扰）**
跳过时记 info 日志一条，字段含 `day / is_trading_day / source / degraded / reason` 与
路径标识（`intraday_monitor` / `orchestrator_tick`）；**不发送**任何通知、不写新台账表、
不加开关。日历降级时的响亮留痕沿用 `TradingDayGuard` 既有通道（`_log_degraded_loud` /
`_alert_degraded`，每【日+来源】限流），本需求不重复造告警。

## 现状取证（2026-10-06 实测）

| 编号 | 证据 |
|---|---|
| E1 | **外层闸门按周几判日**：`adapters/inbound/fastapi_app/orchestrator_bootstrap.py:41` `return now.weekday() < 5 and 8 <= now.hour <= 17`；`:53-58` `_in_intraday_window` 用 `MarketSessionPolicy.phase_for(now.time(), is_trading_day=now.weekday() < 5)`。本机实测：`_in_intraday_window(2026-10-06 10:30) = True`、`(13:00) = True`、`_in_orchestrator_window(2026-10-06 12:30) = True`；同日 `TradingDayGuard.check('2026-10-06')` → `False / trading-calendar-holiday / degraded=False` |
| E2 | **内层日级门被硬编码为真**：`application/services/intraday_monitor.py:60` 只判 `_is_trading_time(now.time())`；`:138-150` 的 `_is_trading_time` 调 `phase_for(current_time, is_trading_day=True)`，其 docstring `:146` 自陈「日级仍由调用方（外层节拍闸门）把关，待 RFC 016 D9 统一」——而外层闸门正是 E1 的周几近似 |
| E3 | **休市日的实际后果（分"今天"与"有持仓时"两档，不许混说）**：`check()`（`:52-117`）先 `PaperTradingEngine(account_name='rotation_main')`（`paper_trading_engine.py:48` `self.repo = SimulationORMRepository()`）→ `get_all_positions('rotation_main')`（读 **`quant.simulation_positions`**，**不是** `quant.positions`）→ 实测 `rotation_main` **0 条**非零持仓（`simulation_positions` 现有 v13_simulation 4 / agent_virtual 2 / user_main_simulation 2 条），故今天每次止步于 `{'status':'no_positions'}` 早退、**未写库**。**但**同一分支一旦有持仓就继续走完：`_get_realtime_prices`（`:152-164`，读**最新日 K 收盘价、库内不联网**）→ `engine.check_stop_loss` 止损止盈 → `engine._update_position_values`（`:115` → `SimulationORMRepository.update_position_prices:928-953`，写 `simulation_positions.current_price / market_value / profit_total` 与 `simulation_account.total_value / position_value`）→ `_check_index_alert` 可能唤醒 agent |
| E4 | **编排内层本来就有门，故外层属空转**：`application/services/daily_orchestrator.py:133-137` `tick()` 首行即 `TradingDayGuard.is_trading_day(today)` 早退；`:866-868` `resume_from_breakpoint()` 同门。于是休市日 8:00–17:59 每分钟一次调用**全部空转**（今天 10:06 起进程存活） |
| E5 | **历史空跑实证（机制已明）**：`quant.daily_orchestrator_state` 存在 `trade_date = 2026-10-01 / 10-02 / 10-05` 三行（均为国庆休市），且 `PRE_MARKET` 在 `08:30` 记为 `completed`、结果里写 `data_update: stale`。说明当时"日历未覆盖 → weekday 口径放行"确实让编排器在休市日**真跑了**；今天（`quant.trading_calendar` 已覆盖到 `2026-12-31`）不再产生 `10-06` 行 |
| E6 | **唯一真源已存在**：`application/services/trading_day_gate.py:118-153` `should_skip(policy, now) -> (skip, info)`，三值策略 + fail-open（`:27-34` 说明"收益只是省一次重算，绝不能换成一次静默停摆"）；`adapters/inbound/fastapi_app/daily_jobs/gate.py` 已退化为转发壳；② 的消费点在 `infrastructure/scheduler/job_executor.py` |
| E7 | **打桩点规则**：判定在 `trading_day_gate` 模块内取值（该模块的 `TradingDayGuard` 全局名），桩打在别处**静默失效**（`daily_jobs/gate.py:7-13` 有同款说明与证伪用例） |
| E8 | **v2 台账复现不出「27 次空跑」**：今日 `quant.scheduler_runs` 仅 4 行（`232 success @00:00`、`250 success @09:25`、`259 success @09:40`——三条都在 10:05 补门**之前**；`261 skipped @10:10` 为补门后）、`quant.inprocess_job_runs` **0 行**、`quant.automation_runs` **0 行**。报告口径待对齐（已登记，见 D-1） |
| E9 | **日历覆盖度与"未来日"语义**：`quant.trading_calendar` 覆盖 `1994-03-01 .. 2026-12-31`（23373 行 / 3 交易所）；今天 `check('2026-12-31')` → `source='future'` / `False`。**覆盖一旦断档，resolver 会退化到周几口径 → 空转复发**（`2027-01-01` 起，或任何刷新断档期间）——本需求只登记、不修（见边界 7 与「后续线」） |
| E10 | **既有回归锁**：`tests/api/test_orchestrator_bootstrap.py:20-49` 逐条固定窗口语义；实测 `check('2026-08-13')` → `True / trading-calendar`（故接门**不会**打破该用例中 8-13 的 True 断言）、`check('2026-08-15')` → `False / weekend`。三类相关既有用例：`tests/test_scheduler_trading_day_gate.py`、`tests/test_daily_jobs_trading_day_gate.py`、`tests/api/test_orchestrator_bootstrap.py` |
| E11 | **不在范围的报错（登记）**：今日 `logs/api.log` `00:01–00:04` 共 **7995 条** `application.services.data_validator` error「检测异常值失败: cannot select elements using Sequence with elements of type 'str'」+ **294 条**（98×3 次重试）`data_backfiller` warning「All data providers failed」；同批「每日数据质量检查」(task 232, `policy=holidays`) 4.5 分钟内扫 5686 只、748 只有问题、回补 50 只成功 1 只，并发出一条 high 告警（`alert_count=1, delivered=true`） |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（外层加门会不会让钱路变少？）**：不会。外层门是 **fail-open**（降级照跑），内层
  `tick()` / `resume_from_breakpoint()` 的 fail-closed **一行不改**；外层只在"日历明确答休市"时拦，
  而这种日子内层今天也会早退——净效果是**少了空调，不少真实执行**。
- **R2（为什么不干脆改进窗口函数）**：窗口函数是既有测试的契约面（E10），
  且它表达的是"时段"而非"日级"；塞进去会让两件事重新纠缠，并使 `_in_intraday_window` 的
  `phase_for(is_trading_day=...)` 需要外部注入日级结论、签名被迫改变。故取"调用点加门"。
- **R3（外层的漏网风险）**：`IntradayMonitor.check()` 的生产调用方只有
  `infrastructure/jobs/monitor_jobs.intraday_monitor_check()`（`monitor_jobs.py:21-24`），
  而它的唯一生产调用点就是 `orchestrator_bootstrap.py:71`；`IntradayMonitor()` 单例见
  `intraday_monitor.py:271`。若设计阶段发现新的旁路调用方，须一并纳入（FR-1 的验收含静态对账）。
- **R4（跳过会不会掩盖真问题）**：休市日跳过只是"不做无信息量的重算"；若某天确实需要补数据，
  该走 `evening_pipeline` 的 K 线段（2b8c 已刻意保留）与人工触发，不靠这两条线程兜底。

## 接口与数据契约

- **对外接口**：无新增/变更（无 HTTP 路由、无 API 契约、无 CLI）。
- **内部契约**：
  - `_in_orchestrator_window(now: datetime) -> bool`、`_in_intraday_window(now: datetime) -> bool`：
    **签名与语义不变**（FR-4）。
  - 新增（建议，名称由设计定）**薄封装**：在 `orchestrator_bootstrap` 内定义
    `_should_run_today(now) -> tuple[bool, dict]` 之类，内部**只调**
    `application.services.trading_day_gate.should_skip('trading-days', now)`；
    不得在模块内出现第二份日历/星期判定。
  - **不新增**台账表、**不新增**列、**不新增**环境开关；跳过只写日志。
- **数据契约**：读 `quant.trading_calendar`（既有，`is_trading_day IS NOT FALSE`）；
  不写任何 `quant.*` 新状态。
- **兼容/回滚**：纯代码路径改动，无迁移；回滚 = 还原 commit（门移除后行为与现在一致）。

## 判定标准（可跑）

> 命令均在本仓根目录、用 `./venv/bin/python` 执行；新增用例文件名在拆分阶段定稿
> （建议 `tests/api/test_orchestrator_trading_day_gate.py`）。

1. **日期驱动 + 降级 + 反例锁**：
   `./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q` → 全过。
   覆盖：休市日 `2026-10-06`、`2026-10-01/02` → skip；交易日 `2026-09-30`、`2026-08-13` → run；
   `degraded=True` → run 且注解完整；反例锁 `check('2026-10-07').source == 'future'`
   （未来日不得充当休市日判据）。
2. **既有契约**：
   `./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py tests/test_scheduler_trading_day_gate.py tests/test_daily_jobs_trading_day_gate.py -q` → 全过。
3. **静态对账**：
   `grep -c "trading_day_gate" adapters/inbound/fastapi_app/orchestrator_bootstrap.py` → ≥ 2；
   `grep -rn "weekday()" application/services/intraday_monitor.py` → 0 命中（该文件不得自带日级判定）。
4. **真实观察**：`2026-10-07`（休市，**当天**口径下 `source` 应为 `trading-calendar-holiday`）
   日志中检索 `intraday_monitor` 跳过留痕，且 `quant.simulation_positions` /
   `quant.simulation_account` 当日 `updated_at` 无监控刷新（**对照今天**：同日返回的是
   `no_positions`，改后应为 `non-trading-day`）；`2026-10-08`（复市首日，当天口径）恢复执行。
5. **通知守卫**：相关用例运行时 `notify-guard intercepted=N egress=0`（本仓 CLAUDE.md 口径）。

## 档位依据与升级信号

- **档位 = expert**：立项弹框由用户作答（feature / expert，见 D-1 记录）。
  实质难点有三：① 两条路径语义相反（外层 fail-open、内层 fail-closed）必须同时成立；
  ② 判据口径存在"未来日 vs 当日"陷阱（E9/FR-5），写反会把好代码判成 bug；
  ③ 真实观察窗口有限且不可重放（`10-07` 休市 / `10-08` 复市首日），须当天取证。
- **升级/降级信号**：若设计阶段发现"内层兜底"不可避免（例如出现第二个生产调用方），
  范围从"加一道门"升级为"给 `IntradayMonitor` 引入日级依赖注入"，须在设计文档里显式登记。

## 后续线（本次不做，仅登记）

1. **agent-ts 盘中决策任务**：`agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts:165`
   `scheduleExpr: '*/15 9-11,13-14 * * 1-5'`（注释已记录过一次同类治理：跳过 12–13 点午休空跑）。
   跨仓，需在 agent-ts 侧立项。
2. **交易日历覆盖度自动补刷**：`quant.trading_calendar` 覆盖到 `2026-12-31`（E9）；断档即
   退回周几口径 → **空转复发**。`tools/refresh_trading_calendar.py` 是手工工具，未见排班。
3. **今日 00:01–00:04 的报错风暴**（E11）：`data_validator` 的 pandas 选择器用法 + 休市日回补必失败，
   独立缺陷，另案。
4. **「27 次空跑」报告口径对齐**（E8）：请报告来源方给出统计口径与数据源，落到哪个台账/日志。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 本窗口会话消息（2026-10-06，用户直接消息）原话：「【治理建议】休市日盘中任务空转：cron 的 1-5 不认节假日（今日已空跑 27 次调度）报错了，需要你优化一下」 | 立项治理（feature / expert）；「27 次空跑」在 v2 台账**复现不出**，登记为待对齐项，**不据此扩大范围** | FR-1、FR-2 | 立项弹框问答所得 category=feature / prompt_difficulty=expert（REQ-261006130750-0654 已创建并绑定本窗口）；台账计数见 E8（`scheduler_runs` 4 行 / `inprocess_job_runs` 0 行 / `automation_runs` 0 行） |
| D-2 | 本窗口会话消息（2026-10-06，用户回答范围弹框）原话：「A. v2 剩余盘中路径接门：orchestrator_bootstrap 的 _in_orchestrator_window / _in_intraday_window（含 IntradayMonitor 日级判定）（推荐）」 | 范围收口到 ④ 路径（编排 tick + 盘中监控）；agent-ts 侧盘中决策任务与今日 `00:01–00:04` 的报错**不入本次范围**，仅登记 | FR-1、FR-2、FR-3 | `ask_user_question` 返回 `selected=["A. …"]`（单选）；排除项落账见「后续线」第 1 条与第 3 条、边界「不做什么」第 4/5 条 |

## 下一步

**design** —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 请人确认本需求文档；
获确认后 `reqboard_move` 到 design，把设计写进 `docs/requirements/REQ-261006130750-0654/design/`。
（本节点不建任务卡、不写设计。）

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-37a691、t-45c620、t-22d1ba |
| FR-2 | ✅ 已接收 | t-bcbe54、t-45c620 |
| FR-3 | ✅ 已接收 | t-37a691、t-bcbe54、t-45c620、t-22d1ba |
| FR-4 | ✅ 已接收 | t-bcbe54、t-45c620 |
| FR-5 | ✅ 已接收 | t-37a691、t-45c620、t-22d1ba |
| FR-6 | ✅ 已接收 | t-37a691、t-bcbe54、t-45c620 |

> 无未接收条款（6 条全部有落点）。

<!-- reqboard:marks:end -->
