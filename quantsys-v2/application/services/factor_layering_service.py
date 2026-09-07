"""
因子分层回测服务
==================

提供因子分层回测的统一服务接口，封装 FactorLayeringBacktest 和 ICAnalyzer。
"""

from domain.ports import IKlineRepository, IStockRepository
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import structlog
from datetime import datetime, timedelta

from domain.factors.analysis.layering_backtest import FactorLayeringBacktest
from domain.factors.analysis.ic_analyzer import ICAnalyzer
from domain.backtest.stages.factor_stage import FactorStage
from application.services.stock_pool_service import StockPoolService

logger = structlog.get_logger(__name__)


class FactorLayeringService:
    """因子分层回测服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        kline_repo: Optional[IKlineRepository] = None,
        stock_repo: Optional[IStockRepository] = None,
        stock_pool_service: Optional[StockPoolService] = None,
    ):
        """初始化服务

        Args:
            kline_repo: K线仓库（可选）
            stock_repo: 股票仓库（可选）
            stock_pool_service: 股票池服务（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.stock_pool_service = stock_pool_service or StockPoolService(stock_repo=self.stock_repo)

    def run_layering_backtest(
        self,
        factor_name: str,
        symbols: Optional[List[str]] = None,
        start_date: str = None,
        end_date: str = None,
        n_quantiles: int = 10,
        holding_period: int = 20
    ) -> Dict[str, Any]:
        """
        执行单因子分层回测

        Args:
            factor_name: 因子名称（如 reversal_1d, momentum_6m）
            symbols: 股票列表（可选，默认使用热门股票池）
            start_date: 回测起始日期（YYYY-MM-DD）
            end_date: 回测结束日期（YYYY-MM-DD）
            n_quantiles: 分层数量（默认10层）
            holding_period: 持有期天数（默认20天）

        Returns:
            {
                'factor_name': str,
                'n_quantiles': int,
                'start_date': str,
                'end_date': str,
                'layer_stats': dict,
                'long_short_return': float,
                'monotonicity_score': float,
                'ic_stats': dict,
                'effectiveness_score': float,
                'chart_data': dict
            }
        """
        logger.info(
            f"Starting layering backtest for factor={factor_name}, "
            f"n_quantiles={n_quantiles}, holding_period={holding_period}"
        )

        # 使用默认股票池（如果未指定）
        if symbols is None or len(symbols) == 0:
            symbols = self.stock_pool_service.get_hot_stocks()
            logger.info(f"Using default stock pool: {len(symbols)} stocks")

        # 准备数据
        factor_data = self._prepare_factor_data(factor_name, symbols, start_date, end_date)
        return_data = self._prepare_return_data(symbols, start_date, end_date)

        # 验证数据
        if factor_data.empty:
            raise ValueError(f"No factor data available for {factor_name}")
        if return_data.empty:
            raise ValueError("No return data available")

        logger.info(f"Factor data shape: {factor_data.shape}, Return data shape: {return_data.shape}")

        # 执行分层回测
        backtest_engine = FactorLayeringBacktest(n_quantiles=n_quantiles)
        layer_returns = backtest_engine.backtest(
            factor_data=factor_data,
            return_data=return_data,
            holding_period=holding_period
        )

        if layer_returns is None or layer_returns.empty:
            raise ValueError("Backtest produced no layer returns")

        logger.info(f"Layer returns shape: {layer_returns.shape}")

        # 计算分层统计
        layer_stats = backtest_engine.calculate_layer_statistics(layer_returns)

        if layer_stats is None or layer_stats.empty:
            raise ValueError("Failed to calculate layer statistics")

        # 计算多空收益
        long_short_returns = backtest_engine.calculate_long_short_returns(layer_returns)
        long_short_return = long_short_returns.mean()

        # 检查单调性
        monotonicity_result = backtest_engine.check_monotonicity(layer_stats)
        monotonicity_score = monotonicity_result['monotonicity_score']

        # 计算因子有效性评分
        effectiveness_result = backtest_engine.get_factor_effectiveness_score(layer_stats)
        effectiveness_score = effectiveness_result['total_score']

        # 计算 IC 统计
        ic_analyzer = ICAnalyzer()
        ic_series = ic_analyzer.calculate_ic_series(
            factor_data=factor_data,
            return_data=return_data,
            periods=[holding_period]
        )
        ic_stats_df = ic_analyzer.calculate_ic_statistics(ic_series)
        # Convert DataFrame to dict for JSON serialization
        ic_stats_result = ic_stats_df.to_dict(orient='index') if isinstance(ic_stats_df, pd.DataFrame) else ic_stats_df

        # 准备图表数据
        chart_data = self._prepare_chart_data(
            layer_returns=layer_returns,
            long_short_returns=long_short_returns,
            ic_series=ic_series
        )

        result = {
            'factor_name': factor_name,
            'n_quantiles': n_quantiles,
            'start_date': start_date or factor_data.index[0].strftime('%Y-%m-%d'),
            'end_date': end_date or factor_data.index[-1].strftime('%Y-%m-%d'),
            'symbols_count': len(symbols),
            'layer_stats': layer_stats.to_dict(orient='index'),
            'long_short_return': float(long_short_return),
            'monotonicity_score': float(monotonicity_score),
            'monotonicity_details': monotonicity_result,
            'ic_stats': ic_stats_result,
            'effectiveness_score': float(effectiveness_score),
            'effectiveness_details': effectiveness_result,
            'chart_data': chart_data
        }

        logger.info(
            f"Backtest completed: effectiveness_score={effectiveness_score:.2f}, "
            f"IC_mean={list(ic_stats_result.values())[0].get('IC_mean', 0) if ic_stats_result else 0:.4f}"
        )

        return result

    def run_batch_layering_backtest(
        self,
        factor_names: List[str],
        symbols: Optional[List[str]] = None,
        start_date: str = None,
        end_date: str = None,
        n_quantiles: int = 10
    ) -> Dict[str, Any]:
        """
        批量因子分层回测

        Args:
            factor_names: 因子名称列表
            symbols: 股票列表（可选）
            start_date: 回测起始日期
            end_date: 回测结束日期
            n_quantiles: 分层数量

        Returns:
            {
                'success': bool,
                'results': list of dict,
                'ranking': list of dict (sorted by effectiveness_score)
            }
        """
        logger.info(f"Starting batch layering backtest for {len(factor_names)} factors")

        results = []
        for factor_name in factor_names:
            try:
                result = self.run_layering_backtest(
                    factor_name=factor_name,
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    n_quantiles=n_quantiles
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to backtest factor {factor_name}: {e}")
                results.append({
                    'factor_name': factor_name,
                    'error': str(e),
                    'effectiveness_score': 0
                })

        # 按有效性评分排序
        ranking = sorted(
            [
                {
                    'factor_name': r['factor_name'],
                    'effectiveness_score': r.get('effectiveness_score', 0),
                    'ic_mean': list(r.get('ic_stats', {}).values())[0].get('IC_mean', 0) if r.get('ic_stats') else 0,
                    'long_short_return': r.get('long_short_return', 0)
                }
                for r in results
            ],
            key=lambda x: x['effectiveness_score'],
            reverse=True
        )

        return {
            'success': True,
            'count': len(results),
            'results': results,
            'ranking': ranking
        }

    def _prepare_factor_data(
        self,
        factor_name: str,
        symbols: List[str],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> pd.DataFrame:
        """
        准备因子数据矩阵（dates × stocks）

        Args:
            factor_name: 因子名称
            symbols: 股票列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            DataFrame (dates × stocks)
        """
        logger.info(f"Preparing factor data for {factor_name}")

        # 使用默认日期范围（如果未指定）
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # 获取因子适配器
        from infrastructure.quantlib.adapters import get_factor_adapter
        adapter = get_factor_adapter()

        factor_values = {}

        for symbol in symbols:
            try:
                # 获取 K 线数据（需要额外的历史数据用于因子计算）
                extended_start = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=250)).strftime('%Y-%m-%d')
                klines = self.kline_repo.get_daily_klines(
                    symbol=symbol,
                    start_date=extended_start,
                    end_date=end_date
                )

                if not klines or len(klines) < 60:
                    logger.warning(f"Insufficient klines for {symbol}")
                    continue

                # 逐日滑动窗口计算因子值
                for i in range(60, len(klines)):  # 需要至少60天历史数据
                    window_klines = klines[:i+1]

                    try:
                        factor_value = adapter.calculate(factor_name, window_klines)

                        if factor_value is not None:
                            date = klines[i].get('trade_date') or klines[i].get('date')
                            date_str = str(date)  # Convert date to string for comparison

                            # 只保留目标日期范围内的数据
                            if start_date <= date_str <= end_date:
                                if date_str not in factor_values:
                                    factor_values[date_str] = {}
                                factor_values[date_str][symbol] = factor_value
                    except Exception as e:
                        continue

            except Exception as e:
                logger.warning(f"Failed to calculate factor for {symbol}: {e}")
                continue

        # 转换为 DataFrame
        factor_df = pd.DataFrame(factor_values).T
        factor_df.index = pd.to_datetime(factor_df.index)
        factor_df = factor_df.sort_index()

        logger.info(f"Factor data prepared: {factor_df.shape[0]} dates, {factor_df.shape[1]} stocks")
        return factor_df

    def _prepare_return_data(
        self,
        symbols: List[str],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> pd.DataFrame:
        """
        准备收益率数据矩阵（dates × stocks）

        Args:
            symbols: 股票列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            DataFrame (dates × stocks)
        """
        logger.info("Preparing return data")

        # 使用默认日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        return_values = {}

        for symbol in symbols:
            try:
                klines = self.kline_repo.get_daily_klines(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )

                if not klines:
                    continue

                # 计算收益率
                for i, kline in enumerate(klines):
                    if i == 0:
                        continue

                    date = kline.get('trade_date') or kline.get('date')
                    date_str = str(date)  # Convert date to string for consistency
                    prev_close = float(klines[i-1].get('close', 0))
                    current_close = float(kline.get('close', 0))

                    if prev_close > 0:
                        ret = (current_close - prev_close) / prev_close

                        if date_str not in return_values:
                            return_values[date_str] = {}
                        return_values[date_str][symbol] = ret

            except Exception as e:
                logger.warning(f"Failed to calculate returns for {symbol}: {e}")
                continue

        # 转换为 DataFrame
        return_df = pd.DataFrame(return_values).T
        return_df.index = pd.to_datetime(return_df.index)
        return_df = return_df.sort_index()

        logger.info(f"Return data prepared: {return_df.shape[0]} dates, {return_df.shape[1]} stocks")
        return return_df

    def _prepare_chart_data(
        self,
        layer_returns: pd.DataFrame,
        long_short_returns: pd.Series,
        ic_series: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        准备图表数据

        Args:
            layer_returns: 分层收益 DataFrame
            long_short_returns: 多空收益 Series
            ic_series: IC 时间序列 DataFrame

        Returns:
            图表数据字典
        """
        # 累积收益
        cumulative_returns = (1 + layer_returns).cumprod()

        # 多空累积收益
        long_short_cumulative = (1 + long_short_returns).cumprod()

        chart_data = {
            'layer_returns': layer_returns.to_dict(orient='list'),
            'cumulative_returns': cumulative_returns.to_dict(orient='list'),
            'long_short_returns': long_short_returns.tolist(),
            'long_short_cumulative': long_short_cumulative.tolist(),
            'ic_series': ic_series.to_dict(orient='list') if ic_series is not None else {},
            'dates': layer_returns.index.strftime('%Y-%m-%d').tolist()
        }

        return chart_data
