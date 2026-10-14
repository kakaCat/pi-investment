---
title: 应有交易日与新鲜度判定
type: architecture
tags: [trading-calendar, freshness, health-probe, data-contract, daily-jobs]
updated: 2026-10-05
---

# 应有交易日与新鲜度判定（QuantSys V2）

**来源**：[REQ-261004102115-d3de](../requirements/REQ-261004102115-d3de/requirement.md)（2026-10-04）；
调度侧的门见 [REQ-261005203907-2b8c](../requirements/REQ-261005203907-2b8c/requirement.md)（2026-10-05）

## 一句话

「哪天该有数据」在本仓**只有一个口径**：`application/services/trading_day_resolver.py` 的
`last_closed_trading_day()`（语义 = 最近一个**已收盘**的交易日）；任何新鲜度判定都必须问它，
不要再自己写 `weekday()`。

## 事故与根因（2026-10-04）

外部健康探针报「K 线最新 2026-09-30 / 应有 2026-10-02，滞后 2 天」，每 5 分钟一次。
真相：A 股 10-01~10-07 国庆休市（上证公告〔2026〕22 号），**下一交易日是 10-08**，
09-30 就是当下最新的真实交易日——**数据完好，判据错了**。

根因：`daily_jobs/pipeline.py:_last_trading_day` 是「周末排除法；节假日由告警人工复核」，
国庆休市日被当成交易日；探针复用了它，进程内的 `freshness_guard` 也复用了它——
**同一根因两个出口**。

## 唯一口径（改代码前先读这段）

```
anchor = ref 时刻 >= 15:30 ? ref.date() : ref.date() - 1 天
结果   = 交易日历中 <= anchor 的最大交易日
```

三级解析，逐级降级（除入参类型外**不抛异常**）：

| 级 | 源 | 何时用 |
|---|---|---|
| ① | `quant.trading_calendar` 表 | 离线、快；**要求 `max(trade_date) >= anchor`**（表不覆盖 anchor 时它无权判断） |
| ② | `DataProviderManager.get_trading_calendar()`（AKShare） | 表不可答时；这是唯一能给出**未来交易日**的源 |
| ③ | 周一~周五回退 | 前两级都不可用——**必须把 `degraded=True` 带出去** |

**降级必须响亮**：探针 JSON 有 `expected_source` / `expected_degraded`，告警正文在降级时追加
「交易日历不可用，按工作日口径判定」；巡检 result 亦有 `expected_source`。
休市期若日历全挂，读告警的人要能一眼看出"这条判定可信度更低"——否则误报会以"看起来正常"的样子回来。

## 谁在用这个口径

| 调用方 | 位置 | 说明 |
|---|---|---|
| 外部健康探针 | `tools/health_probe.py` `expected_trading_day()` | 输出契约新增两个键（增量，既有键不变） |
| 进程内新鲜度巡检 | `adapters/inbound/fastapi_app/daily_jobs/pipeline.py` | `_last_trading_day()` 保留原名与签名（40+ 导入方），内部转发 resolver |
| 数据契约检查器 | `tools/check_data_contracts.py:compute_expected_trading_day()` | **同一语义的第三个实现，尚未合并**（它自带 `holiday_slack_weekdays` 冗余，实测未误报） |

## 运维：日历表要保鲜

`quant.trading_calendar` 由 `tools/refresh_trading_calendar.py` 灌入，真源 = **K 线 DISTINCT 日期 ∪ AKShare 官方日历**
（前者给历史深水区，后者给未来交易日；只用 K 线会让表"刚填好就过期"）：

```bash
./venv/bin/python tools/refresh_trading_calendar.py            # 幂等，可反复跑
./venv/bin/python tools/refresh_trading_calendar.py --dry-run  # 先看会写多少
```

- 主键 `(trade_date, exchange)`，只写 TRUE/FALSE、不写 NULL；
- **未加排班**（属调度层决定）：表一旦不覆盖 anchor，探针每次运行都会走一次 provider；
- 填表有一个**连带影响**：`data_pipeline_service.load_trading_calendar_from_db(exchange)` 从
  「空表 → 回退 K 线 + error 日志」变为「直接读表」——这正是该函数注释要求的方向，回退路径未改。

## 调度侧：休市日不再开火（2026-10-05 · REQ-261005203907-2b8c）

上面解决的是「**哪天该有数据**」；这一节解决「**今天该不该跑这件活**」。

**背景**：DailyJobs 宿主的排班只认工作日（`registry.py` 的 `weekdays`），不认识法定节假日——
2026-10-05（国庆休市）实测 6 个任务照跑：`pool_daily_refresh` 空跑 22.1 秒还发了「开始/完成」
两条飞书；`evening_pipeline` 的 K 线段已自证新鲜跳过，**因子段仍对着 09-30 的冻结快照
全市场重算 50+ 分钟**。

**做法**：任务级交易日门。

| 件 | 位置 | 要点 |
|---|---|---|
| 门 | `adapters/inbound/fastapi_app/daily_jobs/gate.py` | 判据**唯一**：`skip = (not is_trading_day) and (not degraded)`；三个入口 `skip_non_trading_day` / `is_non_trading_day` / `verdict_info`；**永不抛**（自身异常 → 判「照跑」+ `source='gate-error'`） |
| 标志 | `daily_jobs/defs.py` 的 `JobDef.trading_days_only` | 追加在**末位带默认值**（仓内多处按位置参数构造 JobDef） |
| 整段跳过 | `daily_jobs/runtime.py` `_run_job` | 早退点**必须在「开始」通知之前**：写 `status='skipped'` + `result.{skipped,reason,trading_day}`；**不发通知、不观测 duration** |
| 局部跳过 | `daily_jobs/pipeline.py` `_job_evening_pipeline` | 判据是「**非交易日 且 K 线本次无更新 且 非 error**」——交易日一律照跑 |

**钉死的三条取舍**（改这块之前先读）：

1. **门是 fail-open，与钱路任务的 fail-closed 刻意相反**：`TradingDayGuard` 对钱路任务是
   保守判非交易日（见 `orchestrator_bootstrap.py:33` 的教训），而本门的收益只是"省一次无信息量的
   重算"——**任何降级（`weekday_fallback` / `unavailable` / `compute-error`）一律照跑**，
   最坏退化为改动前的行为；降级事实必须写进 `result.trading_day` 并记 warning，**不许静默**。
2. **`evening_pipeline` 只跳因子段，K 线段必须留**：K 线段是休市日**唯一的缺口修复路径**
   （覆盖度不足时它才会真的同步）；因子段只在"K 线本次无更新"时才跳过——
   反过来，休市日若 K 线段**真的修了数据**（`success>0`），因子段照跑，避免留下因子空洞。
   ⚠️ **不许**用"K 线段是否 `skipped`"单独判定因子段：交易日若 K 线已由别的路径同步过，
   `kline_sync` 同样是 `skipped`，但当日因子还没算——那样写会在**正常交易日漏算因子**。
3. **跳过要留痕、且与"根本没跑"可分**：`quant.inprocess_job_runs.status` 多一个取值
   `'skipped'`（列是 `text`、无 CHECK 约束 ⇒ **零 DDL**）。`is_due` 对未知状态落 `False`
   （当天不重跑）、`catchup_due` 只看 `failed`（不补跑）、`trigger_job` 不因 `skipped` 拒绝
   （人工仍可触发，但休市日语义仍成立）。

**回滚**：撤掉 `registry.py` 里 3 处 `trading_days_only=True` 与 `pipeline.py` 的因子段判定，
重启服务即可；已产生的 `skipped` 行**无需清理**（无消费者把它当异常态）。
**生效前提**：门跑在宿主线程里 ⇒ **必须重启进程**（`launchctl kickstart -k gui/501/com.pi-investment.v2-api`）。

**实测记录**：[需求档案的观察记录](../requirements/REQ-261005203907-2b8c/notes/holiday-observation.md)（含改造前基线与复跑命令）。

## 库表调度侧：同一道门补到第二条路径（2026-10-06 · REQ-261006093620-a315）

上一节只修了 ③ **DailyJobs**；② **库表调度**（APScheduler，读 `quant.scheduler_tasks`）**一直没有门**——
2026-10-06（国庆休市·周二）09:25 实测 `pre-market-scan` 照常开火并记 `success`（`run_id=3379`、129ms）。

**做法**：判据上移 + 任务级策略列 + **门落在执行期**。

| 件 | 位置 | 要点 |
|---|---|---|
| 判据真源 | `application/services/trading_day_gate.py` | `should_skip(policy, now)`；两条路径**共用这一份**（③ 的 `daily_jobs/gate.py` 退为**纯转发壳**）。理由：`infrastructure/` 不能反向依赖入站适配器目录 |
| 策略列 | `quant.scheduler_tasks.trading_day_policy` | **三值**：`always`（缺省＝行为不变）/ `trading-days`（非交易日一律跳）/ `holidays`（**只跳法定节假日、周末照跑**）。8 条吃当日行情的任务挂门，3 条不吃的不挂 |
| 执行期门 | `infrastructure/scheduler/job_executor.py` `_execute_scheduled_job_impl` | 门插在 `is_enabled` 之后、**并发检查之前**；跳过时 `create_run` + `complete_run_skipped` 后 `return`（不执行命令、不发通知、`last_error` 为空） |
| 人工旁路 | `apscheduler_service.trigger_task_now` | 改为投递**一次性** `DateTrigger` job 并带 `manual=True`；执行期见 `manual` 就**不判门**。旧实现 `modify_job(next_run_time=now)` 与自动到点同路径、无法区分，还会提前排期吞掉当天正常排班 |
| 台账三态 | `scheduler_repository.complete_run_skipped` | `status='skipped'`（`text` 列无 CHECK ⇒ **零 DDL**）；`_finish_run` 是 success / failed / skipped **共用的唯一收尾** |

**为什么门放执行期而不是排班期**（这是本节最值钱的一条）：执行期判定**改一行策略即生效、
无需 `POST /api/scheduler/reload`**，天然绕开「DB 改了但 jobstore 持旧 job」那族坑
（实证：任务 250 曾 `is_enabled=false` 仍每天触发 15 天，只有显式 reload 才摘掉）。

**`skipped` ≠ `missed`（极性相反，别读反）**：

| status | 谁写 | 语义 | 该不该告警 |
|---|---|---|---|
| `skipped` | 交易日门（本需求） | 按日历**本就不该跑**（正常） | **不告警**、也不算"真执行" |
| `missed` | APScheduler 超宽限跳过 | **该跑没跑**（异常） | **告警** |

`should_have_run.py` 为此把状态拆成两套**写出来的**常量：`HANDLED_STATUSES`
（success/failed/**skipped**，判"该槽位是否已处理"）与 `REAL_RUN_STATUSES`（success/failed，
呈现"最近一次真执行"）。**靠 `!= 'missed'` 的副作用会在休市日刷出"漏跑"假警。**

**四条钉死的取舍**（改这块之前先读）：

1. **未知策略 fail-open**：写库侧有 CHECK 约束，运行时仍读到未知值 ⇒ **照跑** + `policy_unknown`
   + warning（最坏＝多跑一次，绝不静默停摆）；2. **降级不许静默**：降级照跑时 result 必须带
   `trading_day_gate{source,degraded,policy}` 并记 warning（含 `task_id`）；
3. **跳过记账失败不许影响调度**：`create_run`/`complete_run_skipped` 自兜底，失败只记 error、
   **仍不执行**命令、不外抛到调度线程；4. **门只拦自动到点**：人工触发永远照跑（`manual=True`）。

**回滚**：把 8 行 `trading_day_policy` 改回 `'always'` 即恢复原行为——**无需 DDL、无需 reload、
无需重启**（门在执行期读 DB）；列可长期保留。
**生效前提**：进程仍须**重启一次**以加载新代码（`launchctl kickstart -k gui/501/com.pi-investment.v2-api`），
之后策略改动才免重启。

**实测记录**：生产 `run_id=3381 chan-scan-daily` @ 2026-10-06 10:10（休市日）→ `skipped`、
`error=NULL`、`source=trading-calendar-holiday`；同路径改造前为 `success`
（[需求档案](../requirements/REQ-261006093620-a315/notes/acceptance-run.md)）。

## 常驻线程侧：第 ④ 条路径也补上门（2026-10-06 · REQ-261006130750-0654）

②③ 之外还有**两条常驻线程**在按日循环，它们此前用**周几**近似判日：

| 线程 | 循环 | 改前行为 | 改后 |
|---|---|---|---|
| 编排 tick | `orchestrator_bootstrap._monitor_loop`，工作日 8:00–17:59 **每 60 秒** | 休市日**每分钟空调一次**（内层 fail-closed 早退） | 休市日**零调用** |
| 盘中监控 | 同一循环，`:00/:30` | 休市日**真跑** `IntradayMonitor.check()`：取持仓 → 读最新日K → 判止损止盈 → 写持仓市值 | 休市日**不调用**；旁路直调返回 `non-trading-day` |

**落点（两层，判据同一份）**：
1. **A 层（循环预过滤）** `orchestrator_bootstrap._should_run_today(now, path=...)`：内部**只调**
   `application/services/trading_day_gate.should_skip('trading-days', now)`；跳过时按 `(path, day)`
   去噪记一条 `orchestrator_trading_day_skip`（编排线程休市日会命中 600 次/天，逐次刷屏会淹没留痕）。
2. **B 层（被调用方权威门）** `IntradayMonitor.check()` 首部：**在既有时段判定之后**插同一道门
   （严格增量：新分支只覆盖"原本会真干活"的时刻），命中即返回
   `{'status':'skipped','reason':'non-trading-day','trading_day':{五键}}` ——
   **不构造 `PaperTradingEngine`、不读持仓/价格、不写市值**。为什么两层都要：旁路调用
   （补跑脚本 / 其它窗口）绕过循环时，B 层是唯一闸门（与 `WatchEngine.tick()` 2026-09-11 的做法同型）。

**四条硬规则**（与本页其余部分一致，但载体不同）：

1. **窗口函数只表达"时段"，不表达"日级"**：`_in_orchestrator_window` / `_in_intraday_window`
   里的 `weekday()` 是**时段语义**（与原 daemon 的 `hour='8-17'` 对齐），日级一律交给那道门；
   不要为了"支持节假日"去改窗口函数（会同时改语义与既有测试契约）。
2. **外层 fail-open、内层 fail-closed 刻意相反**：外层门只省一次无信息量的重算，任何降级
   （`weekday_fallback` / `unavailable` / `compute-error` / `gate-error`）一律**照跑**；
   内层 `daily_orchestrator.tick()` / `resume_from_breakpoint()` 保持 fail-closed（钱路语义）。
   **不要**用 fail-open 去覆盖内层。
3. **重启会多一条跳过日志**：去噪键是**内存态**，进程重启即清 ⇒ 同一休市日会出现两条
   （实测：13:21:44 与 13:48:32 各一条 `orchestrator_tick`）。这是设计内的"最坏多一条"，不是漏去噪。
4. **循环按线程启动时刻对齐 60 秒节拍**：`13:30` 槽位实际在 `13:30:4x` 判定——查留痕别在 `:00:05` 就判"没生效"。

**实测记录（2026-10-06 休市日）**：`orchestrator_trading_day_skip` 4 条（13:21:44 / 13:30:46 /
13:48:32 / 14:00:33，均 `source=trading-calendar-holiday` `degraded=false`）；
`quant.simulation_positions` 最新仍为 `2026-10-04`、`daily_orchestrator_state`（10-06）0 行
（[观察档](../requirements/REQ-261006130750-0654/notes/holiday-observation.md)）。

**已知残留（未修，改前先读）**：
- `resume_from_breakpoint()` 仍 fail-closed ⇒ **日历覆盖断档**（`quant.trading_calendar` 只到 `2026-12-31`）
  时，休市日仍会跑——修它要动日历自动补刷（本页「运维：日历表要保鲜」一节），不是加一道门能解决的。
- `application/services/scheduler_tasks_runtime.py::handle_intraday_monitor` 会把 `check()` 的
  `skipped` 包成外层 `status='success'`——**假成功形态**（与 a315 治过的同型）；当前无启用任务接线，
  接线前须先把 `result.status` 上提。


## 改这块代码时的硬规则

1. **不要新增第二份 `weekday()` 判定**：新需求一律调 `last_closed_trading_day()`；
2. **不要静默降级**：任何降级都要能被外部看见（字段或日志）；
3. **打桩点跟着接缝走**：测试打桩要打在**被调函数所在模块**——
   本仓已因"名字还在但不再被读"栽过四次（最近一次就是 `test_freshness_guard.py` 打在转发壳
   `pipeline._last_trading_day` 上）；
4. **休市日空跑同步：已定案「只跳因子段」**（2026-10-05 · REQ-261005203907-2b8c）——
   `evening_pipeline` 的 `kline_sync` **保留**（它是休市日唯一的缺口修复路径），
   因子段才在"非交易日 且 K 线无更新"时跳过；`pool_daily_refresh` / `chip_distribution` /
   `evolution_fitness` 三个吃当日行情的任务休市日**整段跳过**（详见上一节）。
5. **不要再造第二个交易日门**：新任务要"只在交易日跑"，③ 走 `JobDef.trading_days_only=True`，
   ② 走 `quant.scheduler_tasks.trading_day_policy`——两者都指向**同一份判据**
   `application/services/trading_day_gate.py`；不要在自己的 handler 里写 `weekday()` 或直调 `TradingDayGuard`。
6. **台账里 `skipped` 与 `missed` 极性相反**：新增消费者前先问"它该把哪一个当异常"
   （详见上文「`skipped` ≠ `missed`」）；判漏跑请用 `HANDLED_STATUSES` / `REAL_RUN_STATUSES` 两套常量，
   别写 `status != 'missed'` 这种副作用判据。
7. **策略改动是热生效、代码改动不是**：改 `trading_day_policy` 立即生效（执行期读库）；
   改门/执行体代码必须重启进程。别在文档或运维脚本里把两者说成同一件事。

## 回归锁在哪

- `tests/test_trading_day_resolver.py`（13 条）：日期表驱动 + 三条降级路径 + 类型守卫；
- `tests/test_health_probe.py`（5 条）：探针判定与来源标注（含"降级才标注"的双向锁）；
- `tests/e2e/test_health_probe_e2e.py`（2 条）：按 launchd 的真实入口跑整条链，断言可观察终态。
- `tests/test_scheduler_trading_day_gate.py`（21 条）：**策略真值表**（14 行）+ `future` 反例锁 + 兜底与兼容；
- `tests/infrastructure/test_scheduler_skip_ledger.py`（8 条）：执行期接门的 N1/N2/N4 负向断言、
  `manual` 旁路、降级留痕、跳过记账失败不外抛；
- `tests/infrastructure/test_scheduler_run_skipped_ledger.py`（8 条）：仓储三态收尾（假会话 + 一次真库往返）；
- `tests/test_daily_jobs_trading_day_gate.py`（28 条）：③ 语义不回归 + **转发壳的证伪断言**
  （桩打错模块会被发现）；
- `tests/test_should_have_run.py`（31 条）：两套状态集、门跳过不算漏跑、`missed` 仍告警。
- `tests/api/test_orchestrator_trading_day_gate.py`（12 条）：**第 ④ 条路径**（编排 tick / 盘中监控）——
  休市日零调用、交易日对照、降级 fail-open、门自身异常照跑、未来日反例锁、
  `(path, day)` 去噪、窗口语义不回归、时段优先、**打桩点证伪**（桩打在调用方只影响该模块）、静态唯一真源。
  配套 `tests/api/test_orchestrator_bootstrap.py` 6 条（接线与线程存活，按需补「今天是交易日」桩）。
