# REQ-261006130750-0654 · 设计：数据层与契约

**结论先行（一句话）**：**本需求零 DDL、零迁移、零新表、零新列、零新开关**；
数据侧的唯一变化是**减少写入**——休市日不再刷新 `quant.simulation_positions` /
`quant.simulation_account`。判据读取的是既有 `quant.trading_calendar`（只读，口径不变）。

## 1. 是否改表 / 改 schema（serves: FR-1, FR-2, FR-6）

| 问题 | 答案 | 依据 |
|---|---|---|
| 新增表 / 列？ | **否** | ④ 路径没有运行台账表（不像 ② 有 `quant.scheduler_runs`）；留痕走日志（FR-6） |
| 需要迁移脚本？ | **否** | 无 schema 变更，故无 `infrastructure/persistence/migrations/*` 新增 |
| 需要回填历史？ | **否** | 不改变任何历史行的语义；历史空跑记录（E5）保留原样，不做"追认" |
| 需要新开关 / 配置？ | **否** | 行为随代码生效；开关会引入"关掉就复发"的隐性风险（FR-6） |
| 有 DDL 回滚动作？ | **不需要** | 回滚 = 还原代码（见 §6） |

## 2. 读契约：`quant.trading_calendar`（只读，沿用既有口径）（serves: FR-3, FR-5）

判定链在本需求中**只经由** `TradingDayGuard.check(now)`，本设计不直接查表、也不新增查询。

| 项 | 值（实测 2026-10-06） |
|---|---|
| 表 / schema | `quant.trading_calendar` |
| 主键 | `(trade_date, exchange)` |
| 语义 | **只存交易日**（无 `is_trading_day=false` 行）；查询口径 `is_trading_day IS NOT FALSE`（NULL 视为交易日） |
| 覆盖区间 | `1994-03-01 .. 2026-12-31`（23373 行 / ALL·SSE·SZSE） |
| 覆盖判定 | `max(trade_date) >= anchor` 才算"能回答"；否则降级（`trading_calendar_not_covering`） |
| 本需求对它的写 | **无**（不刷新、不补数据；补刷属后续线 E9） |

**覆盖度是本设计的已知外部风险**（E9）：覆盖一旦断档，判定链退化到"周几口径" ⇒
休市日又会照跑。本设计**不修**它，只保证此时**响亮**（`TradingDayGuard` 既有
`_log_degraded_loud` + `_alert_degraded`，按【日+来源】限流），且门**照跑不静默停摆**。

## 3. 写契约：本需求**减少**哪些写入（serves: FR-1）

休市日被拦下后，下面这些原本会发生的写入**不再发生**（当前受监控账户 `rotation_main`
无持仓，故今天实测止步于 `no_positions`；本表描述的是"有持仓时的能力面"，E3）：

| 表 | 列（`SimulationORMRepository.update_position_prices:928-953` 会写） | 休市日改后 |
|---|---|---|
| `quant.simulation_positions` | `current_price` / `market_value` / `profit_total` / `profit_total_rate` / `updated_at` | **不写** |
| `quant.simulation_account` | `position_value` / `total_value` /（随附的收益率字段） | **不写** |

- 本需求**不新增任何写入**：跳过路径只写日志（进程 stdout / `LOG_FILE` 轮转），不落库。
- `quant.positions`（14 行）**与本路径无关**——`PaperTradingEngine` 用的是
  `SimulationORMRepository`（`quant.simulation_positions`），E3 已改正。

## 4. 跳过态的三态语义（定死，避免"跳过"与"没跑"混淆）（serves: FR-6）

④ 路径没有台账表，故用**函数返回 + 日志**两个可核验面表达状态：

| 状态 | 触发条件 | `IntradayMonitor.check()` 返回 | 日志 | 与"根本没跑"可区分？ |
|---|---|---|---|---|
| `not trading time`（既有） | 时段外（午休 / 盘后） | `{'status':'skipped','reason':'not trading time'}` | 无（既有行为） | ✅（有返回/可观察） |
| `non-trading-day`（**新增**） | 日历明确答休市 | `{'status':'skipped','reason':'non-trading-day','timestamp':…,'trading_day':{五键}}` | `orchestrator_trading_day_skip`（A 层，按 path+day 去噪） | ✅ |
| `no_positions` / `no_prices` / `completed`（既有） | 交易日正常流程 | 原样 | 原样 | ✅ |

**编排 tick 侧**：跳过**没有返回值**可看（函数返回 `None`），故其可核验面**只有日志**
（`orchestrator_trading_day_skip`，`path='orchestrator_tick'`）。这是 ④ 路径没有台账表的
直接代价，本设计接受（不为此新建表——那会平白引入一次 DDL 与一套消费者矩阵）。

## 5. 日志字段契约（可被 grep / 巡检消费）（serves: FR-6）

| 事件名 | 级别 | 字段 | 类型 / 取值 | 备注 |
|---|---|---|---|---|
| `orchestrator_trading_day_skip` | `info` | `path` | `'orchestrator_tick'` \| `'intraday_monitor'` | 受控二值 |
| | | `day` | `YYYY-MM-DD` | 判定对象日 |
| | | `is_trading_day` | bool | 降级路径可能为 `False` 但 `degraded=True` |
| | | `source` | str（`trading-calendar` / `trading-calendar-holiday` / `weekend` / `future` / `weekday_fallback` / `unavailable` / `compute-error` / `gate-error`） | 与 ②③ 同值域 |
| | | `degraded` | bool | `True` ⇒ 必然**照跑**（此事件不会出现） |
| | | `reason` | str ≤200 | 直接取 `info['reason']` |

- **去噪键**：`(path, day)`——同一键只留一条（编排线程休市日会命中 600 次/天，盘中 10 次/天）。
- **不发通知**：跳过路径对 `NotificationFacade` / 飞书 / agent 消息**零调用**；
  用例以 `tests/notify_guard.py` 的 `egress=0` 见证（CLAUDE.md 口径）。

## 6. 迁移、兼容与回滚（serves: FR-1, FR-2, FR-3, FR-4）

- **兼容性**：`IntradayMonitor.check()` 新增**可选**入参 `now`（缺省 `datetime.now()``），
  既有调用方（`monitor_jobs.intraday_monitor_check()`）**一字不改**；既有返回形状除"休市日"
  这一新分支外逐字保留。
- **生效方式**：随进程重启（两条线程由 FastAPI lifespan 启动）；无 jobstore、无 reload 步骤
  （与 ② 的"DB 改了还要 reload"不同）。
- **可观测生效证据**：改后休市日日志出现 `orchestrator_trading_day_skip`；
  盘中返回由 `no_positions` 变为 `non-trading-day`（对照面清晰）。
- **回滚步骤**：还原 `orchestrator_bootstrap.py` / `intraday_monitor.py` / 用例文件；
  **无需**改库、无需清数据、无需重放。
- **部分回滚**：A 层与 B 层互相独立（architecture.md §8），可各自单独还原。

## 7. 数据侧的不变量（实施与验收都不许破坏）（serves: FR-3, FR-5）

1. 交易日与降级日的**写入集合与门装之前完全相同**（不许因门而少写）。
2. 休市日**只能少写**（`simulation_*` 的监控刷新），**不许新增写**。
3. 判定只读 `quant.trading_calendar`（经 `TradingDayGuard`）；**不得**新增直接 SQL。
4. 不新增 `quant.*` 表/列/索引；不改 `scheduler_tasks`（与本需求无关）。
5. 台账 `quant.scheduler_runs`（② 的）本需求**不碰**。
