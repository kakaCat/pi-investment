"""
回测引擎 - 异步版本

⚠️ DEPRECATED（2026-09-01，E-1 修复）：本类的 _simulate_trading 曾是随机数假回测
（random.uniform 生成假夏普 0.5~2.5），已改为显式抛 NotImplementedError。
真实回测：StrategyCodeService.backtest_strategy / RealBacktestEngineAdapter。
本类保留仅为 run_backtest 异步任务外壳的兼容性，不再产生任何回测数据。
"""
from domain.ports import IAsyncKlineRepository, IBacktestRepository
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import structlog

from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)


class BacktestAsyncEngine:
    """回测引擎 - 异步版本"""

    def __init__(self):
        pass

    async def run_backtest(
        self,
        strategy_name: str,
        symbol: Optional[str] = None,
        start_date: str = '2023-01-01',
        end_date: str = '2024-12-31',
        initial_capital: float = 100000.0
    ) -> Optional[Dict[str, Any]]:
        """
        运行回测

        Args:
            strategy_name: 策略名称
            symbol: 股票代码（可选）
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金

        Returns:
            回测结果或None
        """
        logger.info(f"开始回测: {strategy_name}, {symbol}, {start_date} - {end_date}")

        try:
            # Step 1: 获取K线数据
            if symbol:
                klines = await self._get_klines(symbol, start_date, end_date)
                if not klines:
                    logger.warning(f"未获取到K线数据: {symbol}")
                    return None

            # Step 2: 运行回测逻辑（简化版）
            result = await self._simulate_trading(
                strategy_name,
                symbol,
                initial_capital
            )

            # Step 3: 保存回测结果
            backtest_id = await self._save_result(result)

            result['id'] = backtest_id
            logger.info(f"回测完成: ID={backtest_id}")
            return result

        except Exception as e:
            logger.error(f"回测失败: {e}")
            return None

    async def _get_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """获取K线数据"""
        try:
            async with get_async_session_context() as session:
                kline_repo = IAsyncKlineRepository(session)
                klines = await kline_repo.get_klines(
                    symbol,
                    start_date,
                    end_date,
                    limit=500
                )
                return klines

        except Exception as e:
            logger.error(f"获取K线失败: {e}")
            return []

    async def _simulate_trading(
        self,
        strategy_name: str,
        symbol: Optional[str],
        initial_capital: float
    ) -> Dict[str, Any]:
        """已禁用（2026-09-01，E-1 修复）。

        原实现用 random.uniform 生成假收益/假夏普（0.5~2.5）/假回撤——
        任何调用方拿到的都是随机数，且假数据会落库污染 backtest_results。
        显式拒服，防止静默造假；真实回测走 StrategyCodeService.backtest_strategy
        （同步接口见 RealBacktestEngineAdapter）。
        """
        raise NotImplementedError(
            "BacktestAsyncEngine 是随机数假引擎，已禁用（2026-09-01）。"
            "真实回测请用 StrategyCodeService.backtest_strategy "
            "或 RealBacktestEngineAdapter（application.services.real_backtest_engine_adapter）"
        )

    async def _save_result(self, result: Dict[str, Any]) -> Optional[int]:
        """保存回测结果"""
        try:
            async with get_async_session_context() as session:
                backtest_repo = IBacktestRepository(session)
                backtest_id = await backtest_repo.create_backtest(result)
                return backtest_id

        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")
            return None

    async def get_recent_backtests(
        self,
        strategy_name: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """获取最近的回测结果"""
        try:
            async with get_async_session_context() as session:
                backtest_repo = IBacktestRepository(session)
                backtests = await backtest_repo.list_backtests(
                    strategy_name=strategy_name,
                    limit=limit
                )
                return backtests

        except Exception as e:
            logger.error(f"获取回测结果失败: {e}")
            return []

    async def get_best_strategies(
        self,
        min_sharpe: float = 1.0,
        limit: int = 10
    ) -> List[Dict]:
        """获取表现最好的策略"""
        try:
            async with get_async_session_context() as session:
                backtest_repo = IBacktestRepository(session)
                backtests = await backtest_repo.get_best_backtests(
                    min_sharpe_ratio=min_sharpe,
                    limit=limit
                )
                return backtests

        except Exception as e:
            logger.error(f"获取最佳策略失败: {e}")
            return []


__all__ = ['BacktestAsyncEngine']
