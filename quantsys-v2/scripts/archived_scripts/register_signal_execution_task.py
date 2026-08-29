#!/usr/bin/env python3
"""
Register scheduled task for daily signal execution.

This script registers the signal execution task:
- daily_signal_execution - Daily signal execution at 15:30 (Mon-Fri)

Usage:
    python scripts/register_signal_execution_task.py
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent

from infrastructure.scheduler.scheduler import SchedulerService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def register_task():
    """Register signal execution scheduled task with the scheduler."""
    scheduler = SchedulerService()

    try:
        # Task: Daily signal execution (Mon-Fri at 15:30)
        # Cron: 30 15 * * 1-5 (minute=30, hour=15, day_of_week=1-5)
        logger.info("Registering daily_signal_execution task...")

        # Check if task already exists
        existing_task = scheduler.get_task_by_name("daily_signal_execution")
        if existing_task:
            logger.info(f"Task 'daily_signal_execution' already exists (id={existing_task['id']})")
            logger.info("Updating task to ensure correct configuration...")
            scheduler.update_task(
                existing_task['id'],
                cron_expression="30 15 * * 1-5",
                command="signal_execution_daily",
                description="每天15:30自动运行策略、生成信号、风控检查、创建订单"
            )
        else:
            task_id = scheduler.add_task(
                name="daily_signal_execution",
                cron_expression="30 15 * * 1-5",
                command="signal_execution_daily",
                params={},
                description="每天15:30自动运行策略、生成信号、风控检查、创建订单"
            )
            logger.info(f"Registered daily_signal_execution task (id={task_id})")

        # List all tasks
        logger.info("\nAll registered tasks:")
        tasks = scheduler.list_tasks()
        for task in tasks:
            status = "enabled" if task['is_enabled'] else "disabled"
            logger.info(
                f"  - {task['name']} ({status}): {task['cron_expression']} "
                f"-> {task['command']}"
            )

        logger.info("\nTask registration completed successfully!")
        logger.info("To start the scheduler, run: python -m runtime.scheduler.scheduler")

    except Exception as e:
        logger.error(f"Failed to register task: {e}", exc_info=True)
        sys.exit(1)
    finally:
        scheduler.close()


if __name__ == "__main__":
    register_task()
