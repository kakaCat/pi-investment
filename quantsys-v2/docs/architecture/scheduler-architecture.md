# 调度器重构架构图

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
