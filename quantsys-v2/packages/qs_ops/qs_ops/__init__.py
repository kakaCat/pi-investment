"""qs_ops — 运维装配包（调度 Infrastructure / 作业 / 任务域 / 守卫 / 数据质量）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S9）。
包内布局沿用原领域结构：
- qs_ops.application.services.scheduler_tasks*  调度任务域（12 文件：registry/common/data/factors/models/reports/runtime/signals/strategy/training_guard）
- qs_ops.application.services.trading_day_guard 交易日守卫
- qs_ops.application.services.data_quality_service 数据质量
- qs_ops.infrastructure.scheduler               调度器（APSchedulerService/SchedulerService/job_executor/cron_compat/...）
- qs_ops.infrastructure.jobs                    后台作业（kline/financial/fund_flow/risk_check/weekly_report/...）

装配宿主：FastAPI lifespan 经 app 壳 daily_jobs_bootstrap / APSchedulerService（留在 app 壳）。
ops 是「顶点装配者」：允许依赖所有业务包（qs_market_data/qs_strategy/qs_trading/qs_notification...），
业务包不得反向依赖本包。
"""

__version__ = "0.1.0"
