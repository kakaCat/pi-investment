"""
V14 FastAPI 路由

提供V14策略的REST API接口
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

from infrastructure.jobs.strategy_trading_job import v14_daily_check, v14_manual_rebalance
from live_trading.simulation_trader import SimulationTrader
from application.strategies.v14_use_case import V14StrategyUseCase

logger = logging.getLogger(__name__)

# 创建V14路由器
router = APIRouter(prefix="/api/v14", tags=["V14 Trading"])


@router.get("/account-info")
async def get_account_info():
    """获取V14账户信息"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'
        trader.model_path = 'live_trading/models/v14_p0_model.json'
        trader.factors_path = 'live_trading/models/v14_p0_valid_factors.json'

        # 获取账户信息
        account = trader.repo.get_account(trader.account_name)
        positions = trader.repo.get_all_positions(trader.account_name)

        # 计算持仓市值
        position_value = sum(
            pos.shares_total * (pos.current_price if pos.current_price else pos.avg_cost)
            for pos in positions
        )

        return {
            'success': True,
            'account_name': trader.account_name,
            'totalValue': float(account.total_value if account else 100000),
            'cash': float(account.cash if account else 10000),
            'positionValue': float(position_value),
            'totalReturn': float((account.total_value - 100000) / 100000 if account else 0),
            'positionsCount': len(positions),
            'lastRebalanceDate': account.last_rebalance_date.strftime('%Y-%m-%d') if account and hasattr(account, 'last_rebalance_date') else None
        }

    except Exception as e:
        logger.error(f"获取V14账户信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    """获取V14持仓明细"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        positions = trader.repo.get_all_positions(trader.account_name)

        return {
            'success': True,
            'positions': [
                {
                    'symbol': pos.symbol,
                    'name': getattr(pos, 'name', pos.symbol),
                    'shares': pos.shares_total,
                    'shares_available': pos.shares_available,
                    'avgPrice': float(pos.avg_cost),
                    'currentPrice': float(pos.current_price if pos.current_price else pos.avg_cost),
                    'profit': float(((pos.current_price if pos.current_price else pos.avg_cost) - pos.avg_cost) * pos.shares_total),
                    'profitRate': float(((pos.current_price if pos.current_price else pos.avg_cost) / pos.avg_cost - 1) if pos.avg_cost else 0),
                    'weight': 0.18  # 简化，实际应计算
                }
                for pos in positions
            ]
        }

    except Exception as e:
        logger.error(f"获取V14持仓失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades")
async def get_trades(limit: int = 50):
    """获取V14交易记录"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        trades = trader.repo.get_recent_trades(limit=limit)

        return {
            'success': True,
            'trades': [
                {
                    'id': trade.id,
                    'timestamp': trade.timestamp.isoformat() if hasattr(trade, 'timestamp') else None,
                    'action': trade.action,
                    'symbol': trade.symbol,
                    'shares': trade.shares,
                    'price': float(trade.price),
                    'amount': float(trade.shares * trade.price)
                }
                for trade in trades
            ]
        }

    except Exception as e:
        logger.error(f"获取V14交易记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-rebalance")
async def manual_rebalance():
    """V14手动调仓"""
    try:
        logger.info("收到V14手动调仓请求")

        result = v14_manual_rebalance(account_name='v14_simulation')

        return result

    except Exception as e:
        logger.error(f"V14手动调仓失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily-check")
async def daily_check():
    """V14每日检查"""
    try:
        logger.info("收到V14每日检查请求")

        result = v14_daily_check(
            enable_stop_loss=True,
            enable_rebalance=True,
            account_name='v14_simulation'
        )

        return result

    except Exception as e:
        logger.error(f"V14每日检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-config")
async def get_strategy_config():
    """获取V14策略配置"""
    try:
        config = V14StrategyUseCase.CONFIG

        return {
            'success': True,
            'config': {
                'name': config.name,
                'version': config.version,
                'description': config.description,
                'rebalanceDays': config.rebalance_days,
                'maxPositions': config.max_positions,
                'maxPositionPct': config.max_position_pct,
                'modelPath': config.model_path,
                'params': config.params
            }
        }

    except Exception as e:
        logger.error(f"获取V14策略配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance():
    """获取V14收益曲线数据"""
    try:
        # TODO: 从数据库查询历史净值数据
        # 这里返回示例数据
        return {
            'success': True,
            'performance': {
                'dates': ['2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01', '2026-05-01', '2026-06-01', '2026-07-01'],
                'values': [100000, 105000, 112000, 118000, 125000, 135000, 141000],
                'returns': [0, 0.05, 0.12, 0.18, 0.25, 0.35, 0.41],
                'benchmark': [0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.18]
            }
        }

    except Exception as e:
        logger.error(f"获取V14收益曲线失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
