"""
初始化财务数据定时更新任务

用途：
1. 在调度器中注册财务数据更新任务
2. 设置每周日凌晨2:30执行（在周全量重建之后）

执行方式：
python scripts/setup_financial_update_task.py
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent

import logging
from infrastructure.scheduler.scheduler import SchedulerService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_financial_update_task():
    """注册财务数据更新任务"""

    scheduler = SchedulerService()

    try:
        # 检查任务是否已存在
        existing_task = scheduler.get_task_by_name("weekly_financial_update")

        if existing_task:
            logger.info(f"Task 'weekly_financial_update' already exists (id={existing_task['id']})")

            # 更新任务配置
            scheduler.update_task(
                task_id=existing_task['id'],
                description="每周财务数据更新 - 检查并更新最新季报/年报",
                cron_expression="30 2 * * 0",  # 每周日 2:30
                command="financial_data_update",
                params={
                    "force_update": False,
                    "max_workers": 8
                },
                is_enabled=True
            )
            logger.info("Task 'weekly_financial_update' updated successfully")

        else:
            # 创建新任务
            task_id = scheduler.add_task(
                name="weekly_financial_update",
                description="每周财务数据更新 - 检查并更新最新季报/年报",
                cron_expression="30 2 * * 0",  # 每周日 2:30（在数据管道全量重建之后）
                command="financial_data_update",
                params={
                    "force_update": False,  # 增量更新
                    "max_workers": 8
                }
            )
            logger.info(f"Task 'weekly_financial_update' created successfully (id={task_id})")

        # 显示任务信息
        task = scheduler.get_task_by_name("weekly_financial_update")
        logger.info(f"Task details:")
        logger.info(f"  - ID: {task['id']}")
        logger.info(f"  - Name: {task['name']}")
        logger.info(f"  - Cron: {task['cron_expression']}")
        logger.info(f"  - Command: {task['command']}")
        logger.info(f"  - Enabled: {task['is_enabled']}")
        logger.info(f"  - Next run: {task['next_run_at']}")

        return True

    except Exception as e:
        logger.error(f"Failed to setup financial update task: {e}", exc_info=True)
        return False

    finally:
        scheduler.close()


if __name__ == "__main__":
    logger.info("Setting up financial data update task...")

    success = setup_financial_update_task()

    if success:
        logger.info("✅ Financial data update task setup completed")
        sys.exit(0)
    else:
        logger.error("❌ Financial data update task setup failed")
        sys.exit(1)
