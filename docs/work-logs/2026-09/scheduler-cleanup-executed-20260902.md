# 调度任务双域清理执行报告（2026-09-02）

> 执行窗口：w-8366e526（investor）｜执行日期：2026-09-02 20:30
> 授权来源：用户指令"业务的、agent 的要分开，重复的要去重，不用的可以直接删除"
> 备份：`/tmp/scheduler_backup_20260902/scheduler_backup.sql`（pg_dump，609 行，无错误）

## 一、清理前状态与发现的问题

### 1. 任务分布（清理前）

| 域 | 表 | enabled | disabled | 合计 |
|----|----|---------|----------|------|
| v2 业务调度 | `quant.scheduler_tasks` | 30 | 48 | 78 |
| Agent OS（Go cron） | `public.tasks` | 17 | 26 | 43 |

### 2. 架构基线（ADR-002）

- **v2（:5001 APScheduler）** = 业务任务主调度，实际运行引擎是 `APSchedulerService`（`main.py:167-171`），从 `quant.scheduler_tasks` 加载 enabled-only 任务到 `public.apscheduler_jobs` jobstore。
- **Agent OS（:8080 Go cron）** = agent 提醒任务（dsh-native 执行器），存 `public.tasks`。
- **dh（:13080）** = 执行器，轮询 Agent OS，只执行 `payload.executor=='dsh-native'` 的 cron+prompt 任务。

### 3. 排查发现的关键故障（清理前实测）

1. **v2 禁用不生效——disabled 任务仍在 jobstore 执行**：
   - `scheduler_async.py` 的 enable/disable/delete 只写 DB 行（走旧 `SchedulerService`），**不触发 APScheduler `reload_tasks()`**。
   - 实锤：jobstore 34 个 job 中混入 disabled 任务 234/256/267/272，且当日真实执行（234 因子计算 08:00 success、256 K线 09:40 failed、267 筹码 10:30 success）。
2. **Agent OS → v2 webhook 桥持续重建僵尸行**：
   - v2 `scheduler_webhook.py` 的 `_write_run_to_database`：job_name 在 `scheduler_tasks` 找不到时自动 `add_task`（cron='managed_by_agent_os'，command='agent_os_webhook'）再 disable → 导致 276-317 段 30 个 managed_by_agent_os 僵尸行被 OS 侧触发器持续写入 run 记录（当日仍有 276/278/290/306/315/316/317 等 15 个僵尸 run）。
   - 即使 Agent OS 侧已 disabled 的任务也在触发（316 pending_orders_match 对应 OS disabled 任务 09:31 仍写入）。
3. **双触发实锤（signal_perf_backfill_daily）**：v2 311 enabled（原生 cron `45 15 * * 1-5`）+ Agent OS 0c523c94 webhook 同刻触发 → 当日 2 次 run。
4. **Agent OS 侧遗留 26 个 disabled webhook 型任务**：全部是 v2 迁移前的 webhook 桥残留，与 v2 原生任务一一重复。

## 二、执行清理

### 1. Agent OS 侧（`public.tasks`）删除 29 个

通过 Agent OS API `DELETE /api/v1/scheduler/tasks/{id}`（Go `scheduler.Delete`：移除 cron entry + DB 级联删 task_runs）：

- **26 个 disabled 僵尸**：chan_knowledge_distill_weekly / chan_scan_daily / chip_distribution_update / daily_equity_snapshot / data_pipeline_daily / data_pipeline_weekly / data_quality_check_daily / factor_compute_daily / financial_data_update / financial_statement_update / kline_update / market_perception_daily / market_style_update / pending_orders_match / pool_refresh_daily / report_weekly / risk_check_weekly / signal_execution_daily / signal_generate_buy / signal_generate_sell / strategy_discover_weekly / strategy_validate_daily / v13_daily_check / v13_risk_check / v13_verification / v13_weekly_report
- **3 个 enabled 重复/冗余**（用户确认）：
  - `signal_perf_backfill_daily`（webhook）— 与 v2 311 原生重复 → 去重保留 v2
  - `v2_health_check`（webhook）— 与 scheduler_watchdog（每 15 分钟 zombie/missed 扫描）职责重叠 → 删除
  - `daily-kline-sync-temp`（dsh-native）— 已由 v2 daily_jobs host 自动接管 K线同步 → 冗余

**删除后：43 → 14 个**（全部 enabled dsh-native agent 域任务，均 watchdog:skip）。

### 2. v2 侧（`quant.scheduler_tasks`）删除 48 个 disabled

直接 SQL 物理删除（FK `scheduler_runs.task_id` CASCADE 级联清 run 历史，已备份）：

- 30 个 `managed_by_agent_os` 僵尸镜像（276-299 段 + 306/309/310/315/316/317，command=agent_os_webhook）
- 9 个英文名重复任务（243-248 / 254 / 257 / 259，对应 enabled 中文版 232-238 等）
- 4 个已禁用的中文名任务（234 因子计算 / 267 筹码 / 272 财报 / 256 创业板K线，均由 daily_jobs host 或 v2 enabled 版接管）
- 5 个临时/测试/废弃（239 华润三九监控 / 255 Unnamed / 260 恐慌抄底 / 300 morning_ai_analysis / 305 market_perception_daily_snapshot）
- 244 daily-data-update（已软删 `_deleted_at` 标记，物理清除）

**删除后：78 → 30 个**（全部 enabled 业务任务）。

### 3. reload APScheduler 同步 jobstore

`POST /api/scheduler/reload`（`remove_all_jobs()` + 重载 enabled-only）：

- jobstore：34 → **30 个**，全部对应 v2 enabled 任务，disabled 残留 job（task_234/256/267/272）清除。

## 三、清理后状态

| 域 | enabled | disabled | jobstore | 说明 |
|----|---------|----------|----------|------|
| v2 业务 | 30 | 0 | 30 ✓ | 纯业务任务，APScheduler 原生调度 |
| Agent OS | 14 | 0 | — | 纯 agent 提醒（dsh-native），无 webhook 型残留 |

- **无孤儿 run**：`scheduler_runs`/`task_runs` 均无悬空引用。
- **webhook 风暴停止**：Agent OS 已无 webhook 型任务 → v2 不会再自动重建 managed_by_agent_os 行。
- **watchdog 不受影响**：只对比 enabled 任务；v2 30 个全在 jobstore 有 job，Agent OS 14 个全 `watchdog:skip`。
- **进程健康**：v2 :5001（PID 1545）、agent-os :8080（PID 3179）、dh :13080、scheduler-watchdog launchd 均正常运行。

## 四、保留确认（未删除）

- v2 30 个 enabled 业务任务全保留（今日均成功执行）。
- Agent OS 14 个 enabled 任务保留，含：
  - `geer-take-profit-0901`（002241 歌尔分批止盈提醒，持仓 600 股浮盈 +7.19%，目标未到）
  - `signal-perf-verify-0903`（2026-09-03 一次性验证，触发前勿删）

## 五、经验沉淀（防复发）

1. **v2 调度改动的正确顺序**：enable/disable/delete 后必须调 `POST /api/scheduler/reload` 同步 APScheduler jobstore，否则 disabled 任务仍会执行。建议后续在 `scheduler_async.py` 的 enable/disable 端点内自动调用 reload。
2. **managed_by_agent_os 行清理必须先拆源头**：先删 Agent OS 侧任务（停 webhook），再删 v2 侧僵尸行，否则 webhook 会自动重建。本次顺序：Agent OS（29）→ v2（48）→ reload。
3. **Agent OS 侧 disabled 任务也会触发 webhook**（Go cron 内存态与 DB 不一致的历史残留），DB disabled 不等于 cron 停止——统一走 API 删除才是硬删路径。

## 六、相关文档

- 方案前置审计：[scheduler-audit-2026-09-01.md](./scheduler-audit-2026-09-01.md) / [scheduler-audit-2026-09-01-v2.md](./scheduler-audit-2026-09-01-v2.md)
- 早期清理方案（未执行，部分认知过时）：[scheduler-tasks-cleanup-v2.md](./scheduler-tasks-cleanup-v2.md)
- 架构分工：agent-dh/docs/rfcs、docs/adr（ADR-002）
