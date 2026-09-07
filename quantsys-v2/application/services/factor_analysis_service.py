"""
因子分析服务 - 基于 alphalens-reloaded
提供专业的因子有效性分析
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
import structlog
from io import BytesIO

logger = structlog.get_logger(__name__)

# 尝试导入 alphalens
try:
    import alphalens as al
    ALPHALENS_AVAILABLE = True
    logger.info("alphalens-reloaded is available")
except ImportError:
    ALPHALENS_AVAILABLE = False
    logger.warning("alphalens-reloaded not available, using fallback implementations")


class FactorAnalysisService:
    """
    因子分析服务

    基于 alphalens-reloaded 库，提供业界标准的因子有效性分析。
    支持的分析包括：
    - IC（信息系数）分析
    - 因子分层回测
    - 因子换手率分析
    - 因子相关性矩阵
    - HTML 格式完整报告
    """

    def __init__(self):
        """初始化因子分析服务"""
        if not ALPHALENS_AVAILABLE:
            logger.warning(
                "alphalens not available. Install with: pip install alphalens-reloaded"
            )

    def prepare_factor_data(
        self,
        factor_df: pd.DataFrame,
        prices_df: Optional[pd.DataFrame] = None,
        periods: Tuple[int, ...] = (1, 5, 10),
        quantiles: int = 5,
        max_loss: float = 0.35
    ) -> pd.DataFrame:
        """
        准备 alphalens 所需的数据格式

        Args:
            factor_df: 因子数据 DataFrame
                必需列: ['symbol', 'date', 'factor']
            prices_df: 价格数据 DataFrame (可选)
                必需列: ['symbol', 'date', 'close']
                如果不提供，会尝试从 factor_df 中提取
            periods: 持有期（天），如 (1, 5, 10)
            quantiles: 分位数数量（默认 5）
            max_loss: 最大数据丢失容忍度（默认 0.35 = 35%）

        Returns:
            alphalens 格式的 factor_data DataFrame

        Raises:
            ValueError: 数据格式错误
            ImportError: alphalens 不可用
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        # 验证输入数据
        self._validate_factor_data(factor_df)

        # 如果没有提供价格数据，尝试从 factor_df 中提取
        if prices_df is None:
            if 'close' not in factor_df.columns:
                raise ValueError("factor_df 必须包含 'close' 列，或单独提供 prices_df")
            prices_df = factor_df[['symbol', 'date', 'close']].copy()

        # 转换为 alphalens 格式
        try:
            # 1. 创建因子 Series（MultiIndex: date, asset）
            factor_series = self._create_factor_series(factor_df)

            # 2. 创建价格 DataFrame（index: date, columns: assets）
            prices_pivot = self._create_prices_dataframe(prices_df)

            # 3. 使用 alphalens 处理数据
            factor_data = al.utils.get_clean_factor_and_forward_returns(
                factor=factor_series,
                prices=prices_pivot,
                periods=periods,
                quantiles=quantiles,  # 必需参数
                bins=None,
                max_loss=max_loss  # 数据丢失容忍度
            )

            logger.info(f"Factor data prepared: {len(factor_data)} rows")
            return factor_data

        except Exception as e:
            logger.error(f"Failed to prepare factor data: {e}", exc_info=True)
            raise

    def calculate_ic_analysis(
        self,
        factor_data: pd.DataFrame
    ) -> Dict[str, Union[float, pd.Series, Dict]]:
        """
        计算信息系数（IC）分析

        IC = correlation(factor[t], forward_return[t+n])

        Args:
            factor_data: alphalens 格式的因子数据

        Returns:
            IC 分析结果字典
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        try:
            # 计算 IC 时间序列（返回 DataFrame，每列是一个持有期）
            ic_df = al.performance.factor_information_coefficient(factor_data)

            # 如果有多个周期，取第一个周期的结果作为主要指标
            # 同时保留所有周期的结果
            if isinstance(ic_df, pd.DataFrame):
                # 获取第一个周期的 IC Series
                first_period = ic_df.columns[0]
                ic_series = ic_df[first_period]

                # 基础统计（针对第一个周期）
                ic_mean = float(ic_series.mean())
                ic_std = float(ic_series.std())
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

                # t 统计量
                n = len(ic_series)
                t_stat = ic_mean / (ic_std / np.sqrt(n)) if ic_std > 0 else 0.0

                # p 值（双尾检验）
                from scipy import stats
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))

                # 月度 IC（第一个周期）
                ic_monthly = ic_series.resample('M').mean()

                # 所有周期的IC均值
                ic_by_period = {}
                for period in ic_df.columns:
                    ic_by_period[str(period)] = {
                        'mean': float(ic_df[period].mean()),
                        'std': float(ic_df[period].std())
                    }

                result = {
                    'ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'ic_ir': ic_ir,
                    'ic_series': ic_series.to_dict(),
                    'ic_monthly': ic_monthly.to_dict(),
                    'ic_by_period': ic_by_period,
                    't_stat': float(t_stat),
                    'p_value': float(p_value)
                }
            else:
                # 如果返回的是 Series（向后兼容）
                ic_series = ic_df
                ic_mean = float(ic_series.mean())
                ic_std = float(ic_series.std())
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

                n = len(ic_series)
                t_stat = ic_mean / (ic_std / np.sqrt(n)) if ic_std > 0 else 0.0

                from scipy import stats
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 1))

                ic_monthly = ic_series.resample('M').mean()

                result = {
                    'ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'ic_ir': ic_ir,
                    'ic_series': ic_series.to_dict(),
                    'ic_monthly': ic_monthly.to_dict(),
                    't_stat': float(t_stat),
                    'p_value': float(p_value)
                }

            logger.info(f"IC analysis: mean={result['ic_mean']:.4f}, IR={result['ic_ir']:.4f}")
            return result

        except Exception as e:
            logger.error(f"Failed to calculate IC: {e}", exc_info=True)
            raise

    def calculate_returns_analysis(
        self,
        factor_data: pd.DataFrame,
        quantiles: int = 5,
        periods: Optional[List[int]] = None
    ) -> Dict[str, Union[float, pd.DataFrame, Dict]]:
        """
        因子分层回测分析

        将股票按因子值分为 Q1-Q5 五个分位数，比较收益差异

        Args:
            factor_data: alphalens 格式的因子数据
            quantiles: 分位数数量（默认 5）
            periods: 持有期列表（如果为 None，使用 factor_data 中的所有期）

        Returns:
            分层收益分析结果
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        try:
            # 计算分层收益
            mean_return_by_q, std_err_by_q = al.performance.mean_return_by_quantile(
                factor_data,
                by_date=False,
                by_group=False,
                demeaned=False,
                group_adjust=False
            )

            # 计算价差（Q5 - Q1）
            if periods is None:
                periods = mean_return_by_q.index.get_level_values(0).unique().tolist()

            spread_returns = {}
            for period in periods:
                if period in mean_return_by_q.index:
                    q_returns = mean_return_by_q.loc[period]
                    spread = q_returns.iloc[-1] - q_returns.iloc[0]  # Q5 - Q1
                    spread_returns[f'{period}D'] = float(spread)

            # 转换为字典格式
            quantile_returns = {}
            for period in periods:
                if period in mean_return_by_q.index:
                    q_returns = mean_return_by_q.loc[period]
                    quantile_returns[f'{period}D'] = {
                        f'Q{i+1}': float(q_returns.iloc[i])
                        for i in range(len(q_returns))
                    }

            result = {
                'mean_return_by_quantile': quantile_returns,
                'mean_return_spread': spread_returns,
                'quantiles': quantiles
            }

            logger.info(f"Returns analysis: {quantiles} quantiles, periods={periods}")
            return result

        except Exception as e:
            logger.error(f"Failed to calculate returns: {e}", exc_info=True)
            raise

    def calculate_turnover_analysis(
        self,
        factor_data: pd.DataFrame,
        quantiles: int = 5
    ) -> Dict[str, Union[float, Dict]]:
        """
        因子换手率分析

        换手率 = 因子排名的变化程度
        高换手率 = 不稳定，交易成本高

        Args:
            factor_data: alphalens 格式的因子数据
            quantiles: 分位数数量

        Returns:
            换手率分析结果
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        try:
            # 计算因子自相关性
            autocorr = al.performance.factor_rank_autocorrelation(factor_data)

            # 计算平均换手率（1 - 自相关性）
            # autocorr 可能是 Series 或 DataFrame
            if isinstance(autocorr, pd.DataFrame):
                # 如果是 DataFrame，取所有周期的平均
                mean_turnover = 1.0 - autocorr.mean().mean()

                # 不同 lag 的自相关性
                autocorr_dict = {}
                for period in autocorr.columns:
                    autocorr_dict[f'{period}D'] = float(autocorr[period].mean())
            else:
                # 如果是 Series（单周期）
                mean_turnover = 1.0 - autocorr.mean()
                autocorr_dict = {'1D': float(autocorr.mean())}

            result = {
                'mean_turnover': float(mean_turnover),
                'autocorrelation': autocorr_dict
            }

            logger.info(f"Turnover analysis: mean={result['mean_turnover']:.4f}")
            return result

        except Exception as e:
            logger.error(f"Failed to calculate turnover: {e}", exc_info=True)
            raise

    def calculate_coverage(
        self,
        factor_data: pd.DataFrame
    ) -> Dict[str, Union[float, int, Dict]]:
        """
        计算因子覆盖率

        覆盖率 = 因子值非空的比例
        高覆盖率（> 90%）→ 因子数据完整，样本代表性强
        低覆盖率（< 70%）→ 因子数据缺失严重，存在样本偏差

        Args:
            factor_data: alphalens 格式的因子数据
                包含 'factor' 列或 MultiIndex

        Returns:
            覆盖率分析结果
            {
                'coverage_ratio': 0.95,  # 总体覆盖率
                'total_samples': 10000,  # 总样本数
                'valid_samples': 9500,   # 有效样本数
                'missing_samples': 500,  # 缺失样本数
                'coverage_by_date': {...} # 按日期的覆盖率（可选）
            }
        """
        try:
            # 获取因子值
            if 'factor' in factor_data.columns:
                factor_values = factor_data['factor']
            else:
                # MultiIndex 格式（alphalens 标准格式）
                factor_values = factor_data.index.get_level_values('factor') if 'factor' in factor_data.index.names else factor_data['factor_quantile']

            # 计算总体覆盖率
            total_samples = len(factor_values)
            valid_samples = factor_values.notna().sum() if hasattr(factor_values, 'notna') else total_samples
            missing_samples = total_samples - valid_samples
            coverage_ratio = valid_samples / total_samples if total_samples > 0 else 0.0

            result = {
                'coverage_ratio': float(coverage_ratio),
                'total_samples': int(total_samples),
                'valid_samples': int(valid_samples),
                'missing_samples': int(missing_samples)
            }

            # 计算按日期的覆盖率（如果有日期索引）
            if isinstance(factor_data.index, pd.MultiIndex) and 'date' in factor_data.index.names:
                coverage_by_date = {}
                for date in factor_data.index.get_level_values('date').unique():
                    date_data = factor_data.xs(date, level='date')
                    if 'factor' in date_data.columns:
                        date_factor = date_data['factor']
                    else:
                        date_factor = date_data.index.get_level_values('factor') if 'factor' in date_data.index.names else None

                    if date_factor is not None:
                        date_total = len(date_factor)
                        date_valid = date_factor.notna().sum() if hasattr(date_factor, 'notna') else date_total
                        coverage_by_date[str(date.date())] = float(date_valid / date_total) if date_total > 0 else 0.0

                result['coverage_by_date'] = coverage_by_date

            logger.info(f"Coverage analysis: {coverage_ratio:.2%} ({valid_samples}/{total_samples})")
            return result

        except Exception as e:
            logger.error(f"Failed to calculate coverage: {e}", exc_info=True)
            raise

    def calculate_monotonicity(
        self,
        factor_data: pd.DataFrame,
        quantiles: int = 5
    ) -> Dict[str, Union[float, bool, Dict]]:
        """
        计算因子单调性

        单调性 = 因子分层收益是否单调递增（或递减）
        高单调性（> 80%）→ 因子逻辑清晰，方向性明确，可预测性强
        低单调性（< 50%）→ 因子效果不稳定，存在噪音或非线性关系

        Args:
            factor_data: alphalens 格式的因子数据
            quantiles: 分位数数量（默认 5）

        Returns:
            单调性分析结果
            {
                'monotonicity_ratio': 0.85,  # 单调性比例（0-1）
                'is_monotonic': True,         # 是否单调（> 0.8）
                'direction': 'increasing',    # 方向：increasing/decreasing/mixed
                'monotonic_periods': 17,      # 单调期数
                'total_periods': 20,          # 总期数
                'violations': {...}           # 违反单调性的情况
            }
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        try:
            # 计算分层收益（按日期）
            mean_return_by_q, _ = al.performance.mean_return_by_quantile(
                factor_data,
                by_date=True,  # 按日期计算，用于检查每日单调性
                by_group=False,
                demeaned=False,
                group_adjust=False
            )

            # 统计单调性
            monotonic_increasing = 0
            monotonic_decreasing = 0
            total_periods = 0
            violations = []

            # 遍历每个日期和持有期
            dates = mean_return_by_q.index.get_level_values(0).unique()
            for date in dates:
                try:
                    date_returns = mean_return_by_q.loc[date]

                    # 如果有多个持有期，取第一个
                    if isinstance(date_returns, pd.DataFrame):
                        date_returns = date_returns.iloc[:, 0]

                    returns = date_returns.values

                    # 检查单调递增
                    is_increasing = all(returns[i] <= returns[i+1] for i in range(len(returns)-1))
                    # 检查单调递减
                    is_decreasing = all(returns[i] >= returns[i+1] for i in range(len(returns)-1))

                    if is_increasing:
                        monotonic_increasing += 1
                    elif is_decreasing:
                        monotonic_decreasing += 1
                    else:
                        # 记录违反单调性的情况
                        violations.append({
                            'date': str(date.date()) if hasattr(date, 'date') else str(date),
                            'returns': returns.tolist()
                        })

                    total_periods += 1

                except Exception as e:
                    logger.warning(f"Failed to process date {date}: {e}")
                    continue

            # 计算单调性比例
            monotonic_periods = monotonic_increasing + monotonic_decreasing
            monotonicity_ratio = monotonic_periods / total_periods if total_periods > 0 else 0.0

            # 判断方向
            if monotonic_increasing > monotonic_decreasing * 2:
                direction = 'increasing'
            elif monotonic_decreasing > monotonic_increasing * 2:
                direction = 'decreasing'
            else:
                direction = 'mixed'

            result = {
                'monotonicity_ratio': float(monotonicity_ratio),
                'is_monotonic': monotonicity_ratio > 0.8,
                'direction': direction,
                'monotonic_periods': int(monotonic_periods),
                'total_periods': int(total_periods),
                'increasing_periods': int(monotonic_increasing),
                'decreasing_periods': int(monotonic_decreasing),
                'violations_count': len(violations),
                'violations_sample': violations[:5]  # 只保留前5个违反案例
            }

            logger.info(
                f"Monotonicity analysis: {monotonicity_ratio:.2%} "
                f"({monotonic_periods}/{total_periods}), direction={direction}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to calculate monotonicity: {e}", exc_info=True)
            raise

    def calculate_factor_correlation(
        self,
        factors: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        计算多因子相关性矩阵

        Args:
            factors: 因子字典 {name: factor_data}

        Returns:
            相关性矩阵 DataFrame
        """
        try:
            # 提取每个因子的值
            factor_values = {}
            for name, factor_data in factors.items():
                if 'factor' in factor_data.columns:
                    factor_values[name] = factor_data['factor']
                else:
                    factor_values[name] = factor_data.index.get_level_values('factor')

            # 创建 DataFrame
            df = pd.DataFrame(factor_values)

            # 计算相关性
            corr_matrix = df.corr()

            logger.info(f"Correlation matrix: {len(factors)} factors")
            return corr_matrix

        except Exception as e:
            logger.error(f"Failed to calculate correlation: {e}", exc_info=True)
            raise

    def _validate_factor_data(self, df: pd.DataFrame) -> None:
        """验证因子数据格式"""
        required_cols = ['symbol', 'date', 'factor']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise ValueError(
                f"factor_df 缺少必需列: {missing_cols}. "
                f"当前列: {df.columns.tolist()}"
            )

        if df.empty:
            raise ValueError("factor_df 不能为空")

        if df['factor'].isna().all():
            raise ValueError("因子值全部为 NaN")

    def _create_factor_series(self, factor_df: pd.DataFrame) -> pd.Series:
        """创建 alphalens 格式的因子 Series"""
        # 确保 date 是 datetime 类型
        factor_df = factor_df.copy()
        factor_df['date'] = pd.to_datetime(factor_df['date'])

        # 创建 MultiIndex
        factor_series = factor_df.set_index(['date', 'symbol'])['factor']

        # 排序
        factor_series = factor_series.sort_index()

        return factor_series

    def _create_prices_dataframe(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        """创建 alphalens 格式的价格 DataFrame"""
        # 确保 date 是 datetime 类型
        prices_df = prices_df.copy()
        prices_df['date'] = pd.to_datetime(prices_df['date'])

        # Pivot 转换
        prices_pivot = prices_df.pivot(
            index='date',
            columns='symbol',
            values='close'
        )

        # 排序
        prices_pivot = prices_pivot.sort_index()

        return prices_pivot

    def generate_report_html(
        self,
        factor_data: pd.DataFrame,
        factor_name: str = "Factor",
        output_path: Optional[str] = None
    ) -> str:
        """
        生成完整的 HTML 因子分析报告

        使用 alphalens 的 create_full_tear_sheet() 生成包含以下内容的报告：
        - IC 时间序列图
        - 因子分层收益柱状图
        - 累计收益曲线
        - 换手率分析
        - 事件研究分析

        Args:
            factor_data: alphalens 格式的因子数据
            factor_name: 因子名称（用于报告标题）
            output_path: HTML 文件保存路径（可选）
                如果不提供，将保存到 /tmp/factor_report_{timestamp}.html

        Returns:
            生成的 HTML 文件路径

        Raises:
            ImportError: alphalens 或 matplotlib 不可用
        """
        if not ALPHALENS_AVAILABLE:
            raise ImportError("alphalens not available")

        try:
            import matplotlib
            matplotlib.use('Agg')  # 非交互式后端
            import matplotlib.pyplot as plt
            from io import BytesIO
            import base64
            from datetime import datetime

            logger.info(f"Generating HTML report for factor: {factor_name}")

            # 确定输出路径
            if output_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"/tmp/factor_report_{factor_name}_{timestamp}.html"

            # 创建图表容器
            figures = []

            # 1. IC 时间序列图
            fig_ic = plt.figure(figsize=(14, 6))
            al.plotting.plot_ic_ts(factor_data)
            plt.title(f'{factor_name} - Information Coefficient Time Series')
            figures.append(('IC 时间序列', self._fig_to_base64(fig_ic)))
            plt.close(fig_ic)

            # 2. IC 柱状图（按月度）
            fig_ic_monthly = plt.figure(figsize=(14, 6))
            al.plotting.plot_ic_hist(factor_data)
            plt.title(f'{factor_name} - IC Distribution')
            figures.append(('IC 分布', self._fig_to_base64(fig_ic_monthly)))
            plt.close(fig_ic_monthly)

            # 3. 因子分层收益图
            fig_returns = plt.figure(figsize=(14, 6))
            al.plotting.plot_quantile_returns_bar(factor_data)
            plt.title(f'{factor_name} - Mean Return By Factor Quantile')
            figures.append(('分层收益', self._fig_to_base64(fig_returns)))
            plt.close(fig_returns)

            # 4. 累计收益曲线
            fig_cumulative = plt.figure(figsize=(14, 6))
            al.plotting.plot_cumulative_returns(factor_data, period='1D')
            plt.title(f'{factor_name} - Cumulative Return by Quantile (1D)')
            figures.append(('累计收益', self._fig_to_base64(fig_cumulative)))
            plt.close(fig_cumulative)

            # 5. 换手率分析（如果有多个日期）
            try:
                fig_turnover = plt.figure(figsize=(14, 6))
                al.plotting.plot_turnover_table(factor_data)
                plt.title(f'{factor_name} - Factor Rank Autocorrelation')
                figures.append(('换手率', self._fig_to_base64(fig_turnover)))
                plt.close(fig_turnover)
            except Exception as e:
                logger.warning(f"Turnover plot skipped: {e}")

            # 6. IC 热力图（按月度 × 持有期）
            try:
                fig_ic_heatmap = plt.figure(figsize=(14, 8))
                al.plotting.plot_ic_by_group(factor_data, group='date')
                plt.title(f'{factor_name} - IC Heatmap')
                figures.append(('IC 热力图', self._fig_to_base64(fig_ic_heatmap)))
                plt.close(fig_ic_heatmap)
            except Exception as e:
                logger.warning(f"IC heatmap skipped: {e}")

            # 生成 HTML
            html_content = self._create_html_report(factor_name, figures, factor_data)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"HTML report saved to: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}", exc_info=True)
            raise

    def _fig_to_base64(self, fig) -> str:
        """将 matplotlib 图表转换为 base64 字符串"""
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_str = base64.b64encode(buffer.read()).decode()
        buffer.close()
        return img_str

    def _create_html_report(
        self,
        factor_name: str,
        figures: List[Tuple[str, str]],
        factor_data: pd.DataFrame
    ) -> str:
        """创建 HTML 报告内容"""
        from datetime import datetime

        # 计算摘要统计
        ic_result = self.calculate_ic_analysis(factor_data)
        returns_result = self.calculate_returns_analysis(factor_data)
        turnover_result = self.calculate_turnover_analysis(factor_data)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{factor_name} 因子分析报告</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
        }}
        .summary {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px;
            padding: 15px;
            background-color: white;
            border-left: 4px solid #4CAF50;
            min-width: 200px;
        }}
        .metric-label {{
            font-size: 12px;
            color: #777;
            text-transform: uppercase;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
        }}
        .chart {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #777;
            font-size: 12px;
        }}
        .good {{ color: #4CAF50; }}
        .bad {{ color: #f44336; }}
        .neutral {{ color: #FF9800; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {factor_name} 因子分析报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>数据点数: {len(factor_data):,}</p>

        <h2>📈 核心指标摘要</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-label">平均 IC</div>
                <div class="metric-value {'good' if ic_result['ic_mean'] > 0.03 else 'bad' if ic_result['ic_mean'] < 0 else 'neutral'}">
                    {ic_result['ic_mean']:.4f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">IC IR (信息比率)</div>
                <div class="metric-value {'good' if ic_result['ic_ir'] > 0.5 else 'neutral'}">
                    {ic_result['ic_ir']:.4f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">t 统计量</div>
                <div class="metric-value {'good' if abs(ic_result['t_stat']) > 2 else 'neutral'}">
                    {ic_result['t_stat']:.2f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">p 值</div>
                <div class="metric-value {'good' if ic_result['p_value'] < 0.05 else 'bad'}">
                    {ic_result['p_value']:.4f}
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">平均换手率</div>
                <div class="metric-value {'good' if turnover_result['mean_turnover'] < 0.4 else 'neutral'}">
                    {turnover_result['mean_turnover']:.2%}
                </div>
            </div>
        </div>

        <h2>📊 可视化分析</h2>
"""

        # 添加所有图表
        for title, img_base64 in figures:
            html += f"""
        <div class="chart">
            <h3>{title}</h3>
            <img src="data:image/png;base64,{img_base64}" alt="{title}">
        </div>
"""

        html += """
        <div class="footer">
            <p>本报告由 QuantSys V2 因子分析系统生成</p>
            <p>基于 alphalens-reloaded 专业因子分析库</p>
        </div>
    </div>
</body>
</html>
"""
        return html
