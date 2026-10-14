# 拆分计划（REQ-261004154902-a7cd）

> 设计依据：[`design/design.md`](design/design.md)（总览）+
> [`architecture.md`](design/architecture.md) / [`interfaces.md`](design/interfaces.md) /
> [`data-model.md`](design/data-model.md) / [`test-cases.md`](design/test-cases.md) /
> [`use-cases.md`](design/use-cases.md)。
> 前置止血记录：[`notes/stopgap-2026-10-04.md`](notes/stopgap-2026-10-04.md)。

## 0. 已完成的前置动作（不是本计划的任务卡）

**周一止血（2026-10-04，用户裁定后执行）**：`scheduler_tasks.id=249` 置 `is_enabled=false`
并 `POST /api/scheduler/reload`（jobstore 中 `task_249` 已消失）；两笔 8/24 搁浅挂单
（id=7/8）置 `status='expired'` + `fail_reason`。原值与回滚命令见止血记录。
**这不修误判本身**，只是"先别开火"——正式修正由 t3/t5 承担。

## 1. 目标（一段人能读懂的）

让 V13 及其所在的自动链路**说真话**：干了就说干了、没干就说没干、失败就说失败并**主动告诉你**；
休市日不开火、复市首日不跳过；挂单不会无声搁浅；账本不再自相矛盾。

## 2. 改动盘点（按设计逐份对照）

| 设计节 | 动作 | 文件（新增 `+` / 修改 `~`） | 卡 |
|---|---|---|---|
| §1/§2 | 结果契约 + 失败出口 | `+application/observability/run_outcome.py`、`+failure_sink.py` | t1 |
| §2.2 | 日检消费返回值、修通知方法缩进 | `~live_trading/simulation_trader.py`、`~application/services/strategy_service.py` | t2 |
| §3 | 交易日判定收敛到日历链 | `~application/services/trading_day_guard.py`、`~trading_day_resolver.py`、`~trading_calendar_service.py` | t3 |
| §7 | 撮合批量不中断 + 时段护栏 + 过期 | `~application/services/account_trading_service.py` | t4 |
| §4 | cron 口径、misfire 语义、missed 落库 | `~infrastructure/scheduler/apscheduler_service.py`、`~adapters/outbound/repositories/scheduler_repository.py` | t5 |
| §9 | 调度路径失败的人工通道 | `~infrastructure/scheduler/job_executor.py`、`~infrastructure/error_reporting/agent_os_reporter.py`、`~adapters/inbound/fastapi_app/daily_jobs/alerting.py` | t6 |
| §8 | 探活加调度活性 + 盘点器 + 节流 | `~tools/health_probe.py`、`+application/services/should_have_run.py`、`+tools/check_should_have_run.py` | t7 |
| §9 | 通知渠道兜底 + formatter + 静默点升格 | `~domain/notification/policies/notification_policy.py`、`~infrastructure/notification/channels/agent_channel.py`、`~infrastructure/notification/formatters/feishu_formatters.py`、`~application/notification/notification_factory.py`、`~application/strategies/v13_use_case.py`、`~application/risk/intraday_risk_service.py` | t8 |
| §5 | 配置单源 + 生效值可见 | `~application/services/strategy_service.py`、`~live_trading/config_simulation.yaml`、`~live_trading/configs/strategies/v13.yaml`、`+tools/check_strategy_config_effective.py` | t9 |
| §6 | 未接线链路修实 + 假断言改正 | `~application/strategies/v13_config.py`、`~v14_config.py`、`~domain/strategies/xgboost_strategy.py`、`~infrastructure/jobs/strategy_trading_job.py`、`~tests/regression/test_strategy_config_refactor.py` | t10 |
| §10 | 超卖拦截 + 对账器 | `~live_trading/simulation_trader.py`、`~application/services/account_trading_service.py`、`+tools/reconcile_sim_account.py` | t11 |
| §10/§14 | 历史虚增标记为脏 + 统计排除 | `~tools/reconcile_sim_account.py`、`+docs/.../notes/legacy-cash-disposition.md` | t12 |
| §12 | 假绿灯结构门禁 | `~pytest.ini`、`~tests/test_scheduled_jobs_account_value.py` | t13 |
| 全 | 端到端冒烟与验收证据 | `+tools/check_v13_chain_health.py`、验收材料 | t14 |

## 3. 任务表

> `DU = files×1 + anchors×0.5 + chars/2000`（容量 16 DU/卡）。全部卡 ≤ 10.2 DU，**无超容量卡**。

| key | 标题 | phase | side | depends_on | FR | files | anchors | chars | DU |
|---|---|---|---|---|---|---|---|---|---|
| t1 | 结果契约与失败出口（RunOutcome + FailureSink） | implement | backend | — | FR-1,2,9 | 4 | 5 | 2400 | 7.7 |
| t2 | 策略日检如实上报 + 修回通知方法 | implement | backend | t1 | FR-1,2 | 4 | 7 | 2600 | 8.8 |
| t3 | 交易日判定收敛到日历链 | implement | backend | — | FR-3 | 4 | 6 | 2400 | 8.2 |
| t4 | 挂单撮合不中断 + 时段护栏 + 过期 | implement | backend | t1 | FR-7 | 2 | 6 | 2000 | 6.0 |
| t5 | cron 口径 + misfire 语义 + missed 落库 | implement | backend | — | FR-4,8 | 3 | 6 | 2400 | 7.2 |
| t6 | 调度失败的飞书兜底 + 告警覆盖面 | implement | backend | t1 | FR-2,8,9 | 4 | 5 | 2200 | 7.6 |
| t7 | 探活调度活性 + 「该跑没跑」盘点器 | implement | backend | t5 | FR-8 | 4 | 6 | 2600 | 8.3 |
| t8 | 通知渠道兜底 + 补 formatter | implement | backend | — | FR-9 | 6 | 6 | 2400 | 10.2 |
| t9 | 配置单源 + 生效值断言 | implement | backend | — | FR-5 | 5 | 5 | 2400 | 8.7 |
| t10 | 未接线链路修实 + 删假断言 | implement | backend | — | FR-6 | 6 | 5 | 2000 | 9.5 |
| t11 | 账本超卖拦截 + 对账器 | implement | backend | t1 | FR-10 | 4 | 5 | 2000 | 7.5 |
| t12 | 历史虚增标记为脏 + 统计排除 | analysis | backend | t11 | FR-10 | 2 | 3 | 1200 | 4.1 |
| t13 | 假绿灯结构门禁（pytest 配置级） | test | backend | — | FR-1,5,6,10 | 2 | 3 | 900 | 4.0 |
| t14 | 端到端冒烟 + 验收证据 | test | fullstack | t2,t3,t4,t5,t6,t7,t8,t9,t10,t11,t12,t13 | FR-1..FR-10 | 2 | 6 | 1600 | 5.8 |

### 每卡的实施与验收（摘要；验收均可跑）

- **t1**：新增结果契约与失败出口模块。验收：`pytest tests/test_run_outcome.py tests/test_failure_sink.py -q` 全过，且断言 `ok` 只由 `executed and error is None` 派生。
- **t2**：日检消费 `rebalance()` 返回值；把 `_send_rebalance_notification` / `_format_rebalance_content` 移回类体；三态映射。验收：`pytest tests/live_trading/test_daily_check_contract.py -q`；`hasattr(SimulationTrader,'_send_rebalance_notification') is True`。
- **t3**：判定链改走日历。验收：`2026-10-05/06/07 → False`、`2026-10-08 → True`；`pytest tests/test_trading_day_guard.py -q`。
- **t4**：单笔异常续跑 + `skipped_off_hours`/`expired` + 时段护栏。验收：`pytest tests/services/test_pending_orders.py -q`；非交易时段调用时 `failed == 0`。
- **t5**：misfire 语义区分 NULL/显式值；监听 `EVENT_JOB_MISSED` 写 `scheduler_runs(status='missed')`。验收：`build_cron_trigger('30 14 * * 1-5')` 的 `next_run_time.hour == 14`；人为造一次 missed 后库里有 `missed` 行。
- **t6**：失败分支加飞书投递；`agent_os_reporter` 加兜底；`_job_failure_watch` 覆盖 `scheduler_tasks`；通知卡片补 `auto_disabled/missed/stale` 字段。验收：8080 不可达时触发失败 → 日志三行证据且飞书收到。
- **t7**：探活加 `scheduler_liveness` 与 `DISABLE_*` 检查；盘点器共用判定。验收：`tools/check_should_have_run.py` 对"人为改成 1 分钟前"的任务报 `missed` 且**只告警一次**。
- **t8**：渠道兜底追加、`AgentChannel.supports()` 不再恒真、补 REBALANCE/RISK_ALERT formatter、`debug`→`warning`。验收：`select_channels('rebalance')` 与 `('risk_alert')` 均含 `feishu`。
- **t9**：全量覆盖 + 生效值日志 + 一致性检查器。验收：`tools/check_strategy_config_effective.py` 退出码 0。
- **t10**：真实模型/因子路径；`reference_capital` 注入；`success`→`ok`；删"不存在的路径"断言。验收：`pytest tests/regression/test_strategy_config_refactor.py tests/test_v13_chain_wiring.py -q`。
- **t11**：卖出前净额校验 + 对账器。验收：`tools/reconcile_sim_account.py --account v13_simulation` 超卖清单 0 行。
- **t12**：按用户裁定"标记为脏并从统计排除"落地口径与记录。验收：对账器"差额解释"逐项覆盖；`notes/legacy-cash-disposition.md` 落盘且含人确认。
- **t13**：`pytest.ini` 把 `PytestReturnNotNoneWarning` 升级为错误；Fake 与真实仓储签名一致性用例。验收：故意写一个 `return True` 的用例会让测试**红**。
- **t14**：一条命令给出"应跑未跑 / 成交 / 通知"三张表。验收：`tools/check_v13_chain_health.py` 退出码 0 + 验收材料（`reqboard_submit(kind=verification)` 的 evidence）。

## 4. 拆分期补充（稳定性审计落地项 → 已并入卡）

| 审计发现（`logs/launchd-api.log` / 库实证） | 并入 |
|---|---|
| `misfire_grace_time` 全 NULL→有效 300 秒，跳过**不写 `scheduler_runs`、不告警**（10-02 15:30 信号执行晚 8:37、10-03/10-04 数据质量检查晚 5:23/24:42 均被静默跳过） | t5（missed 落库）、t7（漏跑可见） |
| APScheduler 失败只上报已下线的 8080 → `agent-os ingest POST failed (dropped)` **1696 次**；`_job_failure_watch` 只覆盖 9 个 DailyJobs，不含 11 张调度卡 | t6 |
| `DISABLE_*` 开着时探针仍报 healthy（10-01 21:48–10-02 08:21 零 run） | t7 |
| `next_run_at` 是死字段：看板显示"逾期 21 天"（242/249），真实排期在 `public.apscheduler_jobs` | t5 |
| 盯盘三个 interval 巡检因 `WATCH_TODO_ENABLED` 默认 false **不注册**；WatchEngine 空转 27 小时（2044 次报错）无人知 | t7（登记为"应跑未跑"覆盖范围，实施时确认开关） |
| `evening_pipeline` K 线同步"成功 0 只 / 未覆盖 5271 只"却记 success（嵌套失败未下钻） | t1/t6（失败判定口径） |
| `event_calendar_check` 记账假失败（handled 成功、UPDATE 失败） | t6（同源：记账失败必须可见） |

## 5. 不在本次范围

模型/因子算法与调参、收益评价、表结构变更、`simulation_trader.py` 的调仓算法重写、
第四条调度路径（`crontab` 里的 `scan_and_save.py`）收编——均超出本需求边界 B3。
