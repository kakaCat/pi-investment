#!/usr/bin/env python3
"""
Register scheduled tasks for the data pipeline.

This script registers two scheduled tasks:
1. daily_data_pipeline - Daily incremental update at 16:30 (Mon-Fri)
2. weekly_full_rebuild - Full rebuild every Sunday at 2:00 AM

Usage:
    python scripts/register_pipeline_tasks.py
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


def register_tasks():
    """Register scheduled tasks with the scheduler."""
    scheduler = SchedulerService()

    try:
        # Task 1: Daily data pipeline (Mon-Fri at 16:30)
        # Cron: 30 16 * * 1-5 (minute=30, hour=16, day_of_week=1-5)
        logger.info("Registering daily_data_pipeline task...")

        # Check if task already exists
        existing_daily = scheduler.get_task_by_name("daily_data_pipeline")
        if existing_daily:
            logger.info(f"Task 'daily_data_pipeline' already exists (id={existing_daily['id']})")
            logger.info("Updating task to ensure correct configuration...")
            scheduler.update_task(
                existing_daily['id'],
                cron_expression="30 16 * * 1-5",
                command="data_pipeline_daily",
                description="Daily incremental update at 16:30 (after market close)"
            )
        else:
            task_id = scheduler.add_task(
                name="daily_data_pipeline",
                cron_expression="30 16 * * 1-5",
                command="data_pipeline_daily",
                params={},
                description="Daily incremental update at 16:30 (after market close)"
            )
            logger.info(f"Registered daily_data_pipeline task (id={task_id})")

        # Task 2: Weekly full rebuild (Sunday at 2:00 AM)
        # Cron: 0 2 * * 0 (minute=0, hour=2, day_of_week=0=Sunday)
        logger.info("Registering weekly_full_rebuild task...")

        existing_weekly = scheduler.get_task_by_name("weekly_full_rebuild")
        if existing_weekly:
            logger.info(f"Task 'weekly_full_rebuild' already exists (id={existing_weekly['id']})")
            logger.info("Updating task to ensure correct configuration...")
            scheduler.update_task(
                existing_weekly['id'],
                cron_expression="0 2 * * 0",
                command="data_pipeline_weekly",
                description="Full rebuild every Sunday at 2:00 AM"
            )
        else:
            task_id = scheduler.add_task(
                name="weekly_full_rebuild",
                cron_expression="0 2 * * 0",
                command="data_pipeline_weekly",
                params={},
                description="Full rebuild every Sunday at 2:00 AM"
            )
            logger.info(f"Registered weekly_full_rebuild task (id={task_id})")

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
        logger.error(f"Failed to register tasks: {e}", exc_info=True)
        sys.exit(1)
    finally:
        scheduler.close()


if __name__ == "__main__":
    register_tasks()
