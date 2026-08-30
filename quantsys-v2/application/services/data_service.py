"""
统一数据访问服务 (DataService) - 完全ORM版本

聚合所有ORM Repository，提供跨表高级查询和工作流方法

迁移状态：✅ 已完全迁移到ORM
"""
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
    IBacktestRepository,
    IRiskRepository,
    IStrategyRepository,
    ISignalExecutionRepository,
)

from infrastructure.persistence.orm import close_session
from application.services.financial_data_service_adapter import FinancialDataServiceAdapter as FinancialDataService
from domain.exceptions import DatabaseError, ExternalServiceError

logger = structlog.get_logger(__name__)


class DataService:
    """统一数据访问服务（完全ORM版本）

    使用SQLAlchemy ORM，自动Session管理

    P2-1: 支持依赖注入，但保持向后兼容
    - 如果传入 Repository 参数则使用（推荐）
    - 如果不传则自动实例化（向后兼容）
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
        strategy_repo: Optional[IStrategyRepository] = None,
        execution_repo: Optional[ISignalExecutionRepository] = None,
        financial_service: Optional[FinancialDataService] = None,
    ):
        """初始化DataService

        Args:
            cache_manager: 缓存管理器（可选）
            *_repo: Repository 实例（可选，用于依赖注入）
            financial_service: 财务数据服务（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例而非直接构造
        P2-3: 不再自动实例化接口，必须通过依赖注入提供 Repository
        """
        # P2-3: 不再尝试实例化接口，Repository 必须通过依赖注入提供
        self.stock = stock_repo
        self.kline = kline_repo
        self.signal = signal_repo
        self.simulation = simulation_repo
        self.portfolio = portfolio_repo
        self.factor = factor_repo
        self.backtest = backtest_repo
        self.risk = risk_repo
        self.strategy = strategy_repo
        self.execution = execution_repo

        self._cache = cache_manager
        self.financial_service = financial_service or FinancialDataService()

        logger.info("DataService初始化完成（ORM模式）")

    def cleanup(self):
        """清理Session（请求/Job结束时调用）"""
        close_session()

    # ==================== 原有方法保持不变 ====================
    # 所有方法现在使用ORM Repository
    
    def get_stock_full_data(self, symbol: str, start_date: str, end_date: str) -> Dict:
        """获取股票完整数据"""
        try:
            stock_obj = self.stock.get_by_symbol(symbol)
            stock_info = stock_obj.to_dict() if stock_obj else None

            klines_df = self.kline.get_daily_klines(symbol, start_date, end_date)
            klines = klines_df.to_dicts() if isinstance(klines_df, pl.DataFrame) and not klines_df.is_empty() else []

            latest_factors_objs = self.factor.get_latest_factors(symbol)
            latest_factors = [f.to_dict() for f in latest_factors_objs]

            signals_objs = self.signal.get_signals_by_symbol(symbol, start_date, end_date)
            signals = [s.to_dict() for s in signals_objs]

            return {
                'symbol': symbol,
                'stock_info': stock_info,
                'klines': klines,
                'latest_factors': latest_factors,
                'signals': signals,
            }
        except DatabaseError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting stock full data for {symbol}: {e}")
            raise DatabaseError(f"Failed to get stock full data for {symbol}") from e

    def get_backtest_workflow_data(self, symbol: str, start_date: str, end_date: str, period: Optional[str] = None) -> Dict:
        """获取回测工作流数据（K线 + 股票信息）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期（daily/5min等，默认daily）

        Returns:
            包含klines、stock_info等的字典
        """
        try:
            stock_obj = self.stock.get_by_symbol(symbol)
            stock_info = stock_obj.to_dict() if stock_obj else None

            # 获取K线数据
            klines_df = self.kline.get_daily_klines(symbol, start_date, end_date)
            klines = klines_df.to_dicts() if isinstance(klines_df, pl.DataFrame) and not klines_df.is_empty() else []

            # 获取财务数据（用于PE/PB回测）
            # 注意：financial_service.get_financial_data 抛的是普通 provider 异常，
            # 这里必须保持宽捕获做降级容忍（财务数据缺失不应拖垮整个回测工作流）
            financials = []
            try:
                financials_data = self.financial_service.get_financial_data(symbol, start_date, end_date)
                if financials_data and 'data' in financials_data:
                    financials = financials_data['data']
            except Exception as e:
                logger.warning(f"Failed to get financial data for {symbol}, degrade to empty: {e}")

            return {
                'symbol': symbol,
                'stock_info': stock_info,
                'klines': klines,
                'financials': financials,
                'period': period or 'daily',
            }
        except DatabaseError:
            raise
        except ExternalServiceError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting backtest workflow data for {symbol}: {e}")
            raise DatabaseError(f"Failed to get backtest workflow data for {symbol}") from e

    def check_data_integrity(self, symbol: Optional[str] = None, check_type: str = 'all') -> Dict:
        """检查数据完整性

        Args:
            symbol: 可选的股票代码，不提供则检查全局
            check_type: 检查类型 (all/kline/stock/signal/factor)

        Returns:
            检查结果字典
        """
        try:
            result = {
                'status': 'ok',
                'checked_at': datetime.now().isoformat(),
                'issues': [],
                'summary': {}
            }

            # 检查K线数据
            if check_type in ['all', 'kline']:
                if symbol:
                    kline_count = self.kline.count_klines(symbol)
                    result['summary']['kline_count'] = kline_count
                    if kline_count == 0:
                        result['issues'].append(f"No kline data for {symbol}")
                        result['status'] = 'warning'
                else:
                    # 检查所有股票的K线数据
                    stocks = self.stock.get_all_stocks(limit=10)
                    for stock_obj in stocks:
                        count = self.kline.count_klines(stock_obj.symbol)
                        if count == 0:
                            result['issues'].append(f"No kline data for {stock_obj.symbol}")

                    if result['issues']:
                        result['status'] = 'warning'

            # 检查股票基础数据
            if check_type in ['all', 'stock']:
                if symbol:
                    stock_obj = self.stock.get_by_symbol(symbol)
                    result['summary']['stock_exists'] = stock_obj is not None
                    if not stock_obj:
                        result['issues'].append(f"Stock {symbol} not found in database")
                        result['status'] = 'error'
                else:
                    stock_count = self.stock.count_stocks()
                    result['summary']['total_stocks'] = stock_count
                    if stock_count == 0:
                        result['issues'].append("No stocks in database")
                        result['status'] = 'error'

            # 检查信号数据
            if check_type in ['all', 'signal']:
                if symbol:
                    today = datetime.now().strftime('%Y-%m-%d')
                    signals = self.signal.get_signals_by_symbol(symbol, today, today)
                    result['summary']['signal_count'] = len(signals)

            # 检查因子数据
            if check_type in ['all', 'factor']:
                if symbol:
                    factors = self.factor.get_latest_factors(symbol)
                    result['summary']['factor_count'] = len(factors)
                    if len(factors) == 0:
                        result['issues'].append(f"No factor data for {symbol}")

            return result

        except DatabaseError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error checking data integrity: {e}")
            raise DatabaseError(f"Failed to check data integrity") from e

    def get_financial_statements(self, symbol: str, statement_type: str = 'all', periods: int = 4) -> Dict:
        """获取财务报表数据

        Args:
            symbol: 股票代码
            statement_type: 报表类型 ('income'|'balance'|'cash_flow'|'all')
            periods: 期数（默认4期）

        Returns:
            包含财务报表数据的字典
        """
        try:
            # 调用 FinancialDataService 获取数据
            financial_data = self.financial_service.get_financial_data(
                symbol=symbol,
                statement_type=statement_type,
                periods=periods
            )

            # 获取股票基本信息
            stock_obj = self.stock.get_by_symbol(symbol)
            stock_name = stock_obj.name if stock_obj else symbol

            # 转换为API响应格式
            result = {
                'symbol': symbol,
                'name': stock_name,
                'statement_type': statement_type,
                'periods': periods,
            }

            # 添加各类报表数据
            if financial_data:
                if hasattr(financial_data, 'income_statement') and financial_data.income_statement:
                    result['income_statement'] = financial_data.income_statement
                if hasattr(financial_data, 'balance_sheet') and financial_data.balance_sheet:
                    result['balance_sheet'] = financial_data.balance_sheet
                if hasattr(financial_data, 'cash_flow') and financial_data.cash_flow:
                    result['cash_flow'] = financial_data.cash_flow

            return result

        except ExternalServiceError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting financial statements for {symbol}: {e}")
            raise ExternalServiceError(f"Failed to get financial statements for {symbol}") from e


# 向后兼容
__all__ = ['DataService']
