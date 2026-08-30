"""
股指期货对冲策略

使用股指期货对冲股票组合的系统性风险
保留Alpha收益，消除Beta风险

策略类型：
1. 静态对冲 - 固定对冲比率
2. 动态对冲 - 根据Beta动态调整
3. 最小方差对冲 - 最小化组合波动率
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BetaCalculator:
    """
    Beta计算器

    计算股票组合相对于指数的Beta
    """

    def __init__(self, lookback_period: int = 60):
        """
        Args:
            lookback_period: 回溯期（天）
        """
        self.lookback_period = lookback_period

    def calculate_beta(
        self,
        portfolio_returns: np.ndarray,
        index_returns: np.ndarray
    ) -> float:
        """
        计算Beta

        Beta = Cov(portfolio, index) / Var(index)

        Args:
            portfolio_returns: 组合收益率序列
            index_returns: 指数收益率序列

        Returns:
            Beta值
        """
        if len(portfolio_returns) < 2 or len(index_returns) < 2:
            return 1.0

        # 确保长度一致
        min_len = min(len(portfolio_returns), len(index_returns))
        portfolio_returns = portfolio_returns[-min_len:]
        index_returns = index_returns[-min_len:]

        # 计算协方差和方差
        covariance = np.cov(portfolio_returns, index_returns)[0, 1]
        variance = np.var(index_returns)

        if variance == 0:
            return 1.0

        beta = covariance / variance

        return beta

    def calculate_rolling_beta(
        self,
        portfolio_returns: pd.Series,
        index_returns: pd.Series,
        window: int = 60
    ) -> pd.Series:
        """
        计算滚动Beta

        Args:
            portfolio_returns: 组合收益率
            index_returns: 指数收益率
            window: 窗口期

        Returns:
            滚动Beta序列
        """
        def calc_beta(port_ret, idx_ret):
            if len(port_ret) < 2:
                return 1.0
            cov = np.cov(port_ret, idx_ret)[0, 1]
            var = np.var(idx_ret)
            return cov / var if var != 0 else 1.0

        rolling_beta = pd.Series(index=portfolio_returns.index, dtype=float)

        for i in range(window, len(portfolio_returns)):
            port_window = portfolio_returns.iloc[i-window:i].values
            idx_window = index_returns.iloc[i-window:i].values
            rolling_beta.iloc[i] = calc_beta(port_window, idx_window)

        return rolling_beta


class IndexFuturesHedgeStrategy:
    """
    股指期货对冲策略

    策略逻辑：
    1. 持有股票组合（Alpha策略）
    2. 计算组合Beta
    3. 使用股指期货对冲Beta风险
    4. 保留Alpha收益
    """

    def __init__(
        self,
        portfolio_value: float,
        futures_multiplier: float = 300,  # 期货合约乘数
        hedge_ratio: float = 1.0,  # 对冲比率
        rebalance_threshold: float = 0.1,  # 再平衡阈值
        lookback_period: int = 60
    ):
        """
        Args:
            portfolio_value: 组合价值
            futures_multiplier: 期货合约乘数
            hedge_ratio: 对冲比率（1.0=完全对冲）
            rebalance_threshold: 再平衡阈值
            lookback_period: Beta计算回溯期
        """
        self.portfolio_value = portfolio_value
        self.futures_multiplier = futures_multiplier
        self.hedge_ratio = hedge_ratio
        self.rebalance_threshold = rebalance_threshold

        self.beta_calculator = BetaCalculator(lookback_period)

        self.current_beta = 1.0
        self.futures_position = 0  # 期货持仓（手数）
        self.target_futures_position = 0

    def calculate_hedge_position(
        self,
        portfolio_value: float,
        beta: float,
        futures_price: float
    ) -> int:
        """
        计算对冲头寸

        对冲手数 = (组合价值 × Beta × 对冲比率) / (期货价格 × 合约乘数)

        Args:
            portfolio_value: 组合价值
            beta: Beta值
            futures_price: 期货价格

        Returns:
            期货手数（负数表示空头）
        """
        hedge_value = portfolio_value * beta * self.hedge_ratio
        contract_value = futures_price * self.futures_multiplier

        if contract_value == 0:
            return 0

        # 做空期货对冲
        futures_contracts = -int(hedge_value / contract_value)

        return futures_contracts

    def update_beta(
        self,
        portfolio_returns: np.ndarray,
        index_returns: np.ndarray
    ):
        """
        更新Beta

        Args:
            portfolio_returns: 组合收益率
            index_returns: 指数收益率
        """
        self.current_beta = self.beta_calculator.calculate_beta(
            portfolio_returns, index_returns
        )

        logger.info(f"Updated Beta: {self.current_beta:.4f}")

    def generate_rebalance_signal(
        self,
        portfolio_value: float,
        futures_price: float
    ) -> Optional[Dict]:
        """
        生成再平衡信号

        Args:
            portfolio_value: 当前组合价值
            futures_price: 期货价格

        Returns:
            再平衡信号
        """
        # 计算目标持仓
        target_position = self.calculate_hedge_position(
            portfolio_value, self.current_beta, futures_price
        )

        # 计算持仓偏差
        position_diff = target_position - self.futures_position

        # 判断是否需要再平衡
        if abs(position_diff) / max(abs(target_position), 1) > self.rebalance_threshold:
            signal = {
                'action': 'rebalance',
                'current_position': self.futures_position,
                'target_position': target_position,
                'adjustment': position_diff,
                'beta': self.current_beta,
                'portfolio_value': portfolio_value,
                'futures_price': futures_price,
                'timestamp': datetime.now()
            }

            self.target_futures_position = target_position

            logger.info(
                f"Rebalance signal: adjust futures by {position_diff} contracts "
                f"(current={self.futures_position}, target={target_position})"
            )

            return signal

        return None

    def on_rebalance(self, executed_position: int):
        """
        再平衡执行回调

        Args:
            executed_position: 执行后的持仓
        """
        self.futures_position = executed_position
        logger.info(f"Rebalance executed: futures_position={self.futures_position}")

    def calculate_hedge_effectiveness(
        self,
        portfolio_returns: pd.Series,
        index_returns: pd.Series,
        futures_returns: pd.Series
    ) -> Dict[str, float]:
        """
        计算对冲有效性

        Args:
            portfolio_returns: 组合收益率
            index_returns: 指数收益率
            futures_returns: 期货收益率

        Returns:
            对冲效果指标
        """
        # 未对冲组合
        unhedged_returns = portfolio_returns

        # 对冲后组合
        # 假设期货持仓为负（做空）
        hedged_returns = portfolio_returns + futures_returns * abs(self.futures_position) * self.futures_multiplier / self.portfolio_value

        # 计算波动率
        unhedged_vol = unhedged_returns.std() * np.sqrt(252)
        hedged_vol = hedged_returns.std() * np.sqrt(252)

        # 计算Beta
        unhedged_beta = self.beta_calculator.calculate_beta(
            unhedged_returns.values, index_returns.values
        )
        hedged_beta = self.beta_calculator.calculate_beta(
            hedged_returns.values, index_returns.values
        )

        # 对冲效果
        volatility_reduction = (unhedged_vol - hedged_vol) / unhedged_vol
        beta_reduction = (unhedged_beta - hedged_beta) / unhedged_beta

        return {
            'unhedged_volatility': unhedged_vol,
            'hedged_volatility': hedged_vol,
            'volatility_reduction': volatility_reduction,
            'unhedged_beta': unhedged_beta,
            'hedged_beta': hedged_beta,
            'beta_reduction': beta_reduction
        }


class DynamicHedgeStrategy(IndexFuturesHedgeStrategy):
    """
    动态对冲策略

    根据市场状况动态调整对冲比率
    """

    def __init__(
        self,
        portfolio_value: float,
        futures_multiplier: float = 300,
        min_hedge_ratio: float = 0.5,
        max_hedge_ratio: float = 1.0,
        **kwargs
    ):
        """
        Args:
            portfolio_value: 组合价值
            futures_multiplier: 期货合约乘数
            min_hedge_ratio: 最小对冲比率
            max_hedge_ratio: 最大对冲比率
            **kwargs: 其他参数
        """
        super().__init__(portfolio_value, futures_multiplier, **kwargs)
        self.min_hedge_ratio = min_hedge_ratio
        self.max_hedge_ratio = max_hedge_ratio

    def adjust_hedge_ratio(
        self,
        market_volatility: float,
        portfolio_volatility: float,
        correlation: float
    ):
        """
        动态调整对冲比率

        考虑因素：
        1. 市场波动率
        2. 组合波动率
        3. 相关性

        Args:
            market_volatility: 市场波动率
            portfolio_volatility: 组合波动率
            correlation: 相关系数
        """
        # 波动率越高，对冲比率越高
        vol_factor = min(market_volatility / 0.2, 1.0)  # 归一化到[0, 1]

        # 相关性越高，对冲比率越高
        corr_factor = abs(correlation)

        # 综合调整
        adjusted_ratio = (vol_factor + corr_factor) / 2

        # 限制在范围内
        self.hedge_ratio = np.clip(
            adjusted_ratio,
            self.min_hedge_ratio,
            self.max_hedge_ratio
        )

        logger.info(
            f"Adjusted hedge ratio: {self.hedge_ratio:.2f} "
            f"(vol_factor={vol_factor:.2f}, corr_factor={corr_factor:.2f})"
        )


class MinimumVarianceHedgeStrategy(IndexFuturesHedgeStrategy):
    """
    最小方差对冲策略

    通过优化找到最小化组合波动率的对冲比率
    """

    def __init__(self, portfolio_value: float, futures_multiplier: float = 300, **kwargs):
        super().__init__(portfolio_value, futures_multiplier, **kwargs)

    def calculate_optimal_hedge_ratio(
        self,
        portfolio_returns: np.ndarray,
        futures_returns: np.ndarray
    ) -> float:
        """
        计算最优对冲比率

        最小方差对冲比率 = Cov(portfolio, futures) / Var(futures)

        Args:
            portfolio_returns: 组合收益率
            futures_returns: 期货收益率

        Returns:
            最优对冲比率
        """
        if len(portfolio_returns) < 2 or len(futures_returns) < 2:
            return 1.0

        covariance = np.cov(portfolio_returns, futures_returns)[0, 1]
        variance = np.var(futures_returns)

        if variance == 0:
            return 1.0

        optimal_ratio = covariance / variance

        # 限制在合理范围内
        optimal_ratio = np.clip(optimal_ratio, 0.0, 2.0)

        return optimal_ratio

    def update_hedge_ratio(
        self,
        portfolio_returns: np.ndarray,
        futures_returns: np.ndarray
    ):
        """
        更新对冲比率

        Args:
            portfolio_returns: 组合收益率
            futures_returns: 期货收益率
        """
        self.hedge_ratio = self.calculate_optimal_hedge_ratio(
            portfolio_returns, futures_returns
        )

        logger.info(f"Updated optimal hedge ratio: {self.hedge_ratio:.4f}")


# 使用示例
def example_static_hedge():
    """静态对冲示例"""
    print("=== Static Hedge Strategy ===\n")

    strategy = IndexFuturesHedgeStrategy(
        portfolio_value=10_000_000,  # 1000万组合
        futures_multiplier=300,
        hedge_ratio=1.0,
        rebalance_threshold=0.1
    )

    # 模拟数据
    np.random.seed(42)
    n = 100

    portfolio_returns = np.random.randn(n) * 0.015
    index_returns = np.random.randn(n) * 0.012

    # 更新Beta
    strategy.update_beta(portfolio_returns, index_returns)

    # 生成再平衡信号
    signal = strategy.generate_rebalance_signal(
        portfolio_value=10_000_000,
        futures_price=4000
    )

    if signal:
        print("Rebalance Signal:")
        print(f"  Current position: {signal['current_position']} contracts")
        print(f"  Target position: {signal['target_position']} contracts")
        print(f"  Adjustment: {signal['adjustment']} contracts")
        print(f"  Beta: {signal['beta']:.4f}")


def example_dynamic_hedge():
    """动态对冲示例"""
    print("\n=== Dynamic Hedge Strategy ===\n")

    strategy = DynamicHedgeStrategy(
        portfolio_value=10_000_000,
        futures_multiplier=300,
        min_hedge_ratio=0.5,
        max_hedge_ratio=1.0
    )

    # 模拟市场状况
    market_vol = 0.25  # 高波动
    portfolio_vol = 0.20
    correlation = 0.85

    # 调整对冲比率
    strategy.adjust_hedge_ratio(market_vol, portfolio_vol, correlation)

    print(f"Adjusted hedge ratio: {strategy.hedge_ratio:.2f}")


def example_minimum_variance_hedge():
    """最小方差对冲示例"""
    print("\n=== Minimum Variance Hedge Strategy ===\n")

    strategy = MinimumVarianceHedgeStrategy(
        portfolio_value=10_000_000,
        futures_multiplier=300
    )

    # 模拟数据
    np.random.seed(42)
    n = 100

    portfolio_returns = np.random.randn(n) * 0.015
    futures_returns = portfolio_returns * 0.8 + np.random.randn(n) * 0.005

    # 更新对冲比率
    strategy.update_hedge_ratio(portfolio_returns, futures_returns)

    print(f"Optimal hedge ratio: {strategy.hedge_ratio:.4f}")

    # 计算对冲效果
    portfolio_returns_series = pd.Series(portfolio_returns)
    index_returns_series = pd.Series(np.random.randn(n) * 0.012)
    futures_returns_series = pd.Series(futures_returns)

    effectiveness = strategy.calculate_hedge_effectiveness(
        portfolio_returns_series,
        index_returns_series,
        futures_returns_series
    )

    print("\nHedge Effectiveness:")
    for key, value in effectiveness.items():
        print(f"  {key}: {value:.4f}")


if __name__ == "__main__":
    example_static_hedge()
    example_dynamic_hedge()
    example_minimum_variance_hedge()
