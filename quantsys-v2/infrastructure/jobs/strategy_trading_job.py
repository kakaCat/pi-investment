"""
统一策略交易定时任务

提供配置驱动的定时任务，支持所有策略版本（V13/V14/V15...）
避免重复代码，统一接口

使用方式：
    # 通用接口
    strategy_daily_check('v13')
    strategy_daily_check('v14')
    strategy_daily_check('v15')

    # 向后兼容接口
    v13_daily_check()
    v14_daily_check()
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

from application.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


def strategy_daily_check(strategy_name: str, **params):
    """
    策略每日检查（统一接口）

    Args:
        strategy_name: 策略名称（v13/v14/v15...）
        **params: 可选参数（覆盖配置）
            - enable_stop_loss: 是否启用止损检查（默认True）
            - enable_rebalance: 是否启用调仓（默认True）
            - rebalance_days: 覆盖调仓周期
            - max_positions: 覆盖最大持仓数

    Returns:
        dict: 执行结果
            - strategy: 策略名称
            - status: 'success' | 'failed'
            - account_name: 账户名称
            - timestamp: 执行时间
            - initial_value: 初始资产
            - final_value: 最终资产
            - cash: 现金
            - positions_count: 持仓数量
            - cumulative_return: 累计收益率

    Examples:
        # V13
        strategy_daily_check('v13')

        # V14
        strategy_daily_check('v14')

        # V15（未来，无需修改代码）
        strategy_daily_check('v15')

        # 带参数
        strategy_daily_check('v13', enable_stop_loss=False)
    """
    logger.info(f"{'='*70}")
    logger.info(f"{strategy_name.upper()} 模拟交易每日检查开始")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*70}")

    try:
        service = StrategyService()

        # 获取策略配置
        config = service.get_config(strategy_name)
        logger.info(f"策略配置:")
        logger.info(f"  名称: {config['strategy']['name']}")
        logger.info(f"  版本: {config['strategy']['version']}")
        logger.info(f"  账户: {config['strategy']['account_name']}")
        logger.info(f"  调仓周期: {config['trading']['rebalance_days']}天")
        logger.info(f"  最大持仓: {config['trading']['max_positions']}只")

        # 执行每日检查
        result = service.daily_check(strategy_name, **params)

        logger.info(f"\n{'='*70}")
        logger.info(f"✅ {strategy_name.upper()} 模拟交易每日检查完成")
        logger.info(f"{'='*70}")
        logger.info(f"执行结果:")
        logger.info(f"  状态: {result['status']}")
        logger.info(f"  账户: {result['account_name']}")
        logger.info(f"  最终资产: ¥{result['final_value']:,.2f}")
        logger.info(f"  现金: ¥{result['cash']:,.2f}")
        logger.info(f"  持仓数量: {result['positions_count']}只")
        logger.info(f"  累计收益率: {result['cumulative_return']*100:.2f}%")
        logger.info(f"{'='*70}")

        return result

    except Exception as e:
        logger.error(f"{'='*70}")
        logger.error(f"❌ {strategy_name.upper()} 模拟交易每日检查失败")
        logger.error(f"{'='*70}")
        logger.error(f"错误信息: {e}")

        import traceback
        traceback.print_exc()

        return {
            'strategy': strategy_name,
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# ==================== 向后兼容接口 ====================

def v13_daily_check(**params):
    """
    V13每日检查（向后兼容接口）

    这是一个兼容层，实际调用统一接口 strategy_daily_check('v13')

    Args:
        **params: 可选参数
            - model_path: 模型路径（会被配置覆盖）
            - factors_path: 因子路径（会被配置覆盖）
            - enable_stop_loss: 是否启用止损
            - enable_rebalance: 是否启用调仓

    Returns:
        dict: 执行结果（与原接口格式一致）

    Note:
        建议使用新接口 strategy_daily_check('v13')
    """
    logger.info("⚠️ 使用旧接口 v13_daily_check()，建议迁移到 strategy_daily_check('v13')")
    return strategy_daily_check('v13', **params)


def v14_daily_check(**params):
    """
    V14每日检查（向后兼容接口）

    这是一个兼容层，实际调用统一接口 strategy_daily_check('v14')

    Args:
        **params: 可选参数（同 v13_daily_check）

    Returns:
        dict: 执行结果（与原接口格式一致）

    Note:
        建议使用新接口 strategy_daily_check('v14')
    """
    logger.info("⚠️ 使用旧接口 v14_daily_check()，建议迁移到 strategy_daily_check('v14')")
    return strategy_daily_check('v14', **params)


def v13_manual_rebalance(**params):
    """
    V13手动调仓（向后兼容接口）

    Note:
        建议使用新接口: StrategyService().manual_rebalance('v13')
    """
    logger.info("⚠️ 使用旧接口 v13_manual_rebalance()，建议迁移到统一接口")
    service = StrategyService()
    return service.manual_rebalance('v13', **params)


def v14_manual_rebalance(**params):
    """
    V14手动调仓（向后兼容接口）

    Note:
        建议使用新接口: StrategyService().manual_rebalance('v14')
    """
    logger.info("⚠️ 使用旧接口 v14_manual_rebalance()，建议迁移到统一接口")
    service = StrategyService()
    return service.manual_rebalance('v14', **params)


# ==================== 测试入口 ====================

if __name__ == '__main__':
    """命令行测试"""
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python strategy_trading_job.py v13")
        print("  python strategy_trading_job.py v14")
        print("  python strategy_trading_job.py v15")
        sys.exit(1)

    strategy = sys.argv[1]
    print(f"\n开始测试 {strategy} 每日检查...\n")

    result = strategy_daily_check(strategy)

    if result['status'] == 'success':
        print(f"\n✅ 测试成功")
        sys.exit(0)
    else:
        print(f"\n❌ 测试失败: {result.get('error')}")
        sys.exit(1)
