"""
回测历史查询 API - FastAPI 异步版本
"""
from fastapi import APIRouter, Query
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["Backtest History"])


def _to_camel(snake_str: str) -> str:
    """转换为驼峰命名"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _convert_dict_to_camel(data: dict) -> dict:
    """将字典键转换为驼峰命名"""
    return {_to_camel(k): v for k, v in data.items()}


@router.get("/history")
async def get_backtest_history(
    strategy_name: Optional[str] = Query(None, description="策略名称"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制")
):
    """
    查询回测历史记录

    返回回测历史列表，支持按策略名称和股票代码筛选
    """
    try:
        from adapters.outbound.repositories import BacktestORMRepository

        backtest_repo = BacktestORMRepository()
        results = backtest_repo.get_all_backtests(
            strategy_name=strategy_name,
            symbol=symbol,
            limit=limit
        )

        # 转换为驼峰命名
        results_camel = [_convert_dict_to_camel(r) for r in results]

        return {
            "success": True,
            "data": {
                "items": results_camel,
                "count": len(results_camel)
            }
        }

    except Exception as e:
        logger.exception(f"Failed to get backtest history: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stats")
async def get_backtest_stats(
    strategy_name: Optional[str] = Query(None, description="策略名称")
):
    """
    获取回测统计信息

    返回:
    - totalBacktests: 总回测次数
    - avgSharpe: 平均夏普比率
    - avgReturn: 平均收益率
    - avgMaxDrawdown: 平均最大回撤
    - bestSharpe: 最佳夏普比率
    - bestReturn: 最佳收益率
    """
    try:
        from adapters.outbound.repositories import BacktestORMRepository

        backtest_repo = BacktestORMRepository()
        stats = backtest_repo.get_backtest_stats(strategy_name=strategy_name)

        # 转换为驼峰命名
        stats_camel = _convert_dict_to_camel(stats)

        return {
            "success": True,
            "data": stats_camel
        }

    except Exception as e:
        logger.exception(f"Failed to get backtest stats: {e}")
        return {
            "success": False,
            "error": str(e)
        }
