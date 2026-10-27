# DailyJobs 迁移到 APScheduler

- 执行：investor / w-0e4ae20d
- 日期：2026-10-27
- 依据：ADR-004（V2 业务定时任务统一由 V2 调度）
- 范围：11 个 `JobDef`；盯盘影子/SLA/自愈 60s 级巡检保留为执行引擎，不纳入每日 cron。

## 目标结构

```text
quant.scheduler_tasks + APScheduler  →  每日定时业务
JobRegistry                           →  command → 业务函数
盯盘 60s 级引擎                        →  仅高频执行循环
```

每日任务不再由 `daily-jobs` 宿主线程调度。`start_daily_jobs()` 保留为兼容符号，但实际启动会抛错，防止未来重新引入第二调度所有者。

## 迁移内容

新增 11 条 APScheduler 任务（生产 id 401–411）：

| job_id | cron |
|---|---|
| watch_rule_health | `30 16 * * 1-5` |
| v2_daily_cycle_reset | `35 16 * * 1-5` |
| invalid_rule_escalation | `0 17 * * 1-5` |
| event_calendar_check | `45 16 * * *` |
| freshness_guard | `20 17 * * 1-5` |
| evening_pipeline | `30 20 * * 1-5` |
| chip_distribution | `10 21 * * 1-5` |
| evolution_fitness | `35 20 * * 1-5` |
| financial_statements | `0 20 * * 6` |
| pool_daily_refresh | `5 19 * * 1-5` |
| pool_weekly_review | `0 18 * * 0` |

实现要点：

- `FunctionJob`：只做 callable → `JobResult` 适配，不重写业务逻辑。
- `apscheduler_bridge.py`：从原 `JOBS` 派生排班与 Handler，保留开始/成功/失败通知。
- 兼容 API `/api/jobs/inprocess/status` 与 `/run` 改为读取/触发 APScheduler。
- 新鲜度巡检同时读取 `scheduler_runs` 与迁移前的 `inprocess_job_runs`，避免历史失败失明。
- 旧的 `daily-pool-refresh`（id 258，23:00）已禁用；股票池每日刷新唯一所有者改为 19:05 的 `pool_daily_refresh`。
- 迁移脚本：`infrastructure/persistence/migrations/20261027_dailyjobs_to_apscheduler.py`，支持 `--apply / --activate / --rollback`。

## 切换顺序

1. 在 `quant_test` 完成 apply/activate/状态读取验证。
2. 生产库执行 `--apply`：创建 11 条禁用任务，禁用 258。
3. 确认 22:38 后无其他窗口新增 V2 改动；确认无运行中 APScheduler 任务。
4. 重启 V2：启动日志出现 `Registered: migrated DailyJobs` 与 `Watch interval engine started`，不再出现 `daily-jobs host thread started`。
5. 执行 `--activate` 并 `POST /api/scheduler/reload`；jobstore 11/11 记录全部存在且未来触发。

切换当晚没有手动触发任何迁移任务；首个真实运行为 2026-10-28 16:30。

## 验证

- 新增/兼容测试 **94 passed**（主工作区真实组合状态）。
- 迁移脚本在 quant_test 完成 apply → activate → 11/11 校验。
- 生产 jobstore：11/11 新任务存在且 `next_run_time` 在未来，`task_258` 已移除。
- `/api/jobs/inprocess/status` 返回 11 条任务，`backend=apscheduler`。
- 切换当天 APScheduler 尚无记录时，状态 API 回读旧台账，避免把已成功的 9 条任务显示为 `not_run`。
- 快照：`agent-dh/.dsh-data/state/dailyjobs-apscheduler-20261027/`。

## 已知差异与后续

- APScheduler 不复制旧宿主的“失败 2 小时后自动重试”。失败仍会落 `scheduler_runs`、发告警并在状态 API 可见；是否增加统一重试策略需单独设计，不能靠复制 cron 行制造双跑。
- 3 个盯盘间隔巡检仍由执行引擎负责；当前环境开关为默认关闭。
- V13 的 06:30 单独日检与 14:30 全策略执行重叠属于另一项待治理问题，本次未改交易行为。
- 首日复核计划：2026-10-28 盘后核对 401–410 的真实运行、旧 `inprocess_job_runs` 不应再新增当日行。

## 回滚

代码回滚需恢复 `main.py` 的 DailyJobs 启动接线；排班回滚执行：

```bash
PYTHONPATH=. ./venv/bin/python \\
  infrastructure/persistence/migrations/20261027_dailyjobs_to_apscheduler.py --rollback
```

回滚会禁用 11 条新任务并重新启用旧的 `daily-pool-refresh`，随后调用 `/api/scheduler/reload`。不要在交易时段做切换。
