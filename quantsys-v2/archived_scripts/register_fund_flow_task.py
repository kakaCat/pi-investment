#!/usr/bin/env python3
"""
注册资金流更新定时任务到调度器

执行命令：
    python scripts/register_fund_flow_task.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent

from infrastructure.scheduler.scheduler import SchedulerService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_task():
    """注册资金流更新任务"""
    scheduler = SchedulerService()

    try:
        # 检查任务是否已存在
        existing_tasks = scheduler.list_tasks()
        for task in existing_tasks:
            if task['name'] == 'fund_flow_update':
                logger.info(f"任务已存在 (id={task['id']})，跳过注册")
                return

        # 注册新任务
        task_id = scheduler.add_task(
            name='fund_flow_update',
            cron_expression='30 21 * * *',  # 每天 21:30
            command='update_fund_flow',      # 对应 scheduled_tasks.py 中的函数
            description='更新主要指数成分股的资金流数据缓存',
            params={}
        )

        logger.info(f"✅ 资金流更新任务注册成功 (id={task_id})")
        logger.info(f"   执行时间: 每天 21:30")
        logger.info(f"   命令: update_fund_flow")

    except Exception as e:
        logger.error(f"❌ 任务注册失败: {e}")
        raise
    finally:
        scheduler.close()


if __name__ == '__main__':
    register_task()
