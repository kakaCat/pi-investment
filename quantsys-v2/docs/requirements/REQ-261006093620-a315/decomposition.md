# 拆分计划（REQ-261006093620-a315）

> 设计依据：[`design/architecture.md`](design/architecture.md)（落点/执行期 vs 排班期/人工旁路/回滚）、
> [`design/interfaces.md`](design/interfaces.md)（门签名/策略真值表/executor 形参/仓储新方法/错误语义）、
> [`design/data-model.md`](design/data-model.md)（三值列 + 迁移回滚/台账三态/消费者矩阵）、
> [`design/use-cases.md`](design/use-cases.md)（9 个场景）、
> [`design/test-cases.md`](design/test-cases.md)（13 行真值表/打桩点迁移/7 条负向测试/命令）。
> 需求依据：[`requirement.md`](requirement.md)（8 条 FR + D-1~D-6）。

## 1. 目标（一段人能读懂的）

给 v2 的**库表调度（② APScheduler）**装上与 DailyJobs 同一道**交易日门**：休市日不再对着冻结快照
空跑盘前扫描/信号/周报，也不再把这些空跑记成 `success`；跳过要在台账留一行 `status='skipped'`
（"跳过"与"根本没跑"分得开）。门 **fail-open**（日历不可用就照跑并标注降级），**复市首日不跳过**，
**人工触发照跑**。今晚那行
`Running job "pre-market-scan" … 2026-10-06 09:25` + `run_id=3379 success`，改完后应当变成一行 `skipped`。

## 2. 改动盘点（按设计逐份对照）

| 设计节 | 动作 | 文件（新增 `+` / 修改 `~`） | 卡 |
|---|---|---|---|
| interfaces §1、architecture「落点」 | 判据抽到 application 层：策略入口 + 既有三函数搬迁 | `+application/services/trading_day_gate.py` | t1 |
| data-model §1~§4 | 三值列 + CHECK + 8 行回填 + ORM 同列 + 两库迁移 | `+infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`、`~infrastructure/persistence/orm/models/scheduler.py` | t2 |
| architecture「打桩点迁移」 | ③ 退为薄转发 + 三处 `monkeypatch` 目标迁移 | `~adapters/inbound/fastapi_app/daily_jobs/gate.py`、`~tests/test_daily_jobs_trading_day_gate.py` | t3 |
| data-model §5、interfaces §5 | 台账三态：`complete_run_skipped` + 抽私有 `_finish_run` | `~adapters/outbound/repositories/scheduler_repository.py` | t4 |
| interfaces §3 | 执行期接门：`manual` 形参 + 判策略 + 跳过落账 | `~infrastructure/scheduler/job_executor.py` | t5 |
| interfaces §4 | 人工旁路：投一次性 `manual=True` job（不再 `modify_job`） | `~infrastructure/scheduler/apscheduler_service.py` | t6 |
| data-model §5「消费者矩阵」 | 巡检口径同步（两处**极性相反**的判据） | `~application/services/should_have_run.py`、`~scripts/scheduler_watchdog.py` | t7 |
| test-cases §4 | 端到端验收 + 真实台账观察 + 回滚演练 | `+docs/requirements/REQ-261006093620-a315/verification.md`、`+notes/acceptance-run.md` | t8 |

**删除**：无（`daily_jobs/gate.py` 保留为薄转发，公开名字与导入路径不变）。
**新增依赖**：无第三方依赖。
**DDL**：有 1 处加列（`trading_day_policy`）+ 1 个 CHECK 约束；**回滚不需要 DDL**（见 §6）。

## 3. 任务表

> `DU = files×1 + anchors×0.5 + chars/2000`（容量 16 DU/卡）。最大 8.3 DU，**无超容量卡**。
> 本需求**无 UI**，故「原型锚点」列一律 `—`；「关联 D-x」指 requirement.md 的裁定编号。

| key | 标题 | phase | side | depends_on | FR | files | anchors | chars | DU | 原型锚点 | 关联 D-x |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t1 | 判据真源：`trading_day_gate` 模块与策略入口 | implement | backend | — | FR-1, FR-2, FR-5 | 3 | 8 | 2600 | 8.3 | — | D-2 |
| t2 | 数据契约：三值列 + CHECK + 8 行回填 + ORM | implement | backend | — | FR-1, FR-4, FR-5 | 3 | 6 | 2800 | 7.4 | — | D-4, D-6 |
| t3 | ③ 退为薄转发 + 打桩点迁移（行为零变化） | implement | backend | t1 | FR-3, FR-8 | 4 | 5 | 2000 | 7.5 | — | D-4 |
| t4 | 仓储层：`complete_run_skipped` + 抽 `_finish_run` | implement | backend | t2 | FR-3 | 2 | 5 | 2200 | 5.6 | — | — |
| t5 | 执行期接门与跳过落账（含 `manual` 旁路） | implement | backend | t1, t2, t4 | FR-2, FR-3, FR-4, FR-6, FR-7 | 2 | 6 | 2600 | 6.3 | — | D-1, D-3, D-5 |
| t6 | 人工触发改投一次性 `manual=True` job | implement | backend | t5 | FR-6 | 2 | 4 | 2000 | 5.0 | — | D-5 |
| t7 | 巡检口径同步（`should_have_run` + watchdog） | implement | backend | t5 | FR-3 | 3 | 5 | 2200 | 6.6 | — | D-3 |
| t8 | 端到端验收、真实台账观察与回滚演练 | test | backend | t1~t7 | FR-8 | 2 | 5 | 2000 | 5.5 | — | D-1, D-4 |

> `t8` 的 `depends_on` 展开：`t1, t2, t3, t4, t5, t6, t7`。

### 覆盖对照表（需求条款 ↔ 计划 key）

| 需求条款 | 接收任务 | 承接说明 |
|---|---|---|
| FR-1 | t1, t2 | 逐任务声明的载体：判据模块的策略入口 + `trading_day_policy` 列（缺省 `always` = 行为不变） |
| FR-2 | t1, t5 | fail-open 语义在 t1 定义（唯一判据），由 t5 在执行期消费 |
| FR-3 | t3, t4, t5, t7 | 留痕（t4 记账方法 / t5 落账）、不打扰（t5 不发通知）、不误报（t7 巡检口径同步） |
| FR-4 | t2, t5 | 逐任务策略由 t2 回填 8 行、t5 在执行期按行读取 |
| FR-5 | t1, t2 | 周末分档：t1 的 `holidays` 策略语义 + t2 给 `#232` 回填 `holidays` |
| FR-6 | t5, t6 | `manual` 形参（t5）+ 人工触发投一次性 job（t6） |
| FR-7 | t5, t2 | **生效性**：t5 把门放执行期 ⇒ 改策略即生效、无需 reload；t2 的 ORM 同列 + 两库迁移保证重启后判定一致 |
| FR-8 | t3, t8 | 回归锁（t3 的打桩点迁移 + 证伪断言）+ 真实台账观察与回滚演练（t8） |

> 8 条 FR **全部有接收任务**，无「本轮不做」条款。

## 4. 每卡的实施与验收（摘要；验收均可跑）

- **t1**：新建 `application/services/trading_day_gate.py`——把
  `adapters/inbound/fastapi_app/daily_jobs/gate.py` 的三个函数（`verdict_info` /
  `skip_non_trading_day` / `is_non_trading_day`）**原样搬入**（签名逐字不变），并新增
  `should_skip(policy, now=None) -> (bool, dict)` 与 `POLICY_ALWAYS/TRADING_DAYS/HOLIDAYS`：
  `always` → 不跳；`trading-days` → `(not is_trading_day) and (not degraded)`；
  `holidays` → `source == 'trading-calendar-holiday' and (not degraded)`；
  **未知/None → 不跳 + `policy_unknown=True` + warning**。判据只用 `TradingDayGuard.check(now)`，
  函数**永不抛**。新增 `tests/test_scheduler_trading_day_gate.py`：13 行真值表
  （桩打在 `application.services.trading_day_gate.TradingDayGuard`）+ `future` 反例锁。
  验收：`./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q` → 全过；
  `./venv/bin/python -c "from application.services.trading_day_gate import should_skip as s; print(s('always')[0], s('holiday')[0])"` →
  `False False`（`always` 与未知值都不跳）。
- **t2**：写迁移 `infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py`：
  `ADD COLUMN IF NOT EXISTS trading_day_policy varchar(16) NOT NULL DEFAULT 'always'` +
  `CHECK (... IN ('always','trading-days','holidays'))`；按 **id** 回填 8 行
  （250/247/242/259/249/261/237 = `trading-days`；**232 = `holidays`**），rowcount=0 只告警；
  缺省 dry-run、`--apply` 才写、`lock_timeout`、verify 段防空表。
  `infrastructure/persistence/orm/models/scheduler.py` 加同名列（`String(16), nullable=False,
  server_default='always'`）。**两个库都跑**（生产 + `quant_test`）。
  验收：迁移 dry-run 退出码 0；`--apply --dsn postgresql://mac@127.0.0.1:5432/quant_test` 后
  `psql -d quant_test -c "\d quant.scheduler_tasks"` 出现该列；
  `./venv/bin/python -m pytest tests/test_orm_db_drift.py -q` 全过；
  数据断言：8 行策略值逐一等于期望、其余行 `= 'always'`。
- **t3**：`adapters/inbound/fastapi_app/daily_jobs/gate.py` 改为**薄转发**——`from
  application.services.trading_day_gate import (SOURCE_GATE_ERROR, verdict_info,
  skip_non_trading_day, is_non_trading_day)`，**不留任何判定实现**；③ 的 `runtime.py` /
  `pipeline.py` 的导入路径与调用方式**一行不改**。
  `tests/test_daily_jobs_trading_day_gate.py` 的三处
  `monkeypatch.setattr(gate_mod, 'TradingDayGuard', ...)`（`:80/131/139`）目标改到
  `application.services.trading_day_gate`，并**新增一条证伪断言**：patch 新模块后
  `daily_jobs.gate.skip_non_trading_day()` 的结论确实随之改变（桩若失效即红）。
  验收：`./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q` → 全过；
  `./venv/bin/python -c "from adapters.inbound.fastapi_app.daily_jobs import gate; print(gate.skip_non_trading_day.__module__)"`
  → `application.services.trading_day_gate`。
- **t4**：`adapters/outbound/repositories/scheduler_repository.py` 抽出私有
  `_finish_run(run_id, status, result=None, error=None, completed_at=None)`（收尾逻辑：
  `completed_at`/`duration_ms`/`result` 过 `_json_safe`/`config.last_status`/`next_run_at` 重算），
  `complete_run` **签名与返回值逐字不变**、内部改调它；新增
  `complete_run_skipped(run_id, result=None, completed_at=None) -> bool`（`last_error=None`、失败不抛）。
  验收：新增单测断言 `complete_run_skipped` 后该行 `status='skipped'`、`completed_at` 非空、
  `result` 含 `date`/`Decimal` 也能落库、`config.last_status='skipped'`、`last_error IS NULL`；
  `./venv/bin/python -m pytest tests/test_scheduler_run_result_json.py tests/test_scheduler_inner_failure.py -q` 全过。
- **t5**：`infrastructure/scheduler/job_executor.py`：`execute_scheduled_job(task_id, manual=False)`
  → `_execute_scheduled_job_impl(task_id, manual=manual)`；在 `is_enabled` 检查之后、
  **并发检查之前**插入门：`manual=True` 不判门；否则 `policy = task.get('trading_day_policy')
  or 'always'`、`skip, info = should_skip(policy, now)`，跳过则 `create_run` →
  `complete_run_skipped(run_id, result={skipped,reason,trading_day_source,degraded,policy})` →
  一行 info 日志 → `return`；**不调** `_execute_command`、**不调** `_report_failure_to_sink`、
  不发 Agent OS 事件、不写 `last_error`。照跑路径逐字不变。
  验收：`./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q` → 全过，
  含四条负向断言：休市日 `_execute_command` 零调用、`_report_failure_to_sink` 零调用、
  跳过行 `last_error IS NULL`、交易日 `complete_run_skipped` 零调用；且 `manual=True` 照跑。
- **t6**：`infrastructure/scheduler/apscheduler_service.py` 的 `trigger_task_now`：保留
  "job 不存在 → `ValueError`"，把 `modify_job(next_run_time=now)` 换成
  `add_job(func=execute_scheduled_job, trigger=DateTrigger(run_date=now), args=[task_id],
  kwargs={'manual': True}, id=f'manual_{task_id}_{int(time.time())}', replace_existing=False,
  misfire_grace_time=None)`。同步改 `tests/infrastructure/test_apscheduler_service.py::test_trigger_task_now`。
  验收：`./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q` → 全过；
  断言 `scheduler.get_job('task_1').next_run_time` **与触发前相等**（不再被扰动），
  且存在 `manual_1_*` job、其 `kwargs['manual'] is True`。
- **t7**：`application/services/should_have_run.py` 把"最近一次真执行（`status != 'missed'`）"
  拆成两套**写出来的**集合：`NOT_MISSED_STATUSES = ('success','failed','skipped')`（判"该槽位是否已处理"）
  与 `REAL_RUN_STATUSES = ('success','failed')`（`last_run_at` 呈现用）；**不改** `missed` 的告警语义。
  `scripts/scheduler_watchdog.py:289/390` 的 `status='success'` 改为 `status IN ('success','skipped')`。
  在 `tests/test_should_have_run.py` **增量**补用例。
  验收：`./venv/bin/python -m pytest tests/test_should_have_run.py -q` → 全过；两条关键断言在场：
  `skipped` 不进 missed 列表；**`missed` 仍然进 missed 列表**（只豁免正常跳过）。
- **t8**：跑齐 §5 的命令，把**实际输出**写进 `notes/acceptance-run.md`，并准备
  `docs/requirements/REQ-261006093620-a315/verification.md`（交付结论 + 证据清单）；
  另做**回滚演练**：`UPDATE ... SET trading_day_policy='always'` 后确认无需 reload/重启即恢复照跑，
  再改回策略值。
  验收：6 条命令退出码 0；`notes/acceptance-run.md` 含实际查询输出（不是"应该没问题"）；
  休市日（2026-10-07）挂门任务为 `skipped` 且无通知、复市首日（2026-10-08）恢复 `success`；
  回滚演练有 SQL 与前后读数；会话末 notify-guard 行 `egress=0`。

## 5. 批次与依赖顺序

- **批次 1**：t1（判据真源，nobody depends on nothing）、t2（数据契约）——互不依赖，可并行。
- **批次 2**：t3（depends_on t1）、t4（depends_on t2）——互不依赖，可并行。
- **批次 3**：t5（depends_on t1, t2, t4）——执行期接门，是本次改动的**接线中心**。
- **批次 4**：t6（depends_on t5）、t7（depends_on t5）——互不依赖，可并行。
- **批次 5**：t8（depends_on t1~t7）——链尾总验收。

**无前向引用**：每条 `depends_on` 都指向前一批次已定义的 key。

## 6. 验收命令（与 design/test-cases.md §4 同口径）

```bash
./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q
./venv/bin/python -m pytest tests/infrastructure/test_scheduler_skip_ledger.py -q
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
./venv/bin/python -m pytest tests/test_should_have_run.py tests/test_orm_db_drift.py -q
./venv/bin/python -m pytest tests/infrastructure/test_apscheduler_service.py -q
psql -d quant_investment -c "select t.id, t.name, t.trading_day_policy, r.status, r.result->>'reason' from quant.scheduler_runs r join quant.scheduler_tasks t on t.id=r.task_id where r.started_at::date = DATE '2026-10-07' order by t.id;"
```

## 7. 边界（不做什么 · 防范围蔓延）

- 不改 `TradingDayGuard` / `trading_day_resolver` 的语义（含"未来 → 非交易日"的保守口径）；
  **不**把 ③ 的 fail-open 语义反向灌进守卫。
- 不改 ③ 的判定行为：`daily_jobs/gate.py` 只许变薄，不许变义；`runtime.py` / `pipeline.py` 一行不改。
- 不改任何 cron 表达式；不动 `orchestrator_bootstrap` 的 weekday 近似；不动 Agent OS 托管任务。
- 不删 `trading_day_policy` 列（回滚 = 改回 `always`，属数据动作不属 DDL）；不加 `DISABLE_*` 开关。
- 不追「早盘要点」卡片的产出方（D-3 明确范围只到 ② 库表调度）。
- 与设计矛盾时**退回设计阶段**改设计，不在本阶段私改（覆盖 2）。

## 8. 批准门与下一步

提交本计划 → `reqboard_ask_confirm(target=plan)` 请人批准；**批准后自动落库任务卡并进入实施**
（批次内 `depends_on` 用本表 key 引用）。未获批准时 `reqboard_decompose` 被代码级拒绝。
