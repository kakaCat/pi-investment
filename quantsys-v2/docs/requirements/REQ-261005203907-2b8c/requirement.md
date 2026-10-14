# REQ-261005203907-2b8c · DailyJobs 宿主接入交易日门：休市日不再开火

**需求ID**: REQ-261005203907-2b8c
**类型**: feature
**作用域**: `quantsys-v2/`（`adapters/inbound/fastapi_app/daily_jobs/`（registry / runtime / defs）、`tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: 轻档（L3 依据见文末；出现"第二个未定决策 / 动架构 / 新增子系统 / 改数据模型"即单向升级重档）

## TL;DR

**2026-10-05（国庆休市、下一交易日 10-08）当天，DailyJobs 宿主照常开了 6 个任务。**
根因一句话：**这套宿主的排班只认"工作日"，不认交易日**——`pool_daily_refresh` 19:05 记 success
（22.1 秒，3 个 dynamic 池 50/30/20 只，0 失败），`evening_pipeline` 20:30 还在跑
（K 线段已自证新鲜跳过，**因子段仍对着 09-30 的冻结快照全市场重算**）。

```
registry.py:44   JobDef('pool_daily_refresh', dtime(19,5), (0,1,2,3,4), ...)   ← 只有 weekday
runtime.py:53    is_due(): 只看 weekday + 是否过点 + 当天有无记录              ← 无交易日概念
                 └─▶ 休市日（10-01/02/05/06/07）在工作日集合内 → 一律开火
```

**本需求要做的**：给 DailyJobs 宿主加一道**交易日门**（JobDef 级标志），让"吃当日行情数据"的工作日任务
在休市日**不执行、只留一行 `skipped`、不发通知**；门必须 **fail-open**（日历不可用 → 照跑），
且**复市首日不得跳过**。

## L1 一句话目标 + 可证伪判定标准

**目标**：休市日不再对着一份冻结的行情快照空跑重算，也不再为这些空跑发"开始/完成"通知；
"跳过"必须留痕，与"根本没跑"在台账里可区分。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：
1. 固定日期单测：休市日（2026-10-05/06/07）→ 4 个在册任务判 `skip`；交易日（2026-09-30、2026-10-08）→ 判 `run`。
2. 降级单测：日历链降级（`degraded=True`）→ 判 `run`（fail-open），并在 result 里带 `degraded`。
3. 留痕单测：跳过时写入 `inprocess_job_runs(status='skipped')`，且**不调用** `_send_feishu`。
4. 现行回归不破：既有 daily_jobs 测试全过；`trigger_job(force=True)` 仍可人工强制跑。
5. 真实观察（休市日实跑）：2026-10-06/07 的 `pool_daily_refresh` 台账出现 `status=skipped` 且当天无该任务飞书；
   2026-10-08（复市首日）两个任务恢复 `success`。

## 边界

### 做什么

1. **给 `JobDef` 加交易日门标志**（候选名 `trading_days_only`，缺省 `False` = 行为完全不变），
   并在宿主判排班处消费它：休市日不进执行路径。
2. **门是 fail-open 的**：判定走 `application/services/trading_day_guard.TradingDayGuard.check()`
   （其 verdict 已带 `source` / `degraded`）；**只有 `is_trading_day=False 且 degraded=False` 才跳过**。
   日历不可用/判定异常（`unavailable` / `compute-error` / `weekday_fallback`）→ **照跑**，并在 result 里标注降级。
3. **跳过要留痕、不打扰**：写 `quant.inprocess_job_runs` 一行 `status='skipped'`，
   `result` 带 `{'skipped': True, 'reason': ..., 'trading_day_source': ..., 'degraded': ...}`；
   **不发** "▶️ 每日任务开始" / "✅ 每日任务完成" 飞书。
4. **逐任务语义（范围 = 用户裁定的 A 项）**：
   - `pool_daily_refresh`：休市日整段跳过（refresh + sync-stock-names 都不做）。
   - `chip_distribution`：休市日整段跳过。
   - `evolution_fitness`：休市日整段跳过。
   - `evening_pipeline`：休市日**保留 K 线段**（新鲜度检查 + 缺口修复），
     仅在"K 线段未修复任何数据"时跳过因子段；**K 线段确有更新则因子段照跑**（避免留下因子空洞）。
5. **可测**：日期驱动的单元测试 + 一次真实休市日观察（见「判定标准」）。

### 不做什么

- **不动 APScheduler 路径**（`quant.scheduler_tasks` 里 11 条启用任务，全部按工作日 cron；
  v13 链已由 REQ-261004154902-a7cd 在内部自守，信号/扫描类是否需自守属**另一条线**，本次只登记）。
- **不动 `freshness_guard` / `watch_rule_health`**：前者靠交易日感知的基准日自证新鲜（休市日判"新鲜"即安静），
  后者与行情无关；本需求不改它们的排班。
- **不动 `event_calendar_check`（含周末设计）/ `financial_statements`（周六）/ `pool_weekly_review`（周日）**：
  它们的排班本就落在非交易日，且与"当日行情"无关。
- **不改 `TradingDayGuard` 的既有语义**：它对钱路任务是 fail-closed（保守判非交易日），
  这一语义**保留**；fail-open 是本需求在**调用点**按 `degraded` 做的取舍，不反向改守卫。
- **不改 K 线 / 因子数据内容**，不新增第三方依赖，不改任何对外 HTTP 契约。

### 边界理由

- 用户可感知的成本有两项，且都可量化：**空跑的 CPU**（见 E6：休市日因子段全市场 5268 只）与
  **休市日的通知噪声**（每次任务 2 条飞书，见 E7）。
- 修法局部：一个 dataclass 加一个标志 + 宿主 `_run_job` 一处分支 + registry 4 行 + 测试，
  不新增子系统、不动数据模型。
- 为什么必须 fail-open：本仓已为"保护性判定变成可用性故障"付过代价（E8），
  而本需求的收益是"省一次无信息量的重算"——**绝不能为此换来一次静默停摆**。
- 为什么 `evening_pipeline` 不能一刀切：它的 K 线段是休市日**唯一的缺口修复路径**（E10 明确把这件事交接给了本需求），
  因子段才是那份"对着冻结快照重算"的成本（E6）。

## 产品定义

### 一句话

让 DailyJobs 宿主按**真实交易日历**决定"今天该不该干这件活"，而不是按"今天是不是周一~周五"猜——
休市日不再空跑，也不再为空跑发通知；跳过落在台账里，看得见、也认得出来。

### 为什么现在做

1. **同一系统两套口径**：策略链已按 a7cd 定下"休市日不开火、复市首日不跳过"（E9 相邻口径），
   DailyJobs 仍按工作日近似——本次是把这个口径补到第二条调度路径上。
2. **国庆给出了现成的观察窗口**：10-05/06/07 三个休市日 + 10-08 复市首日，
   改完当天就能拿到真实台账证据（不必等下一个长假）。
3. **已有现成件，缺的只是接线**：`TradingDayGuard.check()` 已经返回
   `is_trading_day / source / degraded`（E9），`orchestrator_bootstrap.py:33` 注释里缺的那件
   "故障时降级为 weekday 而非判 False 的日级来源"正是它——本需求不需要再发明判定器。

### 成功长什么样

- 休市日：`quant.inprocess_job_runs` 出现 `pool_daily_refresh → skipped`，当天没有该任务的飞书；
  `evening_pipeline` 的 result 显示 `kline_sync=skipped` + `factor_compute=skipped(非交易日)`。
- 复市首日（10-08）：两个任务恢复 `success`，池子照常换血、因子照常算。
- 日历源挂掉的那天：任务**照跑**，且 result / 日志里有 `degraded=True` 与来源，不留死角。

## 用户与角色

- **项目所有者（人类）**：判断标准是"休市日安静、复市首日照常；跳过的事我能从台账上看见"。
- **窗口 AI Agent（本需求实施者）**：按 FR 逐条改，改动集中在 1 个 dataclass + 1 处宿主分支 + 4 行注册 + 测试。
- **后续维护者 / 新会话**：需要一条明确规则——**"今天该不该跑"只允许有一个来源**
  （`TradingDayGuard` + 本需求的 fail-open 取舍说明），禁止在下游各自写一遍 `weekday()`。

## 功能点（G2 条款）

**FR-1: DailyJobs 任务可声明"只在交易日执行"**
`JobDef` 新增布尔标志（缺省 `False`，语义 = 行为与现在完全一致）；宿主在判"是否该跑"处消费它。
未声明该标志的任务排班与行为**逐字不变**（含周末/每日任务）。
（标志名与消费点由设计阶段定；`daily_jobs_bootstrap.py` 转发壳的导出清单需同步——它是 44 个模块的既有导入路径。）

**FR-2: 交易日门必须 fail-open**
判定走 `TradingDayGuard.check(now)`：**仅当 `is_trading_day=False` 且 `degraded=False` 才判定为"该跳过"**；
任何降级来源（`weekday_fallback` / `unavailable` / `compute-error`）一律**判该跑**，
并把 `source` / `degraded` 带进任务 result 与日志（不许静默）。
判定器自身异常**不得**让宿主线程或任务线程挂掉。

**FR-3: 跳过 = 留痕 + 不打扰**
休市日跳过时：① 写 `quant.inprocess_job_runs` 一行 `status='skipped'`（`finished_at` 有值、`result` 带原因与判定来源）；
② **不发送**开始 / 完成飞书；③ 记一条 info 日志。台账里 `skipped` 与"没有行（根本没跑）"必须可区分。
`skipped` **不得**被任何巡检判为失败或"该跑没跑"（`find_result_failure` 已认 `skipped=True` 为不失败，E9）。

**FR-4: 范围内 4 个任务的逐任务语义**
- `pool_daily_refresh` / `chip_distribution` / `evolution_fitness`：休市日**整段跳过**（不调用 handler）。
- `evening_pipeline`：休市日**保留 K 线段**（新鲜度检查与缺口修复不得被门挡掉）；
  因子段在"K 线段本次未更新任何数据"时跳过，K 线段确有更新时照跑。
- 其余 5 个任务（`watch_rule_health` / `event_calendar_check` / `freshness_guard` /
  `financial_statements` / `pool_weekly_review`）**不声明**该标志，行为不变。

**FR-5: 跳过不得引发补跑，人工仍可强制**
休市日的跳过记录**不得**触发跨日补跑（`catchup_due` 只看 failed，需保持）；
复市首日（判定为交易日）照常执行；`trigger_job(force=True)` 在跳过日仍可人工强制跑，
且**不得**因为存在 `skipped` 行而拒绝（现状 `trigger_job` 只对 `running` / `success` 拒绝）。

**FR-6: 回归锁与真实观察**
新增日期驱动的单测（休市日 / 交易日 / 周末 / 降级四条），并保证既有 `tests/test_daily_jobs_bootstrap.py`
与 daily_jobs 相关用例全过；产出一次真实休市日（2026-10-06 或 10-07）与复市首日（10-08）的台账观察结论。

## 现状取证（2026-10-05 实测）

| 编号 | 证据 |
|---|---|
| E1 | `adapters/inbound/fastapi_app/daily_jobs/registry.py:44-47`：`pool_daily_refresh` 19:05 `(0,1,2,3,4)`、`evening_pipeline` 20:30、`chip_distribution` 21:10、`evolution_fitness` 20:35 —— 排班只有 weekday |
| E2 | `adapters/inbound/fastapi_app/daily_jobs/runtime.py:53-86` `is_due()`：`now.weekday() not in job.weekdays` / 过点 / 当天记录三条件，**无任何交易日判定**；`runtime.py:100` 与 `:134` 是**无条件**发出的开始/完成飞书 |
| E3 | 2026-10-05 台账（`quant.inprocess_job_runs`）：`watch_rule_health` 16:30:48（0.56s）/ `event_calendar_check` 16:45:50（0.52s）/ `freshness_guard` 17:20:55（0.53s）/ **`pool_daily_refresh` 19:05:39→19:06:01（22.1s，success）** / `evening_pipeline` 20:30:59 起 running / `evolution_fitness` 20:35:00（1.2s） |
| E4 | `resolve_trading_day`：2026-10-05 → `is_trading_day=False`、`source=calendar_table`、`degraded=False`；10-08 → `True`；`TradingDayGuard.check('2026-10-05').is_trading_day=False`（与 a7cd 的验收记录一致："2026-10-05/06/07 判休市、10-08 判交易日"） |
| E5 | `pool_daily_refresh` 休市日无实质变化：10-05 全天 `quant.pool_change_log` **0 行**（该表现存仅 2 行，均为 10-04 18:00 周任务写的 `刷新换血：+1 / -1`）→ 今天的 refresh 是把 09-30 的冻结快照重算一遍 |
| E6 | 同日 20:31:01 日志：`K线已新鲜（覆盖 5265/5277=99.8% ≥ 98%，基准日 2026-09-30），跳过同步` → **同一秒**进入 `evening_pipeline: factor_compute start (full market)`，预筛 5268 只；至 20:41 仍在跑（**K 线段已自守，因子段无门**） |
| E7 | 通知成本：每次任务固定 2 条飞书（`runtime.py:100/134`）；实测 20:30:59 `飞书发送成功`（`agent_channel` 因 webhook 未配置降级为飞书） |
| E8 | fail-closed 教训（`adapters/inbound/fastapi_app/orchestrator_bootstrap.py:31-40`）：交易日守卫是 fail-closed，而那是"钱路"任务的唯一门——接上去会让 DB 一抖就静默停掉 T+1 结转与止损；故该处**刻意**保持 weekday 近似（2026-09-12 审查后回退） |
| E9 | 相邻口径已定：`infrastructure/scheduler/job_executor.py:157`「显式 `skipped=True` 不算失败（非交易日/幂等跳过是正常语义）」；`trading_day_guard.py` 的 verdict 已带 `source` / `degraded`，并明确"不许把日历不可用当成休市" |
| E10 | 交接来源：`docs/requirements/REQ-261004102115-d3de/requirement.md`「不做什么」原文——"**不修 `evening_pipeline` 在休市日空跑 `kline_sync` 的行为**（10-02 那次成功 0 只、未覆盖 5271 只）——属'休市日是否该起同步'的另一个决定，本次只登记、另案处理" |
| E11 | 范围边界实测：`quant.scheduler_tasks` 启用 11 条（`signal_execution_daily` 15:30 / `v13_daily_check` 14:30 / `chan_scan` 10:10 等，全部工作日 cron）→ 属 **APScheduler 路径**，本需求不改（见「不做什么」） |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1（跳过的代价）**：休市日的池刷新**并非恒为 no-op**——10-04（周日）周任务写的 `+1 / -1` 两行就是休市日产生的换血。
  即"跳过"会少一次"可能产生变化"的重算。**为什么仍然接受**：10-08 复市首日会照常跑（FR-5），
  那两行换血在复市首日同样会发生，只是日期落在交易日上——对 point-in-time 审计反而是**更准确**的落点。
- **R2（因子空洞）**：若休市日 K 线段修复了历史缺口，跳过因子段会让这些修复结果当次不落因子。
  **这就是 FR-4 对 `evening_pipeline` 例外处理的原因**（K 线段有更新 → 因子段照跑）。
- **R3（新增依赖面）**：把日历判定引入调度热路径，多了一次查库（`TradingDayGuard` 有 60s 进程级缓存，
  实测两次索引查询约 0.12ms）；若日历源抖动，FR-2 的 fail-open 保证"最坏 = 回到现在的行为"（多跑一次），
  不会变成"该跑没跑"。

## 接口与数据契约

- **内部接口**：`JobDef` 新增字段（候选 `trading_days_only: bool = False`）——同名 dataclass 由
  `daily_jobs_bootstrap.py` 转发导出，`__all__` 与既有导入路径需保持可用（44 个模块在用）。
- **数据契约（增量）**：`quant.inprocess_job_runs.status` 新增取值 `'skipped'`
  （既有取值 `running` / `success` / `failed` 语义不变）；`result` 形状见 FR-3。
  消费方兼容性：`is_due` 对未知 status 落到 `return False`（天然不重跑）；
  `_job_failure_watch` 只看 failed；`_reap_orphan_runs` 只看 running。
- **无对外 HTTP 契约变化**：`list_today_runs()` 会多出 `skipped` 状态，属展示层增量。

## 判定标准（可跑）

1. `./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q` → 全过（新增：休市日 / 交易日 / 周末 / 降级四条）。
2. `./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py -q` → 全过（既有回归，含 `is_due` / `catchup_due` 语义不动）。
3. 跳过留痕：测试断言 `_mark_done(..., status='skipped', result={'skipped': True, ...})` 被调用**且** `_send_feishu` 未被调用。
4. 降级 fail-open：patch 判定返回 `degraded=True` → 断言任务**照跑**（不是 skip）。
5. 人工强制：`trigger_job('pool_daily_refresh', force=False)` 在存在 `skipped` 行时**不返回拒绝**。
6. 真实观察（休市日）：2026-10-06 或 10-07 查
   `select job_id, status, result->>'reason' from quant.inprocess_job_runs where run_date='2026-10-06';`
   → `pool_daily_refresh` 为 `skipped`，且当天无该任务飞书。
7. 复市首日：2026-10-08 查同表 → `pool_daily_refresh` / `evening_pipeline` 均 `success`。

## 轻档依据（L3）与升级信号

- **L1 一句话目标 + 可证伪判定**：见「产品定义」与「判定标准」第 1~3 条（命令 + 期望输出写死）。
- **L2 范围边界 ≤3 条**：见「做什么 / 不做什么」，显式排除 APScheduler 路径与另外 5 个任务。
- **L3 轻路径依据**：改动面小（1 个 dataclass 字段 + 1 处宿主分支 + 4 行注册 + 1 个测试文件），
  判定器**已存在**（不新增子系统），数据模型不动。
- **单向升级信号**（出现即升重档、改走完整设计）：
  ① 设计阶段若选择"因子段改用**因子新鲜度门**"（而非日历门）——需新增"因子最新日"查询口径，属**第二个未定决策**；
  ② 若要把门推广到 APScheduler 路径（`scheduler_tasks` 11 条）——那是**动架构**（两条调度路径共用日级门）。
- **提示词难度**：`expert`（立项弹框作答，见 D-1）。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 立项弹框作答（本窗口，2026-10-05 20:39）：名称「DailyJobs 宿主接入交易日门：休市日不再开火（pool_daily_refresh 等）」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**，难度 expert，文档落 `docs/requirements/REQ-261005203907-2b8c/` | FR-1、FR-2、FR-3、FR-4、FR-5、FR-6 | `reqboard_status` 显示本窗口绑定 REQ-261005203907-2b8c；六条 FR 的「条款接收状态」在拆分落库后由 FR-1~FR-6 逐条承接 |
| D-2 | 本窗口用户消息（2026-10-05 20:41）：「A（我推荐）」 | 范围取 **A**：门做成 `JobDef` 通用标志，先挂到 4 个"吃当日行情数据"的工作日任务（`pool_daily_refresh` / `evening_pipeline` / `chip_distribution` / `evolution_fitness`）；`freshness_guard` / `watch_rule_health` 保持工作日 | FR-1、FR-4 | FR-4 的单测逐任务断言：4 个在册任务在休市日判 skip；另外 5 个任务行为不变 |

## 下一步

产物已落盘 → 交人工确认（`reqboard_ask_confirm(target=artifact, kind=requirement)`）；
确认后进入 **design** 节点（只写设计文档，`docs/requirements/REQ-261005203907-2b8c/design/`）。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-dd0d4d、t-075116 |
| FR-2 | ✅ 已接收 | t-dd0d4d |
| FR-3 | ✅ 已接收 | t-075116、t-dbb9d0 |
| FR-4 | ✅ 已接收 | t-588729 |
| FR-5 | ✅ 已接收 | t-075116、t-dbb9d0 |
| FR-6 | ✅ 已接收 | t-6384c0 |

> 无未接收条款（6 条全部有落点）。

<!-- reqboard:marks:end -->
