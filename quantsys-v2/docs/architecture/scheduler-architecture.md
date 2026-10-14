# 调度器重构架构图

> ## ⚠️ 先读这一节：现状（2026-10-02 定案 · `REQ-261001145152-3982` 审查后）
>
> **下面正文描述的是历史设计（Agent OS webhook 调度）——它已被 ADR-004 取代，
> 不要照着它改动现网。** 现网运行态如下。
>
> ### 归属已定案（[ADR-004](../adr/004-scheduling-ownership.md)）
>
> **业务的定时任务由 v2 自己调度；agent-os 只调度 agent 自身任务**（`AGENT_OS_ENABLED=false`）。
> 因此本文第三、五节描述的「Agent OS Scheduler → webhook → 本地执行」链路**当前不生效**。
>
> ### 现网只有两条路径（互为补充，不要新增第三条）
>
> | | 承载 | 读什么 | 跑什么 |
> |---|---|---|---|
> | ① | `APSchedulerService`（`infrastructure/scheduler/apscheduler_service.py`） | `quant.scheduler_tasks` 表的 cron | 非核心数据类任务（实时信号监控 / 盘前扫描 / 缠论 / 策略验证 / 周报 …） |
> | ② | DailyJobs 宿主线程（`adapters/inbound/fastapi_app/daily_jobs_bootstrap.py`） | 代码内注册表 | 9 个核心数据任务（带幂等 / 补跑 / 失败告警 + `quant.inprocess_job_runs` 留痕） |
>
> ### ② DailyJobs 有任务级**交易日门**（2026-10-05 · REQ-261005203907-2b8c）
>
> 宿主排班只认工作日，不认识法定节假日——2026-10-05（国庆休市）实测 `pool_daily_refresh`
> 空跑 22.1 秒还发了 2 条飞书、`evening_pipeline` 的因子段对着冻结快照全市场重算了 50+ 分钟。
> 现新增 `JobDef.trading_days_only` 标志 + `daily_jobs/gate.py`（判据唯一：
> `skip = (not is_trading_day) and (not degraded)`，**fail-open**）；休市日整段跳过的有
> `pool_daily_refresh` / `chip_distribution` / `evolution_fitness`，`evening_pipeline` 只跳因子段
> （K 线段是休市日唯一的缺口修复路径）。跳过写 `status='skipped'`（列是 text ⇒ 零 DDL）、
> **不发通知**；生效需重启宿主。口径与回滚详见
> [trading-day-freshness.md §调度侧](trading-day-freshness.md#调度侧休市日不再开火2026-10-05--req-261005203907-2b8c)。
>
> ### 2026-10-02 的收敛与实测数字（都可复跑）
>
> - 删掉了第四条路径 `unified_scheduler.py`（YAML 驱动、**空转**）及其配置、路由与专属 e2e；
> - `infrastructure/scheduler/scheduler.py` 的 `run_loop` **不再被启动**（仍被 22 个文件引用，
>   去留须**单独开卡**评估 —— 删除会牵动这些引用方）；
> - 启用任务去重 **26 → 16**、cron 撞点组 **4 → 0**、`apscheduler_jobs` 僵尸条目 **27 → 16**；
>   随后"启用集合体检"又**停用 5 条全仓零 handler 的命令**（一触发必失败）→ 启用集合 **16 → 11**，
>   11 条命令**全部有效**。⚠️ 停用 DB 行**不足以生效**：任务已进 APScheduler jobstore，
>   须再调 `POST /api/scheduler/reload`（实测停用后仍被触发过一次）。
>
> ### 本次审查修掉的两个真缺陷（都与调度直接相关）
>
> 1. **`APSchedulerService` 曾一条任务都加载不了** ✗：ORM 比 `quant.scheduler_tasks` 多
>    `domain` / `task_type` / `misfire_grace_time_seconds` 三列 → 任何查询直接报 `UndefinedColumn`。
>    已由迁移 `infrastructure/persistence/migrations/20261002_scheduler_tasks_missing_columns.py` 修好。
> 2. **任务终态记账的"假失败"** ✗：daily jobs 共用宿主线程会话，更早某条 SQL 失败未回滚即**毒化会话**
>    → 终态 `UPDATE` 报 `InFailedSqlTransaction` → 任务**干成了却记 failed**，
>    并让"每 job 每日仅 1 条 success"的判据**永远过不了**。已修两处：
>    `JobRunRepository.mark_done` **记账前先回滚**；`event_calendar_repository` 的吞异常处补
>    `_safe_rollback()`（完整因果链见需求档案的审计报告 §W）。
>
> ### 运维与自检
>
> - **守护**：`launchd` 的 `com.pi-investment.v2-api`（`KeepAlive` + `RunAtLoad`，崩了自动拉起）；
> - **总开关**：`DISABLE_APSCHEDULER` / `DISABLE_DAILY_JOBS` / `DISABLE_WATCH_ENGINE`（默认全 false）；
> - **一条命令自检**：`python tools/check_scheduler_dedup.py`（撞点 = 0 / 每 job 每日仅 1 条 success /
>   `adapters/` 单一调度入口），退出码 0 = 全过、2 = 有判据未过、3 = 检查器自身出错；
> - ⚠️ 其中「**连续 3 个交易日**」是**时间型**判据，必须等真实交易日累积
>   （2026-10-02 起国庆休市，判定窗口约 **10-09 之后**）—— 未达之前**不得**把它标成通过。

---

## 一、新框架架构（3 层分离）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scheduler Layer（调度层）                      │
│                                                                 │
│   infrastructure/scheduler/scheduler.py                         │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │  SchedulerService                                        │  │
│   │  • APScheduler 定时触发                                   │  │
│   │  • DB 持久化（quant.scheduler_tasks / scheduler_runs）    │  │
│   │  • cron 解析 + misfire 宽限                               │  │
│   │  • run_due_tasks() 每分钟轮询                             │  │
│   └──────────────────────┬────────────────────────────────────┘  │
│                          │                                       │
│                          ▼                                       │
│   _execute_command(command, params)                              │
│                          │                                       │
│                          ▼                                       │
│              job_registry.execute(command, params)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Job Layer（任务层）                            │
│                                                                 │
│   application/jobs/                                             │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │  job_protocol.py   — Job ABC + JobResult dataclass       │  │
│   │  job_registry.py   — JobRegistry 单例 (register/get/exec)│  │
│   │  registry_setup.py — register_all_jobs() 注册 29 个任务   │  │
│   └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│   │  Data    │ │  Signal  │ │ Trading  │ │ Analysis │          │
│   │  Jobs(6) │ │  Jobs(4) │ │ Jobs(6)  │ │ Jobs(8)  │          │
│   ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤          │
│   │kline_upd │ │signal_gen│ │order_exec│ │backtest  │          │
│   │data_qual │ │signal_mon│ │risk_check│ │factor_cmp│          │
│   │pipeline_d│ │fund_flow │ │portfolio │ │strategy_d│          │
│   │pipeline_w│ │exec_daily│ │stop_loss │ │evolution │          │
│   │data_upd  │ │          │ │position  │ │missed_opp│          │
│   │chip_dist │ │          │ │rotation  │ │chan_scan  │          │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│   ┌──────────┐ ┌──────────┐                                    │
│   │ Report   │ │ Monitor  │                                    │
│   │ Jobs(3)  │ │ Jobs(2)  │                                    │
│   ├──────────┤ ├──────────┤                                    │
│   │daily_rpt │ │health_mon│                                    │
│   │weekly_rpt│ │zombie reap│                                   │
│   │perf_rpt  │ │          │                                    │
│   └──────────┘ └──────────┘                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Domain Layer（领域层）                        │
│                                                                 │
│   domain/ + adapters/ + infrastructure/jobs/                    │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │  实际业务逻辑：数据拉取、信号生成、因子计算、回测等         │  │
│   │  Repository / Service / Stage                             │  │
│   └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│   兼容层：application/services/task_handlers.py                  │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │  10 个 handler 函数 + _TASK_HANDLERS 注册表               │  │
│   │  仅供测试使用，新代码应使用 Job 类                         │  │
│   └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Layer（编排层）                  │
│                                                                 │
│   application/services/daily_orchestrator.py                    │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │  DailyOrchestrator — 状态机驱动每日流程                    │  │
│   │  IDLE → PRE_MARKET → MARKET_OPEN → INTRADAY →            │  │
│   │  MARKET_CLOSE → POST_MARKET → REVIEW → IDLE              │  │
│   │                                                           │  │
│   │  _run_job(name) → job_registry.execute(name)              │  │
│   └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 二、单次调度执行流程

```
APScheduler (每分钟触发)
       │
       ▼
SchedulerService.run_due_tasks()
       │
       ├─ 1. SELECT * FROM quant.scheduler_tasks
       │     WHERE is_enabled = true AND next_run_time <= NOW()
       │
       ├─ 2. 检查 misfire 宽限（避免僵尸任务积压）
       │
       ├─ 3. 写入 scheduler_runs (status='running')
       │
       └─ 4. _execute_command(command, params)
                │
                ▼
        job_registry.execute(command, params)
                │
                ├─ 5. 查找 Job 实例
                │     job = self._jobs.get(name)
                │
                ├─ 6. 执行 Job
                │     result = await job.execute(params)
                │     │
                │     ▼
                │   Job 内部调用 Domain/Adapter 层
                │   （数据拉取 / 信号生成 / 因子计算 / ...）
                │     │
                │     ▼
                │   返回 JobResult(success, action, message, details)
                │
                ├─ 7. 转换为 dict 返回
                │     {action, status, message, error, details}
                │
                └─ 8. 更新 scheduler_runs (status, result, duration_ms)
```

## 三、Webhook 触发流程（Agent OS → 本地）

```
Agent OS Scheduler
       │
       │ POST /api/scheduler/webhook
       │ {job_id, job_name, trigger_time, metadata:{job_type, run_id}}
       ▼
scheduler_webhook.py
       │
       ├─ 1. 验证 job_type 存在
       │     registry.get(job_type)
       │
       ├─ 2. 返回 "accepted"（立即响应，不阻塞）
       │
       └─ 3. BackgroundTask: execute_job(job_type, payload)
                │
                ├─ 4. job_registry.execute(job_type, metadata)
                │
                ├─ 5. 写入本地 DB（审计日志）
                │
                └─ 6. 报告结果回 Agent OS
                       agent_os_client.report_job_result(run_id, result)
```

## 四、Orchestrator 阶段流程

```
每日投资循环（DailyOrchestrator.tick()）

  ┌─────────────────────────────────────────────────┐
  │  08:30 PRE_MARKET                               │
  │  ├─ _run_job("data_update")       → 拉取最新K线 │
  │  ├─ _run_job("market_style_update") → 风格识别  │
  │  └─ _run_job("signal_generate")   → 生成信号    │
  ├─────────────────────────────────────────────────┤
  │  09:25 MARKET_OPEN                              │
  │  └─ 检查开盘条件                                │
  ├─────────────────────────────────────────────────┤
  │  09:35-15:00 INTRADAY                           │
  │  └─ 监控市场动态                                │
  ├─────────────────────────────────────────────────┤
  │  15:00 MARKET_CLOSE                             │
  │  ├─ _run_job("data_update")       → 盘后数据    │
  │  └─ 结算虚拟账户                                │
  ├─────────────────────────────────────────────────┤
  │  15:30 POST_MARKET                              │
  │  ├─ _run_job("factor_compute")    → 因子重算    │
  │  ├─ _run_job("daily_equity_snapshot") → 净值快照│
  │  └─ _run_job("chan_scan")         → 缠论扫描    │
  ├─────────────────────────────────────────────────┤
  │  16:30 REVIEW                                   │
  │  ├─ _run_job("report_daily")      → 日报生成    │
  │  └─ _run_job("decision_score_daily") → 决策打分  │
  └─────────────────────────────────────────────────┘
```

## 五、关键设计对比

| 维度 | 旧架构（scheduler_tasks.py） | 新架构（Job + Registry） |
|------|------|------|
| 任务定义 | 单文件 1640 行 | 6 个模块，每个 Job 独立类 |
| 分发机制 | `_TASK_HANDLERS` dict | `JobRegistry` 单例 + async execute |
| 结果格式 | 各 handler 返回不同 dict | 统一 `JobResult` dataclass |
| 注册方式 | 手动维护 dict | `register_all_jobs()` 启动时自动 |
| 调度器耦合 | SchedulerService 内含业务逻辑 | SchedulerService 纯调度，零业务逻辑 |
| 编排器 | 直接调用 handler | `job_registry.execute(name)` |
| Webhook | 接收函数 + 执行 | 查找 Job 类 + await execute |
| 测试 | 集成测试依赖 DB | 可 mock JobRegistry |
