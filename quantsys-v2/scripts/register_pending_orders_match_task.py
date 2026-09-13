# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

#!/usr/bin/env python3

# Extracted Constants


# Extracted Constants

CONST_60 = 60



CONST_60 = 60



"""
注册挂单撮合任务到调度器 (直接使用数据库)

执行时机: 每个交易日 9:31 (开盘后1分钟)
功能: 撮合所有 pending 状态的挂单
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.persistence.orm.session import get_session
from infrastructure.persistence.orm.models.scheduler import SchedulerTask
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


def register_pending_orders_match_task():
    """注册挂单撮合任务"""

    with get_session() as session:
        # 检查是否已存在
        existing = session.query(SchedulerTask).filter(
            SchedulerTask.task_name == "pending_orders_match"
        ).first()

        if existing:
            logger.info("任务已存在，更新配置")
            existing.enabled = True
            existing.cron_expr = "31 9 * * 1-5"
            existing.command = "pending_orders_match"
            existing.description = "挂单撮合 - 开盘后执行所有 pending 挂单"
            existing.params = {}
            existing.updated_at = datetime.now()
            session.commit()
            logger.info("✅ 挂单撮合任务已更新")
        else:
            logger.info("创建新任务")
            task = SchedulerTask(
                task_name="pending_orders_match",
                command="pending_orders_match",
                cron_expr="31 9 * * 1-5",
                enabled=True,
                description="挂单撮合 - 开盘后执行所有 pending 挂单",
                params={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(task)
            session.commit()
            logger.info("✅ 挂单撮合任务已创建")

        # 验证任务
        task = session.query(SchedulerTask).filter(
            SchedulerTask.task_name == "pending_orders_match"
        ).first()

        if task:
            logger.info(
                "任务配置",
                task_name=task.task_name,
                cron_expr=task.cron_expr,
                enabled=task.enabled,
                command=task.command,
            )
            return True
        logger.error("❌ 任务创建/更新失败")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("注册挂单撮合任务到调度器")
    print("=" * 60)

    try:
        success = register_pending_orders_match_task()
        if success:
            print("\n✅ 挂单撮合任务注册成功")
            print("\n任务详情:")
            print("  - 任务名称: pending_orders_match")
            print("  - 执行时间: 每周一到周五 9:31")
            print("  - 功能: 撮合所有 pending 状态的挂单")
            print("\n下一步:")
            print("  1. 重启 quantsys-v2 服务 (launchctl kickstart -k gui/501/com.pi-investment.v2-api)")
            print("  2. 检查日志确认任务已加载")
            print("  3. 查看调度器状态: curl http://127.0.0.1:5001/api/scheduler/tasks")
        else:
            print("\n❌ 任务注册失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"注册失败: {e}", exc_info=True)
        print(f"\n❌ 注册失败: {e}")
        sys.exit(1)