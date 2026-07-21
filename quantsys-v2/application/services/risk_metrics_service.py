"""
风险指标服务 - 基于empyrical-reloaded
提供标准化的风险与收益指标计算
"""
import empyrical as ep
import pandas as pd
import numpy as np
from typing import Dict, Optional, Union
import structlog

logger = structlog.get_logger(__name__)


class RiskMetricsService:
    """
    风险指标计算服务

    基于empyrical-reloaded库，提供业界标准的风险与收益指标计算。
    支持的指标包括：
    - 夏普比率（Sharpe Ratio）
    - 索提诺比率（Sortino Ratio）
    - 卡尔马比率（Calmar Ratio）
    - 最大回撤（Max Drawdown）
    - Alpha/Beta分析
    - VaR/CVaR（尾部风险）
    - 年化收益率/波动率
    """

    def __init__(self, risk_free: float = 0.03):
        """
        初始化风险指标服务

        Args:
            risk_free: 年化无风险利率（默认3%）
        """
        self.risk_free = risk_free

    def calculate_all_metrics(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        benchmark_returns: Optional[Union[pd.Series, np.ndarray, list]] = None,
        risk_free: Optional[float] = None
    ) -> Dict[str, float]:
        """
        一站式计算所有风险指标

        Args:
            returns: 收益率序列（日收益率）
            benchmark_returns: 基准收益率（可选，用于计算Alpha/Beta）
            risk_free: 年化无风险利率（可选，默认使用实例设置）

        Returns:
            包含所有风险指标的字典

        Example:
            >>> service = RiskMetricsService()
            >>> returns = [0.01, -0.02, 0.03, 0.005, -0.01]
            >>> metrics = service.calculate_all_metrics(returns)
            >>> print(metrics['sharpe_ratio'])
            1.52
        """
        # 转换为Series
        returns = self._to_series(returns)

        # 使用传入的risk_free或实例默认值
        rf = risk_free if risk_free is not None else self.risk_free

        # 基础指标
        metrics = {
            'sharpe_ratio': self.calculate_sharpe_ratio(returns, rf),
            'sortino_ratio': self.calculate_sortino_ratio(returns, rf),
            'calmar_ratio': self.calculate_calmar_ratio(returns),
            'max_drawdown': self.calculate_max_drawdown(returns),
            'annual_return': self.calculate_annual_return(returns),
            'annual_volatility': self.calculate_annual_volatility(returns),
            'var_95': self.calculate_var(returns, cutoff=0.05),
            'cvar_95': self.calculate_cvar(returns, cutoff=0.05),
            'cumulative_return': self.calculate_cumulative_return(returns)
        }

        # 如果提供了基准，计算Alpha/Beta
        if benchmark_returns is not None:
            benchmark_returns = self._to_series(benchmark_returns)
            alpha, beta = self.calculate_alpha_beta(returns, benchmark_returns, rf)
            metrics['alpha'] = alpha
            metrics['beta'] = beta
            metrics['information_ratio'] = self.calculate_information_ratio(returns, benchmark_returns)

        return metrics

    def calculate_sharpe_ratio(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        risk_free: Optional[float] = None
    ) -> float:
        """
        计算夏普比率（风险调整后收益）

        夏普比率 = (平均收益 - 无风险利率) / 收益标准差

        Args:
            returns: 收益率序列
            risk_free: 年化无风险利率

        Returns:
            夏普比率
        """
        returns = self._to_series(returns)
        rf = risk_free if risk_free is not None else self.risk_free

        try:
            return float(ep.sharpe_ratio(returns, risk_free=rf))
        except Exception as e:
            logger.warning(f"计算夏普比率失败: {e}")
            return np.nan

    def calculate_sortino_ratio(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        risk_free: Optional[float] = None
    ) -> float:
        """
        计算索提诺比率（下行风险调整收益）

        索提诺比率 = (平均收益 - 无风险利率) / 下行标准差
        比夏普更合理，只惩罚下行波动

        Args:
            returns: 收益率序列
            risk_free: 年化无风险利率

        Returns:
            索提诺比率
        """
        returns = self._to_series(returns)
        rf = risk_free if risk_free is not None else self.risk_free

        try:
            return float(ep.sortino_ratio(returns, required_return=rf))
        except Exception as e:
            logger.warning(f"计算索提诺比率失败: {e}")
            return np.nan

    def calculate_calmar_ratio(
        self,
        returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算卡尔马比率（最大回撤调整收益）

        卡尔马比率 = 年化收益率 / 最大回撤（绝对值）

        Args:
            returns: 收益率序列

        Returns:
            卡尔马比率
        """
        returns = self._to_series(returns)

        try:
            return float(ep.calmar_ratio(returns))
        except Exception as e:
            logger.warning(f"计算卡尔马比率失败: {e}")
            return np.nan

    def calculate_max_drawdown(
        self,
        returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算最大回撤

        最大回撤 = (谷值 - 峰值) / 峰值

        Args:
            returns: 收益率序列

        Returns:
            最大回撤（负数）
        """
        returns = self._to_series(returns)

        try:
            return float(ep.max_drawdown(returns))
        except Exception as e:
            logger.warning(f"计算最大回撤失败: {e}")
            return np.nan

    def calculate_alpha_beta(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        benchmark_returns: Union[pd.Series, np.ndarray, list],
        risk_free: Optional[float] = None
    ) -> tuple[float, float]:
        """
        计算Alpha和Beta

        Alpha: 相对基准的超额收益（年化）
        Beta: 相对基准的系统性风险暴露

        Args:
            returns: 策略收益率序列
            benchmark_returns: 基准收益率序列
            risk_free: 年化无风险利率

        Returns:
            (alpha, beta)元组
        """
        returns = self._to_series(returns)
        benchmark_returns = self._to_series(benchmark_returns)
        rf = risk_free if risk_free is not None else self.risk_free

        try:
            alpha, beta = ep.alpha_beta(returns, benchmark_returns, risk_free=rf)
            return float(alpha), float(beta)
        except Exception as e:
            logger.warning(f"计算Alpha/Beta失败: {e}")
            return np.nan, np.nan

    def calculate_var(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        cutoff: float = 0.05
    ) -> float:
        """
        计算VaR（Value at Risk，在险价值）

        VaR(5%) = 5%分位数的损失

        Args:
            returns: 收益率序列
            cutoff: 置信水平（默认5%）

        Returns:
            VaR（负数）
        """
        returns = self._to_series(returns)

        try:
            return float(ep.value_at_risk(returns, cutoff=cutoff))
        except Exception as e:
            logger.warning(f"计算VaR失败: {e}")
            return np.nan

    def calculate_cvar(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        cutoff: float = 0.05
    ) -> float:
        """
        计算CVaR（Conditional VaR，条件在险价值）

        CVaR = 超过VaR的平均损失
        也叫Expected Shortfall (ES)

        Args:
            returns: 收益率序列
            cutoff: 置信水平（默认5%）

        Returns:
            CVaR（负数）
        """
        returns = self._to_series(returns)

        try:
            return float(ep.conditional_value_at_risk(returns, cutoff=cutoff))
        except Exception as e:
            logger.warning(f"计算CVaR失败: {e}")
            return np.nan

    def calculate_annual_return(
        self,
        returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算年化收益率

        Args:
            returns: 收益率序列

        Returns:
            年化收益率
        """
        returns = self._to_series(returns)

        try:
            return float(ep.annual_return(returns))
        except Exception as e:
            logger.warning(f"计算年化收益率失败: {e}")
            return np.nan

    def calculate_annual_volatility(
        self,
        returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算年化波动率

        Args:
            returns: 收益率序列

        Returns:
            年化波动率
        """
        returns = self._to_series(returns)

        try:
            return float(ep.annual_volatility(returns))
        except Exception as e:
            logger.warning(f"计算年化波动率失败: {e}")
            return np.nan

    def calculate_cumulative_return(
        self,
        returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算累计收益率

        Args:
            returns: 收益率序列

        Returns:
            累计收益率
        """
        returns = self._to_series(returns)

        try:
            return float(ep.cum_returns_final(returns))
        except Exception as e:
            logger.warning(f"计算累计收益率失败: {e}")
            return np.nan

    def calculate_information_ratio(
        self,
        returns: Union[pd.Series, np.ndarray, list],
        benchmark_returns: Union[pd.Series, np.ndarray, list]
    ) -> float:
        """
        计算信息比率（IR）

        IR = (策略收益 - 基准收益) / 跟踪误差

        Args:
            returns: 策略收益率序列
            benchmark_returns: 基准收益率序列

        Returns:
            信息比率
        """
        returns = self._to_series(returns)
        benchmark_returns = self._to_series(benchmark_returns)

        try:
            # 超额收益
            excess_returns = returns - benchmark_returns
            # 跟踪误差（超额收益的标准差）
            tracking_error = excess_returns.std()

            if tracking_error == 0:
                return np.nan

            # 信息比率 = 平均超额收益 / 跟踪误差
            ir = excess_returns.mean() / tracking_error * np.sqrt(252)
            return float(ir)
        except Exception as e:
            logger.warning(f"计算信息比率失败: {e}")
            return np.nan

    def _to_series(self, data: Union[pd.Series, np.ndarray, list]) -> pd.Series:
        """
        统一转换为pandas Series

        Args:
            data: 输入数据

        Returns:
            pandas Series
        """
        if isinstance(data, pd.Series):
            return data
        elif isinstance(data, np.ndarray):
            return pd.Series(data)
        elif isinstance(data, list):
            return pd.Series(data)
        else:
            raise TypeError(f"不支持的数据类型: {type(data)}")
