#!/usr/bin/env python
"""
注册V13模拟交易定时任务

每天下午2:30执行：
1. 检查单股止损（-15%）
2. 检查是否到调仓日（5天周期）
3. 如到期，执行调仓

Usage:
    python scripts/register_v13_trading_task.py
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from infrastructure.scheduler.scheduler import SchedulerService


def register_v13_trading_task():
    """注册V13模拟交易定时任务"""

    logger.info("注册V13模拟交易定时任务")

    # 初始化scheduler
    scheduler = SchedulerService()

    # V13模拟交易任务配置
    task_config = {
        'name': 'v13-simulation-trading',
        'cron_expression': '30 14 * * 1-5',  # 工作日下午2:30（收盘前30分钟）
        'command': 'v13_daily_check',
        'params': {
            'model_path': 'live_trading/models/v13_model.json',
            'factors_path': 'live_trading/models/valid_factors.json',
            'enable_stop_loss': True,
            'enable_rebalance': True
        },
        'description': 'V13模拟交易每日检查（止损+调仓，68因子模型，IC=0.5465）'
    }

    try:
        # 检查任务是否已存在
        existing = scheduler.get_task_by_name('v13-simulation-trading')

        if existing:
            logger.info("任务已存在，更新配置...")
            scheduler.update_task(
                task_id=existing['id'],
                cron_expression=task_config['cron_expression'],
                command=task_config['command'],
                params=task_config['params'],
                description=task_config['description']
            )
            logger.info("✅ 任务更新成功")
        else:
            logger.info("创建新任务...")
            scheduler.add_task(
                name=task_config['name'],
                cron_expression=task_config['cron_expression'],
                command=task_config['command'],
                params=task_config['params'],
                description=task_config['description']
            )
            logger.info("✅ 任务创建成功")

        # 显示任务信息
        task = scheduler.get_task_by_name('v13-simulation-trading')
        logger.info("\n任务详情:")
        logger.info(f"  名称: {task['name']}")
        logger.info(f"  描述: {task['description']}")
        logger.info(f"  Cron: {task['cron_expression']}")
        logger.info(f"  命令: {task['command']}")
        logger.info(f"  参数: {task['params']}")
        logger.info(f"  状态: {'启用' if task.get('is_enabled', True) else '禁用'}")

        # 显示下次执行时间
        if task.get('next_run_at'):
            logger.info(f"  下次执行: {task['next_run_at']}")

        logger.info("\n执行逻辑:")
        logger.info("  1. 加载V13模型（68因子）")
        logger.info("  2. 检查持仓止损（单股-15%）")
        logger.info("  3. 判断是否到调仓日（5天周期）")
        logger.info("  4. 如到期，重新选股调仓（Top 8）")
        logger.info("  5. 保存交易记录到数据库")

        logger.info("\n✅ V13模拟交易定时任务注册完成")
        logger.info("   每个交易日下午2:30自动执行")

    except Exception as e:
        logger.error(f"❌ 任务注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == '__main__':
    success = register_v13_trading_task()
    sys.exit(0 if success else 1)
