"""
统一数据访问服务 (DataService) - ORM版本

使用ORM Repository重构，提供跨表高级查询和工作流方法。
支持可选的缓存集成（look-aside pattern）。

迁移状态：✅ 已完成ORM迁移
"""
from domain.ports import IRiskRepository, ISignalExecutionRepository
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import structlog
import polars as pl

# 使用ORM Repository
from domain.ports.repository_ports_extended import (
    IStockRepository,
    IKlineRepository,
    ISignalRepository,
    ISimulationRepository,
    IPortfolioRepository,
    IFactorRepository,
    IBacktestRepository
)

# 保留原有Repository用于未迁移的功能

from infrastructure.config import CACHE_TTL, CACHE_NAMESPACE
from infrastructure.persistence.orm import close_session
from application.services.financial_data_service_adapter import FinancialDataServiceAdapter as FinancialDataService

logger = structlog.get_logger(__name__)


class DataServiceORM:
    """统一数据访问服务（ORM版本），聚合所有Repository

    特性：
    - 使用ORM Repository（类型安全、自动Session管理）
    - 支持缓存（look-aside模式）
    - 跨表高级查询
    - 自动清理Session

    使用示例：
        service = DataServiceORM()
        try:
            data = service.get_stock_full_data('000001', '2026-01-01', '2026-06-30')
        finally:
            service.cleanup()  # 清理Session
    """

    def __init__(
        self,
        cache_manager=None,
        stock_repo: Optional[IStockRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        signal_repo: Optional[ISignalRepository] = None,
        simulation_repo: Optional[ISimulationRepository] = None,
        portfolio_repo: Optional[IPortfolioRepository] = None,
        factor_repo: Optional[IFactorRepository] = None,
        backtest_repo: Optional[IBacktestRepository] = None,
        risk_repo: Optional[IRiskRepository] = None,
        execution_repo: Optional[ISignalExecutionRepository] = None,
        financial_service: Optional[FinancialDataService] = None,
    ):
        """初始化DataService

        Args:
            cache_manager: 可选的缓存管理器（支持look-aside模式）
            *_repo: Repository 实例（可选，用于依赖注入）
            financial_service: 财务数据服务（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例而非直接构造
        """
        # P2-1: 依赖注入 - 优先使用传入的实例，否则回退到直接实例化
        self.stock = stock_repo
        self.kline = kline_repo
        self.signal = signal_repo
        self.simulation = simulation_repo
        self.portfolio = portfolio_repo
        self.factor = factor_repo
        self.backtest = backtest_repo

        # 原生Repository（待迁移）
        self.risk = risk_repo
        self.execution = execution_repo

        self._cache = cache_manager

        # 初始化财务数据多源服务
        self.financial_service = financial_service or FinancialDataService()

        if self._cache:
            logger.info(f"DataServiceORM初始化，缓存后端: {self._cache.get_stats().get('backend', 'unknown')}")

    def cleanup(self):
        """清理Session（请求/Job结束时调用）"""
        close_session()

    # ==================== 缓存辅助方法 ====================

    def _cache_get(self, namespace: str, key: str):
        """从缓存获取数据"""
        if self._cache:
            try:
                return self._cache.get(namespace, key)
            except Exception:
                pass
        return None

    def _cache_set(self, namespace: str, key: str, data, ttl: int = None):
        """写入缓存"""
        if self._cache:
            try:
                self._cache.set(namespace, key, data, ttl=ttl)
            except Exception:
                pass

    def _cache_clear_pattern(self, namespace: str, pattern: str):
        """清除匹配模式的缓存"""
        if self._cache:
            try:
                self._cache.invalidate_by_pattern(namespace, pattern)
            except Exception:
                pass

    # ==================== 股票综合查询 ====================

    def get_stock_full_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """获取股票完整数据（K线 + 因子 + 信号）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {symbol, stock_info, klines, factors, signals, kline_stats}
        """
        cache_key = f"stock_full:{symbol}:{start_date}:{end_date}"
        cached = self._cache_get('daily', cache_key)
        if cached:
            return cached

        # 获取股票基本信息（ORM对象）
        stock_obj = self.stock.get_by_symbol(symbol)
        stock_info = stock_obj.to_dict() if stock_obj else None

        # 获取K线数据（Polars DataFrame）
        klines_df = self.kline.get_daily_klines(symbol, start_date, end_date)

        # Convert polars DataFrame to List[Dict] for backward compatibility
        if isinstance(klines_df, pl.DataFrame):
            klines = klines_df.to_dicts() if not klines_df.is_empty() else []
        else:
            klines = []

        # 获取最新因子值（ORM对象列表）
        latest_factors_objs = self.factor.get_latest_factors(symbol)
        latest_factors = [f.to_dict() for f in latest_factors_objs]

        # 获取该时间段内的信号（ORM对象列表）
        signals_objs = self.signal.get_signals_by_symbol(symbol, start_date, end_date)
        signals = [s.to_dict() for s in signals_objs]

        # K线统计
        kline_count = self.kline.count_daily_klines(symbol)
        date_range = self.kline.get_date_range(symbol)

        kline_stats = {
            'total_records': kline_count,
            'date_range': {
                'start': date_range[0].isoformat() if date_range else None,
                'end': date_range[1].isoformat() if date_range else None
            }
        }

        result = {
            'symbol': symbol,
            'stock_info': stock_info,
            'klines': klines,
            'kline_stats': kline_stats,
            'latest_factors': latest_factors,
            'signals': signals,
            'date_range': {'start': start_date, 'end': end_date}
        }

        self._cache_set('daily', cache_key, result, ttl=300)  # 5分钟TTL
        return result

    def get_stock_analysis(
        self,
        symbol: str,
        date: str = None
    ) -> Dict:
        """获取股票分析快照

        Args:
            symbol: 股票代码
            date: 分析日期 (默认为最新)

        Returns:
            {stock_info, latest_kline, factors, latest_signal}
        """
        # 获取股票信息
        stock_obj = self.stock.get_by_symbol(symbol)
        stock_info = stock_obj.to_dict() if stock_obj else None

        # 获取最新K线
        latest_kline_df = self.kline.get_latest_daily_kline(symbol)
        latest_kline = None
        if latest_kline_df is not None and len(latest_kline_df) > 0:
            latest_kline = latest_kline_df.to_dicts()[0]

        # 获取最新因子
        factors_objs = self.factor.get_latest_factors(symbol)
        factors = {f.factor_name: f.factor_value for f in factors_objs}

        # 获取最新信号
        latest_signal_obj = self.signal.get_latest_signal_by_symbol(symbol)
        latest_signal = latest_signal_obj.to_dict() if latest_signal_obj else None

        return {
            'symbol': symbol,
            'stock_info': stock_info,
            'latest_kline': latest_kline,
            'factors': factors,
            'latest_signal': latest_signal,
            'analysis_date': date or datetime.now().strftime('%Y-%m-%d')
        }

    # ==================== 批量查询 ====================

    def get_stocks_by_market(
        self,
        market: str,
        include_suspended: bool = False,
        limit: int = None
    ) -> List[Dict]:
        """获取指定市场的股票列表

        Args:
            market: 市场类型（A/HK）
            include_suspended: 是否包含停牌股
            limit: 返回数量限制

        Returns:
            股票列表（字典格式）
        """
        stocks = self.stock.list_by_market(
            market=market,
            include_suspended=include_suspended,
            limit=limit
        )
        return [s.to_dict() for s in stocks]

    def get_latest_klines_batch(
        self,
        symbols: List[str]
    ) -> Dict[str, Dict]:
        """批量获取最新K线

        Args:
            symbols: 股票代码列表

        Returns:
            {symbol: kline_dict}
        """
        return self.kline.get_latest_daily_klines_batch(symbols)

    # ==================== 持仓相关 ====================

    def get_portfolio_summary(self) -> Dict:
        """获取持仓汇总

        Returns:
            持仓汇总信息
        """
        return self.portfolio.get_holdings_summary()

    def get_portfolio_holdings(
        self,
        market: Optional[str] = None
    ) -> List[Dict]:
        """获取持仓列表

        Args:
            market: 市场筛选

        Returns:
            持仓列表
        """
        # get_all_holdings 已恢复 List[Dict] 契约（见 portfolio_repository）
        return self.portfolio.get_all_holdings(market=market)

    # ==================== 信号相关 ====================

    def get_recent_signals(
        self,
        days: int = 7,
        action: Optional[str] = None
    ) -> List[Dict]:
        """获取最近N天的信号

        Args:
            days: 天数
            action: 操作类型筛选

        Returns:
            信号列表
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        signals = self.signal.get_signals_by_date_range(
            start_date=start_date,
            end_date=end_date,
            action=action
        )
        return [s.to_dict() for s in signals]

    def get_pending_signals(self) -> List[Dict]:
        """获取待处理信号

        Returns:
            待处理信号列表
        """
        signals = self.signal.get_pending_signals()
        return [s.to_dict() for s in signals]

    # ==================== 回测相关 ====================

    def get_strategy_performance(
        self,
        strategy_name: str
    ) -> Dict:
        """获取策略表现统计

        Args:
            strategy_name: 策略名称

        Returns:
            策略统计信息
        """
        return self.backtest.get_strategy_stats(strategy_name)

    def get_best_strategies(
        self,
        metric: str = 'sharpe_ratio',
        limit: int = 10
    ) -> List[Dict]:
        """获取表现最好的策略

        Args:
            metric: 排序指标
            limit: 返回数量

        Returns:
            策略列表
        """
        backtests = self.backtest.get_best_backtests(metric=metric, limit=limit)
        return [bt.to_dict() for bt in backtests]

    # ==================== 模拟交易相关 ====================

    def get_simulation_account_status(
        self,
        account_name: str = 'default'
    ) -> Dict:
        """获取模拟账户状态

        Args:
            account_name: 账户名称

        Returns:
            账户状态信息
        """
        account = self.simulation.get_account(account_name)
        if not account:
            return {}

        positions = self.simulation.get_all_positions(account_name)
        recent_trades = self.simulation.get_trades(account_name, limit=10)

        return {
            'account': account.to_dict(),
            'positions': [p.to_dict() for p in positions],
            'recent_trades': [t.to_dict() for t in recent_trades],
            'position_summary': self.simulation.get_position_summary(account_name),
            'trade_stats': self.simulation.get_trade_stats(account_name)
        }

    # ==================== 因子相关 ====================

    def get_factor_distribution(
        self,
        factor_name: str,
        factor_date: str
    ) -> Dict:
        """获取因子分布统计

        Args:
            factor_name: 因子名称
            factor_date: 因子日期

        Returns:
            因子分布统计
        """
        return self.factor.get_factor_stats(factor_name, factor_date)

    def get_stock_factors_history(
        self,
        symbol: str,
        factor_name: str,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """获取股票因子历史

        Args:
            symbol: 股票代码
            factor_name: 因子名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            因子历史列表
        """
        factors = self.factor.get_factor_time_series(
            symbol=symbol,
            factor_name=factor_name,
            start_date=start_date,
            end_date=end_date
        )
        return [f.to_dict() for f in factors]


# 向后兼容的别名
DataService = DataServiceORM
