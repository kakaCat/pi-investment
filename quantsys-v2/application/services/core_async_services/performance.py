"""绩效分析服务 - 异步版本"""
from typing import Dict

import structlog

from qs_kernel.domain.ports.repository_ports_extended import IBacktestRepository
from qs_kernel.infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)


class PerformanceAnalysisAsyncService:
    """绩效分析服务 - 异步版本"""

    async def analyze_strategy_performance(
        self,
        strategy_name: str
    ) -> Dict:
        """分析策略绩效"""
        try:
            async with get_async_session_context() as session:
                backtest_repo = IBacktestRepository(session)
                backtests = await backtest_repo.list_backtests(
                    strategy_name=strategy_name,
                    limit=100
                )

                if not backtests:
                    return {'strategy_name': strategy_name, 'backtest_count': 0}

                # 计算平均指标
                avg_return = sum(b.get('total_return', 0) for b in backtests) / len(backtests)
                avg_sharpe = sum(b.get('sharpe_ratio', 0) for b in backtests) / len(backtests)

                return {
                    'strategy_name': strategy_name,
                    'backtest_count': len(backtests),
                    'avg_return': avg_return,
                    'avg_sharpe': avg_sharpe,
                    'best_return': max(b.get('total_return', 0) for b in backtests),
                    'worst_return': min(b.get('total_return', 0) for b in backtests)
                }
        except Exception as e:
            logger.error(f"分析策略绩效失败: {e}")
            return {}
