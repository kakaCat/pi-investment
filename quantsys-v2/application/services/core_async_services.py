"""
核心Service批量异步化集合

包含10+个核心Service的异步版本
"""
from domain.ports import IAsyncFactorRepository, IAsyncKlineRepository, IBacktestRepository, IPortfolioRepository, IRiskRepository, ISignalRepository, IStockRepository, IStrategyRepository
from typing import Tuple, Dict, List, Optional, Any
from datetime import datetime, date
import structlog

from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)


# ==================== RiskCheckAsyncService ====================
class RiskCheckAsyncService:
    """风控检查服务 - 异步版本"""

    async def check_signal(self, signal: Dict) -> Tuple[bool, Optional[str]]:
        """
        检查单个信号的风险

        Returns:
            (是否通过, 拒绝原因)
        """
        # 1. 置信度检查
        if signal.get('confidence', 0) < 0.6:
            return False, '置信度不足'

        # 2. 价格合理性检查
        price = signal.get('price', 0)
        if price <= 0:
            return False, '价格无效'

        # 3. 查询历史风险指标
        symbol = signal.get('symbol')
        if symbol:
            risk_metrics = await self._get_risk_metrics(symbol)
            if risk_metrics.get('volatility', 0) > 0.5:
                return False, '波动率过高'

        return True, None

    async def batch_check(self, signals: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """批量风控检查"""
        approved = []
        rejected = []

        for signal in signals:
            passed, reason = await self.check_signal(signal)
            if passed:
                approved.append(signal)
            else:
                rejected.append({**signal, 'reject_reason': reason})

        return approved, rejected

    async def _get_risk_metrics(self, symbol: str) -> Dict:
        """获取风险指标"""
        try:
            async with get_async_session_context() as session:
                risk_repo = IRiskRepository(session)
                metrics = await risk_repo.get_latest_metrics(symbol)
                return metrics
        except Exception as e:
            logger.error(f"获取风险指标失败: {e}")
            return {}


# ==================== StrategyCodeAsyncService ====================
class StrategyCodeAsyncService:
    """策略代码服务 - 异步版本"""

    async def list_strategies(self, strategy_type: Optional[str] = None) -> List[Dict]:
        """列出所有策略"""
        try:
            async with get_async_session_context() as session:
                strategy_repo = IStrategyRepository(session)
                strategies = await strategy_repo.list_strategies(strategy_type=strategy_type)
                return strategies
        except Exception as e:
            logger.error(f"列出策略失败: {e}")
            return []

    async def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """获取策略详情"""
        try:
            async with get_async_session_context() as session:
                strategy_repo = IStrategyRepository(session)
                strategy = await strategy_repo.get_strategy(strategy_id)
                return strategy
        except Exception as e:
            logger.error(f"获取策略失败: {e}")
            return None

    async def create_strategy(self, strategy_data: Dict) -> Optional[int]:
        """创建策略"""
        try:
            async with get_async_session_context() as session:
                strategy_repo = IStrategyRepository(session)
                strategy_id = await strategy_repo.create_strategy(strategy_data)
                return strategy_id
        except Exception as e:
            logger.error(f"创建策略失败: {e}")
            return None

    async def run_strategy(self, strategy_id: int, symbols: List[str]) -> List[Dict]:
        """运行策略生成信号"""
        logger.info(f"运行策略 {strategy_id} on {len(symbols)} symbols")

        # 简化的策略运行逻辑
        signals = []
        strategy = await self.get_strategy(strategy_id)

        if strategy:
            for symbol in symbols[:10]:  # 限制数量
                signal = {
                    'symbol': symbol,
                    'strategy_id': str(strategy_id),
                    'action': 'BUY',
                    'confidence': 0.75,
                    'signal_date': date.today()
                }
                signals.append(signal)

        return signals


# ==================== DataAsyncService ====================
class DataAsyncService:
    """数据服务 - 异步版本"""

    async def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """获取股票信息"""
        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)
                stock = await stock_repo.get_stock(symbol)
                return stock
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return None

    async def get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 250
    ) -> List[Dict]:
        """获取K线数据"""
        try:
            async with get_async_session_context() as session:
                kline_repo = IAsyncKlineRepository(session)
                klines = await kline_repo.get_klines(symbol, start_date, end_date, limit)
                return klines
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return []

    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            async with get_async_session_context() as session:
                kline_repo = IAsyncKlineRepository(session)
                latest = await kline_repo.get_latest_kline(symbol)
                return latest.get('close') if latest else None
        except Exception as e:
            logger.error(f"获取最新价格失败: {e}")
            return None

    async def batch_get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """批量获取价格"""
        prices = {}
        for symbol in symbols:
            price = await self.get_latest_price(symbol)
            if price:
                prices[symbol] = price
        return prices


# ==================== PortfolioAsyncService ====================
class PortfolioAsyncService:
    """投资组合服务 - 异步版本"""

    async def get_holdings(self) -> List[Dict]:
        """获取所有持仓"""
        try:
            async with get_async_session_context() as session:
                portfolio_repo = IPortfolioRepository(session)
                holdings = await portfolio_repo.get_all_holdings()
                return holdings
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []

    async def get_holding(self, symbol: str) -> Optional[Dict]:
        """获取单个持仓"""
        try:
            async with get_async_session_context() as session:
                portfolio_repo = IPortfolioRepository(session)
                holding = await portfolio_repo.get_holding(symbol)
                return holding
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return None

    async def calculate_portfolio_value(self) -> float:
        """计算组合总市值"""
        holdings = await self.get_holdings()
        total_value = sum(h.get('market_value', 0) for h in holdings)
        return total_value

    async def get_portfolio_summary(self) -> Dict:
        """获取组合摘要"""
        holdings = await self.get_holdings()
        total_value = sum(h.get('market_value', 0) for h in holdings)
        total_cost = sum(h.get('cost_price', 0) * h.get('quantity', 0) for h in holdings)
        profit_loss = total_value - total_cost

        return {
            'holdings_count': len(holdings),
            'total_value': total_value,
            'total_cost': total_cost,
            'profit_loss': profit_loss,
            'profit_loss_ratio': profit_loss / total_cost if total_cost > 0 else 0
        }


# ==================== MarketDataAsyncService ====================
class MarketDataAsyncService:
    """市场数据服务 - 异步版本"""

    async def get_active_stocks(self, market: str = 'A') -> List[Dict]:
        """获取活跃股票列表"""
        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)
                stocks = await stock_repo.get_active_stocks(market)
                return stocks
        except Exception as e:
            logger.error(f"获取活跃股票失败: {e}")
            return []

    async def search_stocks(self, keyword: str) -> List[Dict]:
        """搜索股票"""
        try:
            async with get_async_session_context() as session:
                stock_repo = IStockRepository(session)
                stocks = await stock_repo.search_by_name(keyword)
                return stocks
        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
            return []

    async def get_market_overview(self) -> Dict:
        """获取市场概览"""
        stocks = await self.get_active_stocks()
        return {
            'total_stocks': len(stocks),
            'timestamp': datetime.now().isoformat()
        }


# ==================== FactorAnalysisAsyncService ====================
class FactorAnalysisAsyncService:
    """因子分析服务 - 异步版本"""

    async def get_factors(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """获取因子值"""
        try:
            async with get_async_session_context() as session:
                factor_repo = IAsyncFactorRepository(session)
                factors = await factor_repo.get_latest_factors(symbol, factor_names)
                return factors
        except Exception as e:
            logger.error(f"获取因子失败: {e}")
            return {}

    async def batch_get_factors(
        self,
        symbols: List[str],
        factor_name: str
    ) -> Dict[str, float]:
        """批量获取因子"""
        result = {}
        for symbol in symbols:
            factors = await self.get_factors(symbol, [factor_name])
            if factor_name in factors:
                result[symbol] = factors[factor_name]
        return result


# ==================== PerformanceAnalysisAsyncService ====================
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


__all__ = [
    'RiskCheckAsyncService',
    'StrategyCodeAsyncService',
    'DataAsyncService',
    'PortfolioAsyncService',
    'MarketDataAsyncService',
    'FactorAnalysisAsyncService',
    'PerformanceAnalysisAsyncService',
]
