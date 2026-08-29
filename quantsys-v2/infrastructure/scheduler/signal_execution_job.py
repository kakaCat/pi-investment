"""
每日信号执行任务
运行策略 → 生成信号 → 风控检查 → 创建订单

被调度器调用: infrastructure.scheduler.signal_execution_job
"""
import structlog
logger = structlog.get_logger(__name__)

import logging
from datetime import date, datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


def execute_daily_signals_job(task_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """调度器调用的入口函数（带_job后缀）"""
    if task_context is None:
        task_context = {}
    return execute_daily_signals(task_context)

def execute_daily_signals(task_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    每日信号执行任务入口

    Args:
        task_context: 调度器传递的上下文 {"task_id": 242, ...}

    Returns:
        执行结果 {
            "success": True,
            "strategies_executed": 49,
            "signals_generated": 12,
            "orders_created": 5
        }
    """
    if task_context is None:
        task_context = {}

    try:
        logger.info("开始每日信号执行任务")

        from infrastructure.config.service_factory import get_data_service

        ds = get_data_service()

        # 1. 获取所有启用的策略（使用 ORM 查询）
        try:
            strategies = ds.strategy.list_strategies()
            logger.info(f"找到 {len(strategies)} 个策略")
        except Exception as e:
            logger.warning(f"获取策略列表失败: {e}")
            strategies = []

        logger.info(f"找到 {len(strategies)} 个启用的策略")

        strategies_executed = 0
        signals_generated = 0
        execution_date = date.today()

        # 2. 遍历执行每个策略
        for strategy in strategies:
            try:
                strategy_id = strategy['id']
                strategy_name = strategy['name']

                logger.info(f"执行策略 {strategy_id}: {strategy_name}")

                # 运行策略代码 (通过API调用或直接执行)
                # TODO: 实现策略执行逻辑
                # result = ds.strategy.execute_strategy(strategy_id, execution_date)

                # 临时跳过策略执行
                logger.info(f"策略 {strategy_id} 执行已跳过（待实现）")

            except Exception as e:
                logger.error(f"执行策略 {strategy.get('id')} 时出错: {e}", exc_info=True)
                continue

        # 4. 返回统计结果
        result = {
            'action': 'signal_execution_daily',
            'status': 'success',
            'success': True,
            'execution_date': str(execution_date),
            'strategies_executed': strategies_executed,
            'signals_generated': signals_generated,
            'orders_created': 0,  # TODO: 集成订单创建逻辑
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"每日信号执行完成: {result}")
        return result

    except Exception as e:
        logger.error(f"每日信号执行任务失败: {e}", exc_info=True)
        return {
            'action': 'signal_execution_daily',
            'status': 'failed',
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# 向后兼容：支持调度器直接调用模块
if __name__ == '__main__':
    result = execute_daily_signals({})
    logger.info(result)
