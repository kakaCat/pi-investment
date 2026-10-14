# REQ-261006093620-a315 · 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

**需求ID**: REQ-261006093620-a315
**类型**: feature
**作用域**: `quantsys-v2/`（`infrastructure/scheduler/`（APSchedulerService 与 run 记账链）、`application/services/scheduler_tasks_*` / `scheduler_handlers.py`、`adapters/inbound/fastapi_app/routes/scheduler_async.py`、`infrastructure/persistence/migrations/`、`tools/`、`tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: 重档（依据见文末「档位依据」；本次触发的正是上一张卡**预先登记**的升级信号）

## TL;DR

**2026-10-06（国庆休市·周二）09:25，v2 的库表调度照常开火了盘前扫描。**

根因一句话：**交易日门只补了 DailyJobs（③）那一条路径，库表调度（APScheduler，②）这条没有。**

```
                     v2 的两条调度路径（门只补了一条）
  +-----------------------------------------------------------------------+
  |  ② 库表调度 APSchedulerService        |  ③ DailyJobs 宿主线程          |
  |     读 quant.scheduler_tasks (11 条)  |     9 个核心数据任务           |
  |     TradingDayGuard 命中数 = 0        |     trading_days_only=True     |
  |              |                        |              |                 |
  |              v  无门 -> 休市日开火     |              v  有门 -> 跳过     |
  +-----------------------------------------------------------------------+
                 |                                        |
                 v                                        v
   logs/api.log:8532/8533                    daily_jobs/gate.py:76
   pre-market-scan 09:25  task_id=250        TradingDayGuard.check(now)
   run_id=3379  success  <-- 假成功           仅 is_trading_day=False
                                                 且 degraded=False 才跳
                 |                                        |
                 +------------------+---------------------+
                                    v
                     本需求：把 ② 补上同一道门
                     8 条挂门 / 3 条不挂（逐条按数据依赖）
```

**本需求要做的**：给库表调度加上**同一道交易日门**（逐任务声明），让"吃当日行情"的任务在休市日
**不执行、只留一行 `skipped`、不发通知**；门必须 **fail-open**（日历不可用 → 照跑）；
**复市首日不得跳过**；且**人工手动触发仍然可跑**（门只拦自动排班）。

## L1 一句话目标 + 可证伪判定标准

**目标**：休市日不再让"吃当日行情"的库表任务对着冻结快照空跑、也不再产生"跑成功了"的假台账；
"跳过"必须留痕，与"根本没跑"在台账里可区分；复市首日照常开火。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **日期驱动单测（新增）**：休市日（`2026-10-06/07`）→ 在册任务判 `skip`；交易日（`2026-09-30`）→ 判 `run`。
2. **降级单测**：日历链降级（`degraded=True`）→ 判 `run`（fail-open），result 带 `degraded` 与判定来源。
3. **周末分档单测**：`2026-10-03`（周六，`source='weekend'`）→ 排班含周末的 `#232` 判 `run`；法定节假日 → 判 `skip`。
4. **判据口径锁（反例锁）**：断言 `TradingDayGuard.check('2026-10-08').source == 'future'` 且 `is_trading_day=False`
   ——即"未来日期保守判非交易日"这一语义**不得**被当成"复市首日应跳过"的依据（见 E9 的坑）。
5. **留痕不打扰**：休市日 `quant.scheduler_runs` 出现 `status='skipped'`（`result` 带原因与来源），
   且当天**没有**该任务的"开始/完成"通知。
6. **人工可强制**：`POST /api/scheduler/tasks/250/trigger` 在休市日**仍返回可执行**（不被门拒绝）。
7. **现行回归不破**：`test_scheduler_duplicate_prevention.py` / `test_scheduler_misfire_semantics.py` /
   `test_daily_jobs_trading_day_gate.py` 全过。
8. **真实观察**：`2026-10-07`（休市）挂门任务台账为 `skipped` 且无通知；`2026-10-08`（复市首日）恢复 `success`。

## 边界

### 做什么

1. **给库表任务加"只在交易日自动执行"的逐任务声明**（候选：`quant.scheduler_tasks` 新增列，
   或复用既有 `params jsonb`；**缺省 = 行为与现在完全一致**），并在自动排班的执行入口消费它。
2. **门必须 fail-open，且复用唯一判定源**：判定走
   `application/services/trading_day_guard.TradingDayGuard.check(now)`（其 verdict 已带 `source` / `degraded`）；
   **只有 `is_trading_day=False` 且 `degraded=False` 才跳过**；日历降级/异常一律**照跑**并留痕。
   禁止在下游另写 `weekday()` 或第二条日历查询链。
3. **跳过 = 留痕 + 不打扰 + 不补跑**：写 `quant.scheduler_runs` 一行 `status='skipped'`，
   `result` 带 `{'skipped': True, 'reason': ..., 'trading_day_source': ..., 'degraded': ...}`；
   **不发**"开始/完成"通知；**不得**被巡检判为失败或"该跑没跑"（口径同步见 FR-3）。
4. **逐任务语义（范围 = 用户裁定的 D-3）**：按"是否吃当日行情数据"逐条判定，见 FR-4 的表。
5. **周末分档语义（D-6）**：排班**含周末**的任务（`#232`）只在"日历明确答**法定节假日**"时跳过，
   `source='weekend'` 照跑；`1-5` 排班任务不受此分档影响（周末本就不排）。
6. **人工口子保留（D-5）**：门只作用于"按时到点自动开火"；手动 `trigger` 与 `reload` 语义不变。
7. **可测**：新增日期驱动单元测试 + 一次真实休市日/复市首日观察（见「判定标准」）。

### 不做什么

- **不动 DailyJobs（③）**：它已在 REQ-261005203907-2b8c 有门。本次**不改**其判定与行为；
  两条路径是否收敛成一份共享模块由设计阶段定，**但不得回归 ③ 的既有语义**。
- **不动 `TradingDayGuard` 的既有语义**：它对钱路任务是 fail-closed（含"未来 → 非交易日"），
  这一语义**保留**；fail-open 是本需求在**调用点**按 `degraded` 做的取舍，不反向改守卫。
- **不追「早盘要点」卡片的产出方**：文案在全仓与 `~/.dsh` 均无模板命中，来源未钉死（见 E7），
  属**另一条线**，本需求只登记、不处理（用户 D-3 明确只堵已确证的这条路径）。
- **不改任何 cron 表达式**：门是执行期判定，不是改排班；`* * 1-5` 保持原样。
- **不新增第三份调度实现**、不动数据模型主键、不改对外 HTTP 契约语义。

### 边界理由

- **为什么这次不是"顺手再补一个标志"**：① 门要覆盖 **11 条启用任务中的 8 条**，且判据是
  "逐条按数据依赖"而不是"一刀切"；② 台账新增一个状态取值，会牵动**巡检口径**
  （`scripts/scheduler_watchdog.py:289` 用 `status='success'` 判"跑没跑"，见 R3）；
  ③ 上一张卡已把"推广到 APScheduler 路径"登记为**动架构**的升级信号（见「档位依据」）。
- **为什么必须 fail-open**：本仓为"保护性判定变成可用性故障"付过代价（E8）；
  本需求收益是"省一次无信息量的重算"，**绝不能换来一次静默停摆**。
- **为什么不能一刀切按"今天是不是交易日"**：启用集合里有任务本就排在周末
  （`#253` 周六 10:00、`#262` 周日 12:00、`#237` 周五 18:00），一刀切会让它们**永不执行**（E6）。
- **为什么保留周末语义分档**：`#232` 是**每日**排班（含周末），把周末一并跳掉属**行为扩大**，
  超出"治本次病"的范围（D-6）。

## 产品定义

### 一句话

让 v2 的库表调度按**真实交易日历**决定"这个任务今天该不该自动开火"，而不是按"今天是不是周一~周五"猜——
休市日不再空跑、不再为空跑发通知、也不再记 "success" 假台账；跳过落在台账里，看得见、也认得出来。

### 为什么现在做

1. **同一系统两套口径**：③ DailyJobs 已按 2b8c 定下"休市日不开火、复市首日不跳过"；
   ② 库表调度仍是工作日近似——本次把口径补到第二条路径上，**两条路径口径才真正一致**。
2. **国庆给了现成观察窗口**：`10-06/07` 两个休市日 + `10-08` 复市首日，改完当天即可拿到真实台账证据。
3. **已有现成件，缺的只是接线**：`TradingDayGuard.check()` 已返回
   `is_trading_day / source / degraded`（E8），`resolve_trading_day()` 已提供"复市首日可判"的口径（E9），
   `③` 的 `daily_jobs/gate.py` 已给出 fail-open 的写法参照（E5）——不需要再发明判定器。
4. **假成功的代价已经付过**：休市日把 `run_id=3379` 记成 `success`，让"任务健康"的巡检读到一个
   根本不该发生的成功（同类演出：09-13 起停摆 18 天、08-05 死讯静默 8 天）。

### 成功长什么样

- 休市日：`quant.scheduler_runs` 出现 `pre-market-scan → skipped`，当天没有该任务的通知；
  其余挂门任务同理。**不再有**休市日的 `success`。
- 复市首日（`10-08`）：挂门任务恢复 `success`，盘前扫描照常出候选。
- 日历源挂掉的那天：任务**照跑**，且 result / 日志里有 `degraded=True` 与来源，不留死角。
- 巡检侧：休市日的 `skipped` **不**冒出一串"该跑没跑"假警（R3 的口径同步已做）。

## 用户与角色

- **项目所有者（人类）**：判断标准是"休市日安静、复市首日照常；跳过的事我能从台账上看见"。
- **窗口 AI Agent（本需求实施者）**：按 FR 逐条改，改动集中在"一处判定 + 一处执行分支 + 一张任务清单"。
- **后续维护者 / 新会话**：需要一条明确规则——**"今天该不该跑"只允许有一个来源**
  （`TradingDayGuard` + 本需求的 fail-open 取舍），禁止在下游各自写一遍 `weekday()`；
  且"跳过"在台账里是可审计的状态，不是沉默。

## 功能点（G2 条款）

**FR-1: 库表任务可声明"只在交易日自动执行"**
`quant.scheduler_tasks` 增加逐任务的交易日门声明（**缺省 = 行为与现在完全一致**）；
未声明的任务排班与执行行为**逐字不变**（含周末排班任务与"每天"排班任务）。
标志载体（新增列 vs `params jsonb`）由设计阶段定；消费点在**自动排班**的执行入口，
必须与手动触发路径分离（见 FR-6）。

**FR-2: 交易日门必须 fail-open，且复用唯一判定源**
判定一律走 `TradingDayGuard.check(now)`：**仅当 `is_trading_day=False` 且 `degraded=False` 才判"该跳过"**；
任何降级来源（`weekday_fallback` / `unavailable` / `compute-error`）一律**判该跑**，
并把 `source` / `degraded` 带进 run 的 `result` 与日志（不许静默）。
判定器自身异常**不得**让调度线程或任务线程挂掉。

**FR-3: 跳过 = 留痕 + 不打扰 + 不误报**
休市日跳过时：① 写 `quant.scheduler_runs` 一行 `status='skipped'`（`completed_at` 有值、`result` 带原因与判定来源）；
② **不发送**开始 / 完成通知；③ 记一条 info 日志。
台账里 `skipped` 与"没有行（根本没跑）"必须可区分；
并**同步"该跑没跑"的巡检口径**，使 `skipped` 不被判为失败或漏跑（现状判据见 R3）。

**FR-4: 范围内逐任务语义（8 条挂门，3 条不挂）**
按"是否吃当日行情数据"逐条判定（判据见「现状取证」E10/E11 的文件行）：

| task_id | name | command | cron | 归类 | 依据 |
|---|---|---|---|---|---|
| 250 | pre-market-scan | `market_scan_preopen` | `25 9 * * 1-5` | **挂门** | 真实选股打分（`scheduler.py:1332-1376` 委托 `StockScreeningService`） |
| 247 | daily-signal-generate | `signal_generate` | `30 16 * * 1-5` | **挂门** | 池内扫描出信号（`scheduler_tasks_signals.py:55-87`） |
| 242 | 每日信号执行 | `signal_execution_daily` | `30 15 * * 1-5` | **挂门** | 推当日 pending 信号（`scheduler_tasks_signals.py:180-223`） |
| 259 | daily-signal-push-fallback | `signal_execution_daily` | `40 9 * * 1-5` | **挂门** | 同上（同一 handler） |
| 249 | v13-simulation-trading | `v13_daily_check` | `30 14 * * 1-5` | **挂门** | 模拟交易检查（`scheduler_tasks_strategy.py:118-135`） |
| 261 | chan-scan-daily | `chan_scan` | `10 10 * * 1-5` | **挂门** | 收盘后买卖点扫描，休市日重扫冻结快照（`scheduler_tasks_reports.py:209-228`） |
| 237 | 每周报告生成 | `report_daily` | `0 18 * * 5` | **挂门** | `date.today()` + 全市场涨跌家数（`scheduler_tasks_reports.py:13-22,40-50`） |
| 232 | 每日数据质量检查 | `data_quality_check` | `0 0 * * *` | **挂门·分档** | 以 `datetime.now()` 为窗口锚（`data_quality_check_job.py:158-159`）；排班含周末 → 见 FR-5 |
| 252 | daily-strategy-validation | `strategy_validate_daily` | `0 21 * * 1-5` | **不挂** | 基于最近落库回测证据 `lookback_days=30`（`scheduler_tasks_strategy.py:33-37`） |
| 253 | weekly-strategy-discovery | `strategy_discover_weekly` | `0 10 * * 6` | **不挂** | `lookback_days=365`，且排班在周六（`scheduler_tasks_strategy.py:82-86`） |
| 262 | chan-knowledge-distill-weekly | `chan_knowledge_distill` | `0 12 * * 0` | **不挂** | `lookback_days=90`，且排班在周日（`scheduler_tasks_reports.py:238-241`） |

**FR-5: 门的周末分档语义**
排班**含周末**的任务（现存仅 `#232`）：**仅当**判定来源为"法定节假日"
（`source='trading-calendar-holiday'`）时跳过；`source='weekend'` → **照跑**。
`1-5` 排班任务无此分档（周末不可达），沿用 FR-2 的一般判据。
新增"含周末排班"任务时**默认不跳过周末**，需显式声明才改变。

**FR-6: 门只拦自动排班，人工仍可强制**
`POST /api/scheduler/tasks/{id}/trigger`（`scheduler_async.py:421`）在休市日**仍可执行**，
不得因门而拒绝或静默转为 skip；`POST /api/scheduler/reload`（`:475`）语义不变。
即"人不让它跑"与"日历说今天不该自动跑"是两件事，**不得互相覆盖**。

**FR-7: 门必须真的生效（含重启与存量 jobstore）**
声明改动经既有生效路径落地后，**旧排班不得继续按原样触发**：
需覆盖"DB 行已改但 jobstore 仍持旧 job"的存量场景（该坑有实证，见 R4），
并保证进程重启后仍生效。生效性与可对账方法写进设计。

**FR-8: 回归锁与真实观察**
新增日期驱动的单测（休市日 / 交易日 / 周末分档 / 降级 / 未来日期口径五条），
既有 `test_scheduler_duplicate_prevention.py` / `test_scheduler_misfire_semantics.py` /
`test_daily_jobs_trading_day_gate.py` 全过；
并产出一次真实休市日（`2026-10-07`）与复市首日（`2026-10-08`）的台账观察结论。

## 现状取证（2026-10-06 实测）

| 编号 | 证据 |
|---|---|
| E1 | **触发实证**：`logs/api.log:8532` `Running job "pre-market-scan (trigger: cron[... day_of_week='mon,tue,wed,thu,fri', hour='9', minute='25'])" (scheduled at 2026-10-06 09:25:00+08:00)`；`:8533` `Starting task: pre-market-scan (task_id=250, run_id=3379, command=market_scan_preopen)` |
| E2 | **假成功**：同日 `Job market_scan_preopen completed: success=True` / `Task completed: pre-market-scan (run_id=3379, duration=129ms, inner_status=success)` —— 休市日照记 success |
| E3 | **同日其它开火**：`:8540` 09:30 `paper_trading_engine_initialized`（`rotation_main`）；`:8511` 00:04 数据质量告警 `回填失败率过高: 98.0% (阈值: 50%)` 并经飞书外发（`notif_e40e151bd0884bdc`） |
| E4 | **排班集合**：`quant.scheduler_tasks` 启用 11 条（`232 0 0 * * *` / `237 0 18 * * 5` / `242 30 15 * * 1-5` / `247 30 16 * * 1-5` / `249 30 14 * * 1-5` / `250 25 9 * * 1-5` / `252 0 21 * * 1-5` / `253 0 10 * * 6` / `259 40 9 * * 1-5` / `261 10 10 * * 1-5` / `262 0 12 * * 0`） |
| E5 | **对照路径已修**：`adapters/inbound/fastapi_app/daily_jobs/registry.py:38/41/58` 三处 `trading_days_only=True`；`daily_jobs/gate.py` 是 fail-open 门的写法参照（`:76` 调 `TradingDayGuard.check`，`:66` 门自身异常 → 按降级照跑） |
| E6 | **一刀切会误伤**：`#253` 周六 10:00、`#262` 周日 12:00、`#237` 周五 18:00 —— 排班本就落在非交易日；按"非交易日就跳"一刀切 → 这三条**永不执行** |
| E7 | **卡片来源未钉死**：全仓（`.py/.ts/.md/.json/.sh/.plist`）+ `~/.dsh` 搜「早盘要点 / 浮盈 / 无处置 / 基准滞后」，仅命中本会话与 reqboard 台账 → 文案是 LLM 现场生成、**不是模板**；PI 实例（`agent-dh/.dsh-data/sessions` 与 projcache）最新会话停在 **10-04**，今日无会话 |
| E8 | **判定器已存在**：`trading_day_guard.py:12-27` 语义（周末 → `weekend`；未来 → `future`；其余走 `trading_day_resolver` 日历链，含法定节假日与降级标注）；实测 `check('2026-10-06')` → `False / trading-calendar-holiday / degraded=False`；`check('2026-09-30')` → `True / trading-calendar` |
| E9 | **两套口径的分岔（验收必须用对）**：`TradingDayGuard.check('2026-10-08')` 今天 → **`False` / `source='future'`**（写入型路径刻意保守）；而 `resolve_trading_day(date(2026,10,8)).date == date(2026,10,8)` → **`True`**（`source=calendar_table`），因 `quant.trading_calendar` 覆盖到 **2026-12-31**（23373 行）。故"复市首日不跳"的验收**只能用 resolver 口径** |
| E10 | **挂门任务的当日数据依赖（文件行）**：见 FR-4 表「依据」列（`scheduler_tasks_signals.py:55-87/180-223`、`scheduler_tasks_strategy.py:118-135`、`scheduler_tasks_reports.py:13-22/209-228`、`scheduler.py:1332-1376`、`data_quality_check_job.py:158-159`） |
| E11 | **不挂门任务的证据（不吃当日）**：`strategy_validate_daily` `lookback_days=30` 基于落库回测证据（`scheduler_tasks_strategy.py:33-37`）；`strategy_discover_weekly` `lookback_days=365`（`:82-86`）；`chan_knowledge_distill` `lookback_days=90`（`scheduler_tasks_reports.py:238-241`） |
| E12 | **零门的机械证据**：`TradingDayGuard` / `trading_day` / `is_trading` 在 `infrastructure/scheduler/apscheduler_service.py`、`application/services/scheduler_tasks_registry.py`、`scheduler_tasks_*.py`、`scheduler_handlers.py` 中**零命中** |
| E13 | **台账契约**：`quant.scheduler_runs.status` 为 `text NOT NULL DEFAULT 'running'`，**无 CHECK 约束** → `'skipped'` 可直接写入，无需 DDL |
| E14 | **交接来源**：`docs/requirements/REQ-261005203907-2b8c/requirement.md:61-62`「**不动 APScheduler 路径**（`quant.scheduler_tasks` 里 11 条启用任务，全部按工作日 cron……）本次只登记」；同文 `:204` 升级信号②「若要把门推广到 APScheduler 路径（`scheduler_tasks` 11 条）——那是**动架构**（两条调度路径共用日级门）」 |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（跳过的代价）**：休市日的这几条任务**并非恒为 no-op**——若休市日恰有补数据/缺口修复，
  跳过会少一次"可能产生变化"的执行。**为什么仍然接受**：`10-08` 复市首日照常开火（FR-2/FR-6），
  变化只是日期落在交易日上——对 point-in-time 审计反而**更准确**；
  且 `#232` 的周末语义已按 D-6 分档保留，避免扩大行为变化。
- **R2（新增判定面）**：把日历判定引入调度热路径，多一次查库（`TradingDayGuard` 有 60s 进程级缓存，
  `trading_day_guard.py:52-55`）；日历源抖动时 FR-2 的 fail-open 保证"最坏 = 回到现在的行为"（多跑一次），
  不会变成"该跑没跑"。
- **R3（**修复自己会造假警**——本需求最容易被忽略的一条）**：`scripts/scheduler_watchdog.py:289` 与 `:390`
  用 `status='success'` 判定"这个槽位是否已跑过"，`application/services/should_have_run.py:32` 记录了
  "把日历混进'该跑没跑'换来 **504 条休市误报**"的教训。
  若只写 `skipped` 而**不同步巡检口径**，修复本身会产出一串"漏跑"假警 → 这是 FR-3 第 ④ 项的由来。
- **R4（只改声明不生效）**：`infrastructure/scheduler/apscheduler_service.py:369` 注释实证——
  任务 250 曾 `is_enabled=false` 仍**每天 01:25 触发**（近 30 天 15 次），三次进程重启都没摘掉，
  只有显式 `POST /api/scheduler/reload` 才生效 → 这是 FR-7 的由来。

## 接口与数据契约

- **内部接口（增量）**：`quant.scheduler_tasks` 增加逐任务的交易日门声明
  （新增列 or `params jsonb`，**设计阶段定**）；缺省值语义 = 行为与现在完全一致。
- **数据契约（增量）**：`quant.scheduler_runs.status` 新增取值 `'skipped'`
  （既有 `running` / `success` / `failed` 语义不变；无 CHECK 约束，E13）；`result` 形状见 FR-3。
  消费方兼容性：**必须逐一对账**现有读 `status` 的方（至少 `scripts/scheduler_watchdog.py`、
  `tools/` 下自检器、看板查询），凡把"非 success"当异常的，都要认得 `skipped` 是**正常语义**。
- **对外 HTTP 契约**：**不变**。`POST /api/scheduler/tasks/{task_id}/trigger`（`scheduler_async.py:421`）
  与 `POST /api/scheduler/reload`（`:475`）继续可用且语义不变（FR-6）。
- **无对外契约破坏、不新增第三方依赖、不改数据模型主键。**

## 判定标准（可跑）

1. 新增单测：`./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q` → 全过
   （休市日 / 交易日 / 周末分档 / 降级 / 未来日期口径 五条）。
2. 既有回归：`./venv/bin/python -m pytest tests/test_scheduler_duplicate_prevention.py tests/test_scheduler_misfire_semantics.py tests/test_daily_jobs_trading_day_gate.py -q` → 全过。
3. **判据口径自检（当天即可跑，不必等到 10-08）**：
   ```bash
   ./venv/bin/python -c "
   from datetime import date
   from application.services.trading_day_resolver import resolve_trading_day as r
   print(r(date(2026,10,7)).date == date(2026,10,7), r(date(2026,10,8)).date == date(2026,10,8))"
   # 期望: False True   ← 10-07 休市 / 10-08 复市首日（日历表覆盖到 2026-12-31）
   ```
4. **反例锁**：`./venv/bin/python -c "
   from application.services.trading_day_guard import TradingDayGuard as G
   v=G.check('2026-10-08'); print(v.is_trading_day, v.source)"` → 期望 `False future`
   （**证明它不能用来判"复市首日"**；FR-8 的单测须固定该语义）。
5. 留痕与不打扰：`select t.name, r.status, r.result->>'reason' from quant.scheduler_runs r join quant.scheduler_tasks t on t.id=r.task_id where r.started_at::date='2026-10-07' order by t.id;`
   → 挂门任务为 `skipped`；当天无对应通知。
6. 复市首日：同表 `started_at::date='2026-10-08'` → 挂门任务恢复 `success`。
7. 巡检不误报：休市日跑既有巡检（`scripts/scheduler_watchdog.py` 的只读模式 / `tools/` 下自检）
   → **不**因 `skipped` 产出"该跑没跑"。

## 档位依据与升级信号

- **重档依据（触发的是预登记的升级信号）**：`REQ-261005203907-2b8c` 的 requirement.md `:204` 明写
  「若要把门推广到 APScheduler 路径（`scheduler_tasks` 11 条）——那是**动架构**（两条调度路径共用日级门）」；
  同文 `:61-62` 把它列为"另一条线，本次只登记"。**本次就是那条线的落地**。
- **范围超出单文件**：跨任务执行策略（8 条挂门 / 3 条不挂）+ 台账新增状态取值 + **巡检口径同步** + 存量 jobstore 生效性。
- **配置比对**：本仓 `docs/requirements/` 同类 feature（2b8c）为轻档；本需求因触发升级信号而**单向升为重档**，
  不因"看起来是加个标志"而降档（拿不准取重档）。
- **仍需设计的开放点**（不得在需求阶段私定）：① 门标志的载体（新增列 vs `params jsonb`）；
  ② 自动排班与手动触发的分离点；③ 两条调度路径是否收敛成一份共享门模块；
  ④ 存量 jobstore 的生效与对账方式。
- **提示词难度**：`expert`（立项弹框作答，见 D-2）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 本窗口用户消息（2026-10-06 09:3x）：「【本实例投资账户 早盘要点】2026-10-06 休市（下一窗口 10-08 09:30）｜持仓 2 只全浮盈·无处置｜情绪 40 偏弱｜零委托｜归因 null（基准滞后）**不是交易日，依然触发了**」 | 本现象立项；定性为**"休市日开火"同族缺陷在第二条调度路径（② 库表调度）上的残留** | FR-1~FR-8（全部） | `reqboard_status` 显示本窗口绑定 `REQ-261006093620-a315`；E1~E3 为现象取证 |
| D-2 | 立项弹框作答（本窗口，2026-10-06 09:36）：名称「库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**，难度 `expert`，文档落 `docs/requirements/REQ-261006093620-a315/` | FR-1~FR-8 | 本文件存在且经 `reqboard_submit(kind=requirement)` 登记 |
| D-3 | 本窗口弹框作答（范围）：「先堵已确证的：v2 库表调度（APScheduler）休市日不开火（推荐）」 | 范围**只含 ② 库表调度**；不追「早盘要点」卡片产出方（来源未钉死，E7），不扩到 ③ DailyJobs | FR-1、FR-4；排除项见「不做什么」 | FR-4 表仅覆盖 `scheduler_tasks` 任务；「不做什么」显式排除卡片溯源 |
| D-4 | 本窗口弹框作答（适用面）：「逐条判定，只跳"吃当日行情"的那几条（推荐）」 | 不按"非交易日一刀切"；按**数据依赖**逐条判定：8 条挂门、3 条不挂 | FR-1、FR-4 | FR-4 表 11 行逐条给「依据」文件行；E6 证明一刀切会让 `#253/#262` 永不执行 |
| D-5 | 本窗口弹框作答（手动口子）：「只拦自动排班；手动触发仍可跑（推荐）」 | 门**只拦自动排班**；`trigger` / `reload` 在休市日仍可用且语义不变 | FR-1、FR-6 | 判定标准第 6 条：休市日 `trigger` 仍返回可执行 |
| D-6 | 本窗口弹框作答（周末语义）：「分档：#232 只跳法定节假日，周末照跑（推荐）」 | 门**分档**：排班含周末的任务仅在 `source='trading-calendar-holiday'` 时跳；`weekend` 照跑 | FR-3、FR-5 | 判定标准第 3 条：`2026-10-03`（周六）→ `#232` 判 `run`；法定节假日 → 判 `skip` |

## 下一步

产物已落盘 → 交人工确认（`reqboard_ask_confirm(target=artifact, kind=requirement)`）；
确认后进入 **design** 节点（只写设计文档，`docs/requirements/REQ-261006093620-a315/design/`），
把「档位依据」列出的 4 个开放点定死。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1、t2、t-63bc0a、t-e05ce2 |
| FR-2 | ✅ 已接收 | t1、t5、t-63bc0a、t-42eb9a |
| FR-3 | ✅ 已接收 | t5、t3、t4、t7、t-d91b87、t-da502d、t-42eb9a、t-54d79f |
| FR-4 | ✅ 已接收 | t2、t5、t-e05ce2、t-42eb9a |
| FR-5 | ✅ 已接收 | t1、t2、t-63bc0a、t-e05ce2 |
| FR-6 | ✅ 已接收 | t5、t6、t-42eb9a、t-3a7ebb |
| FR-7 | ✅ 已接收 | t2、t5、t-42eb9a |
| FR-8 | ✅ 已接收 | t3、t8、t-d91b87、t-ea51f0 |

> 无未接收条款（8 条全部有落点）。

<!-- reqboard:marks:end -->
