"""
V13模拟交易Job - 定时任务执行逻辑

每日检查：
1. 加载V13模型（68因子，IC=0.5465）
2. 检查单股止损（-15%）
3. 判断是否到调仓日（5天周期）
4. 执行调仓（如到期）
"""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from live_trading.simulation_trader import SimulationTrader

logger = logging.getLogger(__name__)


def v13_daily_check(**params):
    """
    V13模拟交易每日检查

    Args:
        **params: 任务参数
            - model_path: 模型文件路径
            - factors_path: 因子文件路径
            - enable_stop_loss: 是否启用止损检查
            - enable_rebalance: 是否启用调仓

    Returns:
        dict: 执行结果
    """
    logger.info("="*70)
    logger.info("V13模拟交易每日检查开始")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)

    trader = None
    try:
        # 初始化交易器
        logger.info("初始化交易器...")
        # 使用绝对路径加载配置
        config_path = project_root / 'live_trading' / 'config_simulation.yaml'
        trader = SimulationTrader(config_path=str(config_path))
        trader.load_model()

        logger.info(f"模型已加载: {len(trader.valid_factors)}个因子")

        # 获取当前账户状态
        total_value = trader._calculate_total_value_from_portfolio()
        logger.info(f"\n当前账户:")
        logger.info(f"  现金: ¥{trader.cash:,.2f}")
        logger.info(f"  持仓: {len(trader.portfolio)}只")
        logger.info(f"  总资产: ¥{total_value:,.2f}")
        logger.info(f"  累计收益: {(total_value / 100000 - 1):.2%}")

        # 执行每日检查
        logger.info("\n执行每日检查...")
        trader.run_daily_check()

        # 获取更新后的状态
        final_value = trader._calculate_total_value_from_portfolio()

        result = {
            'action': 'v13_daily_check',
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'initial_value': total_value,
            'final_value': final_value,
            'cash': trader.cash,
            'positions': len(trader.portfolio),
            'cumulative_return': (final_value / 100000 - 1),
            'message': '每日检查完成'
        }

        logger.info("\n执行结果:")
        logger.info(f"  状态: 成功")
        logger.info(f"  最终资产: ¥{final_value:,.2f}")
        logger.info(f"  持仓数量: {len(trader.portfolio)}只")

        logger.info("="*70)
        logger.info("✅ V13模拟交易每日检查完成")
        logger.info("="*70)

        return result

    except Exception as e:
        logger.error(f"❌ V13模拟交易每日检查失败: {e}")
        import traceback
        traceback.print_exc()

        return {
            'action': 'v13_daily_check',
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'message': '每日检查失败'
        }

    finally:
        # ORM Repository不需要手动close（使用scoped_session自动管理）
        if trader is not None:
            try:
                if hasattr(trader.repo, 'close'):
                    trader.repo.close()
                    logger.debug("数据库连接已释放")
            except Exception as e:
                logger.warning(f"释放连接时出错: {e}")


# Job注册点 - scheduler会调用这个函数
def execute(**params):
    """Scheduler调用的入口函数"""
    return v13_daily_check(**params)


if __name__ == '__main__':
    # 测试执行
    result = v13_daily_check()
    print(f"\n执行结果: {result}")
