# qs_ops — 运维装配包

> 抽离记录：quantsys-v2 单体 S9（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S9。

## 本包是什么

**AI 工作区 L2**：本目录=「运维」项目（调度与作业装配顶点）。上下文只要本文件。

- **定位**：业务的定时任务由 v2 自己调（ADR-004）；本包承载调度基础设施 + 作业层 + 任务域
- **调度双路径**：`infrastructure/scheduler/apscheduler_service.py`（APScheduler，读 `quant.scheduler_tasks`）+ `scheduler.py` SchedulerService（run_loop 悬置态，不再由 lifespan 启动，留作库）
- **scheduler_tasks 任务域**（12 文件）：按 command 分派（`_registry` 路由）→ data/factors/models/reports/signals/strategy/training_guard/…
- **jobs 作业层**（14 py）：kline_update/chip_distribution/financial 三件/fund_flow/index_constituents/data_quality_check/market_style/risk_check（V13）/strategy_risk_check/strategy_trading/verification/weekly_report/monitor_jobs
- **守卫件**：`trading_day_guard`（交易日守卫，全仓降级告警走它）、`data_quality_service`
- **jobs 直连件**：`strategy_trading_job`/`strategy_risk_check_job` 引 `live_trading.simulation_trader`（sim 仿真边，登记为主）

## 目录结构

```
qs_ops/
├── application/services/        scheduler_tasks*.py ×12 + trading_day_guard + data_quality_service
└── infrastructure/
    ├── scheduler/               apscheduler_service · scheduler · cron_compat · job_executor · scheduled_tasks · task_fields · signal_execution_job
    └── jobs/                    数据管道 + 风控/策略/周报作业
```

## 依赖边界（方案卡 §11.3）

- **顶点装配者**：允许 → kernel、→ 全部业务二方包（qs_market_data/qs_notification/qs_strategy/qs_trading/...）、→ live_trading（sim 仿真，新登记边 ops→live_trading）
- **禁止反向**：业务包 import ops = 违规（装配方向必须向下）
- app 壳宿主（留 L1）：`daily_jobs_bootstrap.py` / `watch_sla_job.py` / `main.py` lifespan 装配、`api/internal/scheduler_webhook.py`（Agent OS webhook 已整体退役边）
- 旧路径 shim：`application/services/`（14 alias）+ `infrastructure/{scheduler,jobs}/__init__.py`（__path__），30 天观察期

## 常见任务路径

- **加定时任务** → `application/services/scheduler_tasks_registry.py` 登记分派 → `quant.scheduler_tasks` 表插行（`POST /api/scheduler/reload` 生效）
- **改作业逻辑** → `infrastructure/jobs/<name>_job.py`；数据取数必须走 qs_market_data 的 manager 面（根 CLAUDE.md 数据访问规则）
- **调度体检** → `tools/check_scheduler_dedup.py`（撞点=0/每日 1 success/单一入口三条判据）
- **交易日降级** → `trading_day_guard.py`（连着外部探活与飞书运维群告警）
