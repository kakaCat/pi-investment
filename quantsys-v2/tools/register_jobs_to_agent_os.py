"""Register all quantsys-v2 scheduled jobs to Agent OS Scheduler.

Run this script on deployment or when job definitions change.

Usage:
    python scripts/register_jobs_to_agent_os.py
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path

from application.services.agent_os_client import close_agent_os_client, get_agent_os_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Job Definitions ====================
# Migrated from SchedulerService and scheduler_tasks table

JOBS = [
    # K-line data update (daily, after market close)
    {
        "name": "kline_update",
        "owner": "quantsys-v2",
        "cron": "40 17 * * 1-5",  # 工作日 17:40
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "kline_update",
            "description": "Update daily K-line data for all stocks"
        }
    },

    # Index constituents (daily, after market close) — feeds stock_pool_service.get_hot_stocks
    {
        "name": "index_constituents_update",
        "owner": "quantsys-v2",
        "cron": "40 15 * * 1-5",  # 工作日 15:40（原 scheduler_task_configs 失传任务重建）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "index_constituents_update",
            "description": "Update index constituents (HS300/STAR50/ChiNext) for hot stock pool"
        }
    },

    # Chip distribution (daily, after K-line update)
    {
        "name": "chip_distribution_update",
        "owner": "quantsys-v2",
        "cron": "30 10 * * 1-5",  # 工作日 10:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 900,
        "retry_count": 1,
        "metadata": {
            "job_type": "chip_distribution_update",
            "description": "Calculate chip distribution for all stocks"
        }
    },

    # Pool refresh (daily, early morning)
    {
        "name": "pool_refresh_daily",
        "owner": "quantsys-v2",
        "cron": "0 2 * * *",  # 每日 02:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "pool_refresh",
            "description": "Refresh dynamic stock pools"
        }
    },

    # M1 Market Perception - daily snapshot (RFC 007)
    {
        "name": "market_perception_daily",
        "owner": "quantsys-v2",
        "cron": "0 30 15 * * 1-5",  # 工作日 15:30（盘后）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "market_perception_daily",
            "description": "M1 market perception daily snapshot: regime + sentiment + themes"
        }
    },

    # Signal generation - buy (before market opens)
    {
        "name": "signal_generate_buy",
        "owner": "quantsys-v2",
        "cron": "0 9 * * 1-5",  # 工作日 09:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "signal_generate",
            "scan_type": "buy",
            "strategy_ids": [179, 178, 163, 193],
            "description": "Scan buy signals before market opens"
        }
    },

    # Signal generation - sell (after market close)
    {
        "name": "signal_generate_sell",
        "owner": "quantsys-v2",
        "cron": "0 30 15 * * 1-5",  # 工作日 15:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "signal_generate",
            "scan_type": "sell",
            "description": "Scan sell signals after market closes"
        }
    },

    # Signal execution (daily, after signal generation)
    {
        "name": "signal_execution_daily",
        "owner": "quantsys-v2",
        "cron": "30 7 * * 1-5",  # 工作日 07:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "signal_execution_daily",
            "description": "Execute daily signal execution pipeline"
        }
    },

    # Factor computation (daily, before market opens)
    {
        "name": "factor_compute_daily",
        "owner": "quantsys-v2",
        "cron": "0 8 * * 1-5",  # 工作日 08:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 900,
        "retry_count": 1,
        "metadata": {
            "job_type": "factor_compute",
            "market": "A",
            "description": "Compute technical factors for all stocks"
        }
    },

    # Data quality check (daily, afternoon)
    {
        "name": "data_quality_check_daily",
        "owner": "quantsys-v2",
        "cron": "0 16 * * *",  # 每日 16:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "data_quality_check",
            "days": 30,
            "auto_backfill": True,
            "description": "Check data quality and auto-backfill"
        }
    },

    # Strategy validation (daily, midday)
    {
        "name": "strategy_validate_daily",
        "owner": "quantsys-v2",
        "cron": "0 13 * * 1-5",  # 工作日 13:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "strategy_validate_daily",
            "description": "Validate strategy parameters and performance"
        }
    },

    # V13 daily check (before market close)
    # DEPRECATED (strategy-refactor Part 4.2): superseded by the unified
    # `strategy_execute_all` job below, which runs every active strategy via
    # application.strategies.StrategyExecutor.execute_all(). Kept (name/cron
    # unchanged) for rollback; disabled to avoid double execution at 14:30.
    {
        "name": "v13_daily_check",
        "owner": "quantsys-v2",
        "cron": "30 14 * * 1-5",  # 工作日 14:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": False,  # DEPRECATED: replaced by strategy_execute_all
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "v13_daily_check",
            "enable_stop_loss": True,
            "enable_rebalance": True,
            "deprecated": True,
            "replaced_by": "strategy_execute_all",
            "description": "[DEPRECATED] V13 simulation trading daily check (use strategy_execute_all)"
        }
    },

    # V13 risk check (after market close)
    {
        "name": "v13_risk_check",
        "owner": "quantsys-v2",
        "cron": "0 16 * * 1-5",  # 工作日 16:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "v13_risk_check",
            "description": "V13 post-market risk check"
        }
    },

    # V13 verification (after risk check)
    {
        "name": "v13_verification",
        "owner": "quantsys-v2",
        "cron": "30 16 * * 1-5",  # 工作日 16:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "v13_verification",
            "description": "V13 trading verification"
        }
    },

    # Unified strategy execution (before market close) — strategy-refactor Part 4.2
    # Single task replacing the separate v13_daily_check / v14_daily_check jobs:
    # the webhook handler builds StrategyExecutor(trader, position_repo, engine)
    # and calls execute_all(), which runs every active strategy (V13 + V14) for
    # today and captures per-strategy failures without blocking the others.
    {
        "name": "strategy_execute_all",
        "owner": "quantsys-v2",
        "cron": "30 14 * * 1-5",  # 工作日 14:30（沿用 v13_daily_check 时段）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "strategy_execute_all",
            "description": "Unified daily execution of all active strategies via StrategyExecutor.execute_all()"
        }
    },

    # 盘中风控检查（交易时段每30分钟，10:00-14:30）— strategy-refactor Part 5.2
    # 7 个 cron 任务共用一个 job_type：IntradayRiskService 检查全部持仓的
    # 固定止损/移动止损规则，触发即卖出落库并飞书告警。
    # retry_count=0：失败后由下一个 30 分钟任务接管，避免止损单重复执行。
    {
        "name": "intraday_risk_1000",
        "owner": "quantsys-v2",
        "cron": "0 10 * * 1-5",  # 工作日 10:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1030",
        "owner": "quantsys-v2",
        "cron": "30 10 * * 1-5",  # 工作日 10:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1100",
        "owner": "quantsys-v2",
        "cron": "0 11 * * 1-5",  # 工作日 11:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1300",
        "owner": "quantsys-v2",
        "cron": "0 13 * * 1-5",  # 工作日 13:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1330",
        "owner": "quantsys-v2",
        "cron": "30 13 * * 1-5",  # 工作日 13:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1400",
        "owner": "quantsys-v2",
        "cron": "0 14 * * 1-5",  # 工作日 14:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },
    {
        "name": "intraday_risk_1430",
        "owner": "quantsys-v2",
        "cron": "30 14 * * 1-5",  # 工作日 14:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "intraday_risk_check",
            "description": "Intraday risk check: stop-loss / trailing-stop on all positions"
        }
    },

    # Financial statement update (weekly, Saturday)
    {
        "name": "financial_statement_update",
        "owner": "quantsys-v2",
        "cron": "0 20 * * 6",  # 每周六 20:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 1800,
        "retry_count": 1,
        "metadata": {
            "job_type": "financial_statement_update",
            "description": "Update quarterly financial statements"
        }
    },

    # Financial data update (weekly, Saturday)
    {
        "name": "financial_data_update",
        "owner": "quantsys-v2",
        "cron": "30 18 * * 6",  # 每周六 18:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 1800,
        "retry_count": 1,
        "metadata": {
            "job_type": "financial_data_update",
            "market": "A",
            "description": "Update fundamental financial data"
        }
    },

    # V13 weekly report (weekly, Saturday)
    {
        "name": "v13_weekly_report",
        "owner": "quantsys-v2",
        "cron": "0 10 * * 6",  # 每周六 10:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "v13_weekly_report",
            "description": "Generate V13 weekly performance report"
        }
    },

    # Weekly report generation (weekly, Friday)
    {
        "name": "report_weekly",
        "owner": "quantsys-v2",
        "cron": "0 10 * * 5",  # 每周五 10:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "report_daily",
            "description": "Generate weekly summary report"
        }
    },

    # Market style update (daily, after market close)
    {
        "name": "market_style_update",
        "owner": "quantsys-v2",
        "cron": "0 30 15 * * 1-5",  # 工作日 15:30
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 300,
        "retry_count": 1,
        "metadata": {
            "job_type": "market_style_update",
            "description": "Detect and save market style"
        }
    },

    # Chan theory scan (daily, morning)
    {
        "name": "chan_scan_daily",
        "owner": "quantsys-v2",
        "cron": "10 10 * * 1-5",  # 工作日 10:10
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 600,
        "retry_count": 1,
        "metadata": {
            "job_type": "chan_scan",
            "description": "Chan theory pattern analysis"
        }
    },

    # Chan knowledge distillation (weekly, Sunday)
    {
        "name": "chan_knowledge_distill_weekly",
        "owner": "quantsys-v2",
        "cron": "0 12 * * 0",  # 每周日 12:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 1800,
        "retry_count": 1,
        "metadata": {
            "job_type": "chan_knowledge_distill",
            "description": "Distill Chan theory knowledge"
        }
    },

    # Strategy discovery (weekly, Sunday)
    {
        "name": "strategy_discover_weekly",
        "owner": "quantsys-v2",
        "cron": "0 14 * * 0",  # 每周日 14:00
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",  # Agent OS ensures v2 is running before triggering
        "enabled": True,
        "timeout": 3600,
        "retry_count": 1,
        "metadata": {
            "job_type": "strategy_discover_weekly",
            "description": "Discover new trading strategies"
        }
    },

    # v2 调度健康检查 (daily, after market close) — 2026-09-01 investor w-8366e526
    # ADR-002 后 v2 定时任务由 Agent OS 调度（webhook 模式），Agent OS 单点故障会
    # 静默停摆全部 v2 任务。本任务每日检查僵尸/漏执行/高失败率任务，异常返回 degraded。
    {
        "name": "v2_health_check",
        "owner": "quantsys-v2",
        "cron": "0 45 16 * * 1-5",  # 工作日 16:45（盘后）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 120,
        "retry_count": 0,
        "metadata": {
            "job_type": "v2_health_check",
            "description": "Daily scheduler health check (zombie/missed/failure tasks)"
        }
    },

    # 信号胜率回填 (daily, after market close) — 2026-09-01 investor w-8366e526
    # ADR-002 后 v2 定时任务由 Agent OS 调度（webhook 模式）。原 signal-perf-backfill-daily
    # 在 DSH 原生调度迁移中被禁用为 /bin/true 空壳（审计 §7.2 #3：回填职责悬空——旧任务
    # 07d34e66 描述"已由 post-market-routine-live 覆盖"，但后者仅投递 followup 给窗口、
    # 不保证执行）。本任务以 webhook 直调 v2 SignalTrackingService.update_performance，
    # 不依赖 agent 响应，保证胜率统计与验证门样本持续更新。
    {
        "name": "signal_perf_backfill_daily",
        "owner": "quantsys-v2",
        "cron": "0 45 15 * * 1-5",  # 工作日 15:45（盘后）
        "webhook_url": "http://127.0.0.1:5001/internal/scheduler/webhook",
        "service_name": "quantsys-v2",
        "enabled": True,
        "timeout": 1800,
        "retry_count": 1,
        "metadata": {
            "job_type": "signal_perf_backfill_daily",
            "description": "Backfill signal 5/10/20d performance (signal_track update, after market close)"
        }
    },

]


# ==================== Registration Logic ====================


async def register_all_jobs():
    """Register all jobs to Agent OS Scheduler.

    This function is idempotent - it skips jobs that already exist.
    """
    client = get_agent_os_client()

    try:
        # Get existing jobs
        existing_jobs = await client.list_jobs(owner="quantsys-v2")
        existing_names = {job["name"] for job in existing_jobs}

        logger.info(f"Found {len(existing_jobs)} existing jobs")

        success_count = 0
        skip_count = 0
        error_count = 0

        for job in JOBS:
            try:
                if job["name"] in existing_names:
                    # Backfill service binding on existing jobs that lack it,
                    # so Agent OS auto-starts the bound service on trigger.
                    existing_job = next(j for j in existing_jobs if j["name"] == job["name"])
                    desired_service = job.get("service_name", "")
                    if desired_service and not existing_job.get("service_name"):
                        await client.update_job(existing_job["id"], {"service_name": desired_service})
                        logger.info(f"Job '{job['name']}' bound to service '{desired_service}'")
                    else:
                        logger.info(f"Job '{job['name']}' already exists, skipping")
                    skip_count += 1
                    continue

                # Prepare job payload for Agent OS API
                job_payload = {
                    "name": job["name"],
                    "owner": job["owner"],
                    "cron": job["cron"],
                    "webhook_url": job["webhook_url"],
                    "service_name": job.get("service_name", ""),
                    "enabled": job["enabled"],
                    "timeout": job.get("timeout", 3600),
                    "retry_count": job.get("retry_count", 0),
                    "payload": job["metadata"]
                }

                result = await client.register_job(job_payload)
                logger.info(
                    f"✅ Registered '{job['name']}' (id={result.get('id')}, "
                    f"cron={job['cron']})"
                )
                success_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to register '{job['name']}': {e}")
                error_count += 1

        logger.info("=" * 60)
        logger.info(f"Registration complete:")
        logger.info(f"  - Success: {success_count}")
        logger.info(f"  - Skipped: {skip_count}")
        logger.info(f"  - Errors: {error_count}")
        logger.info(f"  - Total: {len(JOBS)}")
        logger.info("=" * 60)

        return success_count > 0 or skip_count > 0

    finally:
        # Use the module-level cleanup so the global singleton is reset —
        # a bare client.close() would leave get_agent_os_client()
        # returning a dead client to later callers (e.g. job result
        # reporting from scheduler_webhook).
        await close_agent_os_client()


# ==================== CLI Entry Point ====================


if __name__ == "__main__":
    try:
        success = asyncio.run(register_all_jobs())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        sys.exit(1)
