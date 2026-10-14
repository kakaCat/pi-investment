# 拆分计划（REQ-261005203907-2b8c）

> 设计依据：[`design/architecture.md`](design/architecture.md)（落点/依赖方向/回滚）、
> [`design/interfaces.md`](design/interfaces.md)（门契约/JobDef/判定真值表/兼容矩阵）、
> [`design/data-model.md`](design/data-model.md)（零 DDL/status 取值/result JSONB）、
> [`design/use-cases.md`](design/use-cases.md)（8 个场景）、
> [`design/test-cases.md`](design/test-cases.md)（打桩纪律/TC-1~TC-6/命令）。
> 需求依据：[`requirement.md`](requirement.md)（6 条 FR + D-1/D-2）。

## 1. 目标（一段人能读懂的）

给 DailyJobs 宿主装一道**交易日门**：休市日不再对着一份冻结的行情快照空跑重算，
也不再为空跑发飞书；跳过要在台账里留一行 `status='skipped'`（"跳过"和"根本没跑"必须分得开）。
门**fail-open**：日历不可用时照跑并标注降级，绝不因门而停摆；**复市首日不跳过**。
今晚 19:05 那次「22 秒 + 2 条通知、零换血」的形态，改完后应当变成一行 `skipped`。

## 2. 改动盘点（按设计逐份对照）

| 设计节 | 动作 | 文件（新增 `+` / 修改 `~`） | 卡 |
|---|---|---|---|
| interfaces §1 | 新增门模块（fail-open 取舍 + 注解，唯一消费点） | `+adapters/inbound/fastapi_app/daily_jobs/gate.py` | t1 |
| interfaces §2 | `JobDef` 末尾追加 `trading_days_only: bool = False` | `~adapters/inbound/fastapi_app/daily_jobs/defs.py` | t1 |
| interfaces §3 | `_run_job` 跳过早退（写 `skipped`、不发通知、不观测耗时） | `~adapters/inbound/fastapi_app/daily_jobs/runtime.py` | t2 |
| architecture §逐任务 | 3 个任务声明 `trading_days_only=True` | `~adapters/inbound/fastapi_app/daily_jobs/registry.py` | t2 |
| interfaces §4 | `_job_evening_pipeline` 因子段局部跳过（K 线段原样） | `~adapters/inbound/fastapi_app/daily_jobs/pipeline.py` | t3 |
| interfaces §5 / data-model §2 | 兼容与回滚核验（无 DDL、无迁移；`skipped` 对既有消费者的行为） | 测试 + `+notes/compat-rollback.md` | t4 |
| test-cases §7 / §TC-6 | 回归 + 真实休市日/复市首日观察 | `+notes/holiday-observation.md` | t5 |

**删除**：无。**新增依赖**：无。**DDL / 迁移脚本**：无（`quant.inprocess_job_runs.status` 是 `text`、无 CHECK 约束）。
**导出清单不改**：`gate.py` 是新符号，不进 `daily_jobs/__init__.py` 与 `daily_jobs_bootstrap.py` 的转发壳。

## 3. 任务表

> `DU = files×1 + anchors×0.5 + chars/2000`（容量 16 DU/卡）。全部卡 ≤ 9.3 DU，**无超容量卡**。
> 本需求**无 UI**，故「原型锚点」列一律 `—`；「关联 D-x」指 requirement.md 的裁定编号。

| key | 标题 | phase | side | depends_on | FR | files | anchors | chars | DU | 原型锚点 | 关联 D-x |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t1 | 门模块与 JobDef 字段（接口先行） | implement | backend | — | FR-1, FR-2 | 5 | 6 | 2200 | 9.1 | — | — |
| t2 | 宿主接线：`_run_job` 跳过早退 + 3 任务置位 | implement | backend | t1 | FR-1, FR-3, FR-5 | 4 | 5 | 2400 | 7.7 | — | D-2 |
| t3 | 晚间管线：因子段局部跳过（K 线段原样） | implement | backend | t1 | FR-4 | 4 | 6 | 2200 | 8.1 | — | D-2 |
| t4 | 兼容与回滚核验（零 DDL / 既有消费者行为） | test | backend | t2 | FR-3, FR-5 | 3 | 5 | 1500 | 6.3 | — | — |
| t5 | 回归 + 真实休市日/复市首日观察 | test | backend | t2, t3, t4 | FR-6 | 6 | 5 | 1600 | 9.3 | — | — |

### 每卡的实施与验收（摘要；验收均可跑）

- **t1**：新建 `daily_jobs/gate.py`，实现 `skip_non_trading_day(now=None) -> tuple[bool, dict]` /
  `is_non_trading_day(now=None) -> bool` / `verdict_info(now=None) -> dict`：判据
  `skip = (not v.is_trading_day) and (not v.degraded)`（`v = TradingDayGuard.check(now)`），
  **永不抛**（自身异常 → `(False, {'source': 'gate-error', ...})` + warning 日志）。
  在 `defs.py` 的 `JobDef` **末尾**追加 `trading_days_only: bool = False`（位置参数兼容）。
  新增 `tests/test_daily_jobs_trading_day_gate.py` 覆盖 TC-1 真值表（打桩
  `daily_jobs.gate.TradingDayGuard` 为假判定，零网络零 DB）。
  验收：`./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q -k "truth or holiday or degraded"`
  → 全过；且 `JobDef('x', t, (0,), h, 'd').trading_days_only is False`。
- **t2**：`runtime.py` 的 `_run_job` 在 `_mark_running` 之后、`_send_feishu('▶️ 每日任务开始…')`
  **之前**插入早退分支（写 `status='skipped'`、`result={'skipped': True, 'reason', 'trading_day'}`、
  `scheduler_job_runs_total{status='skipped'}`、**不**观测 duration、info 日志、`return`）；
  照跑路径在 `result` 上补 `trading_day` 注解（`degraded=True` 时另记 warning）。
  `registry.py` 给 `pool_daily_refresh` / `chip_distribution` / `evolution_fitness` 三行加
  `trading_days_only=True`（`evening_pipeline` 与其余 5 个任务不加）。
  在 t1 的测试文件追加：跳过留痕 + `_send_feishu` 零调用 + handler 未执行 + 注册表范围恰好 3 个。
  验收：`./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q` → 全过；
  用例断言 `mock_send.call_count == 0` 且 `marks[0][0] == 'skipped'`。
- **t3**：`pipeline.py` 的 `_job_evening_pipeline`：入口取一次 `is_non_trading_day()`；
  因子段改为 `if non_trading and not kline_changed and kline.get('status') != 'error': 跳过
  else: handle_factor_compute(...)`，其中
  `kline_changed = kline.get('status') != 'skipped' and (kline.get('success') or 0) > 0`；
  **K 线段（探活/覆盖度/批大小/修复/失败上抛）逐字不动**。
  新增 `tests/test_evening_pipeline_holiday_gate.py` 覆盖 TC-4 六行真值表
  （打桩 `daily_jobs.pipeline.is_non_trading_day` / `_kline_coverage` / `_probe_kline_sources` +
  源头模块 `application.services.scheduler_tasks.handle_factor_compute` /
  `infrastructure.jobs.kline_update_job.update_gem_klines`）。
  验收：`./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q` → 全过；
  关键两条：`test_holiday_fresh_kline_skips_factor`（未调用因子计算）与
  `test_trading_day_never_skips_factor`（交易日绝不跳）。
- **t4**：不写实现，写**兼容判据**：在 t1 的测试文件追加断言——
  `is_due(job, now, {'status':'skipped',...}) is False`、`catchup_due(...) is False`、
  `trigger_job` 对 `skipped` 不返回"今日已有记录"、`find_result_failure({'skipped': True, ...}) is None`、
  `find_result_failure({'kline_sync': {'skipped': 12}})` 不因 int 误判；
  并把核验结论写进 `notes/compat-rollback.md`（含 `git diff --stat` 无迁移/无 DDL 的核验记录与回滚步骤）。
  验收：`./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q`
  → 全过（既有 `TestIsDue` 三分支不回归）；`git diff --name-only` 中无
  `infrastructure/persistence/migrations/**`。
- **t5**：跑齐四条命令（见「§5 验收命令」），把输出摘要与台账 SQL 结果写进
  `notes/holiday-observation.md`：休市日（2026-10-06 或 10-07）三个任务应为 `skipped` 且当天无对应飞书；
  `evening_pipeline` 的 `result.factor_compute.status` 应为 `skipped`；
  复市首日（2026-10-08）`pool_daily_refresh` / `evening_pipeline` 应恢复 `success`。
  验收：四条命令退出码 0；`notes/holiday-observation.md` 含**实际查询输出**（不是"应该没问题"）；
  会话末 notify-guard 行 `egress=0`。

## 4. 批次与依赖顺序

- **批次 1**：t1（接口先行：门契约 + `JobDef` 字段）——被依赖者先定义，无前向引用。
- **批次 2**：t2（宿主接线，depends_on t1）、t3（晚间管线，depends_on t1）——两张卡互不依赖，可并行。
- **批次 3**：t4（兼容与回滚核验，depends_on t2）。
- **批次 4**：t5（回归 + 真实观察，depends_on t2, t3, t4）。

## 5. 验收命令（与 design/test-cases.md §7 同口径）

```bash
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q
psql -d quant_investment -c "SELECT job_id, status, result->>'reason' FROM quant.inprocess_job_runs WHERE run_date = DATE '2026-10-06' ORDER BY job_id;"
```

## 6. 边界（不做什么 · 防范围蔓延）

- 不改 `TradingDayGuard` / `trading_day_resolver` 的语义；**不**把睡着的 fail-closed 改成 fail-open。
- 不改 `evening_pipeline` 的 K 线段；不改另外 5 个任务（`watch_rule_health` / `event_calendar_check` /
  `freshness_guard` / `financial_statements` / `pool_weekly_review`）的排班与行为。
- 不碰 APScheduler 路径（`quant.scheduler_tasks` 的 11 条）与 `orchestrator_bootstrap` 的 weekday 近似。
- 不加 `DISABLE_*` 开关、不加"休市日强制重算"旁路（回滚 = 撤标志，见 design/architecture.md）。
- 与设计矛盾时**退回设计阶段**改设计，不在本阶段私改。

## 7. 批准门与下一步

提交本计划 → `reqboard_ask_confirm(target=plan)` 请人批准；**批准后自动落库任务卡并进入实施**
（批次内 `depends_on` 用本表 key 引用）。未获批准时 `reqboard_decompose` 被代码级拒绝。
