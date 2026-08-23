"""
市场冲击模型 - Team C
Almgren-Chriss市场冲击成本模型
"""
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class AlmgrenChrissModel:
    """
    Almgren-Chriss市场冲击模型

    论文: Optimal execution of portfolio transactions (2001)

    模型:
    - 永久冲击: γ * σ * sqrt(Q / ADV)
    - 临时冲击: η * σ * (Q / (ADV * T))
    """

    def __init__(self,
                 permanent_impact_coef: float = 0.1,
                 temporary_impact_coef: float = 0.01,
                 volatility: float = 0.02):
        """
        Args:
            permanent_impact_coef: 永久冲击系数 (γ)
            temporary_impact_coef: 临时冲击系数 (η)
            volatility: 价格波动率 (σ)
        """
        self.gamma = permanent_impact_coef
        self.eta = temporary_impact_coef
        self.sigma = volatility

        logger.info(f"AlmgrenChrissModel initialized: γ={self.gamma}, η={self.eta}, σ={self.sigma}")

    def calculate_impact(self,
                        order_size: float,
                        adv: float,
                        price: float,
                        execution_time: float = 1.0) -> Dict[str, float]:
        """
        计算市场冲击成本

        Args:
            order_size: 订单大小（股数）
            adv: 日均成交量 (Average Daily Volume)
            price: 当前价格
            execution_time: 执行时间（天）

        Returns:
            {
                'permanent_impact': 永久冲击成本,
                'temporary_impact': 临时冲击成本,
                'total_impact': 总冲击成本,
                'impact_bps': 冲击成本（基点）,
                'participation_rate': 参与率
            }
        """
        # 参与率 (participation rate)
        participation_rate = order_size / (adv * execution_time)

        # 永久冲击: γ * σ * sqrt(Q / ADV)
        permanent_impact = (
            self.gamma * self.sigma * price *
            np.sqrt(order_size / adv)
        )

        # 临时冲击: η * σ * (Q / (ADV * T))
        temporary_impact = (
            self.eta * self.sigma * price *
            (order_size / (adv * execution_time))
        )

        total_impact = permanent_impact + temporary_impact

        # 转换为基点 (bps)
        impact_bps = (total_impact / price) * 10000

        result = {
            'permanent_impact': float(permanent_impact),
            'temporary_impact': float(temporary_impact),
            'total_impact': float(total_impact),
            'impact_bps': float(impact_bps),
            'participation_rate': float(participation_rate)
        }

        logger.debug(
            f"Market impact: {impact_bps:.2f} bps "
            f"(permanent={permanent_impact:.2f}, temporary={temporary_impact:.2f})"
        )

        return result

    def optimal_execution_schedule(self,
                                   total_shares: int,
                                   total_time: float,
                                   risk_aversion: float = 1e-6) -> np.ndarray:
        """
        计算最优执行策略

        Args:
            total_shares: 总股数
            total_time: 总时间（天）
            risk_aversion: 风险厌恶系数 (λ)

        Returns:
            每个时间段的交易量数组
        """
        # 将时间分为多个时间段（每天390分钟）
        n_periods = int(total_time * 390)

        # Almgren-Chriss最优策略参数
        kappa = np.sqrt(risk_aversion * self.sigma**2 / self.eta)
        tau = total_time / n_periods

        # 计算每个时间段的交易量
        schedule = np.zeros(n_periods)
        remaining = total_shares

        for t in range(n_periods):
            time_left = (n_periods - t) * tau

            # 最优交易速率
            trade_rate = (
                remaining *
                np.sinh(kappa * tau) /
                np.sinh(kappa * time_left)
            )

            schedule[t] = trade_rate
            remaining -= trade_rate

        logger.info(
            f"Optimal execution schedule: {n_periods} periods, "
            f"total={total_shares}, avg_per_period={schedule.mean():.2f}"
        )

        return schedule

    def estimate_total_cost(self,
                           order_size: float,
                           adv: float,
                           price: float,
                           execution_time: float = 1.0) -> Dict[str, float]:
        """
        估算总交易成本

        Returns:
            {
                'market_impact': 市场冲击成本,
                'commission': 佣金（假设0.03%）,
                'slippage': 滑点（假设0.1%）,
                'total_cost': 总成本,
                'total_cost_bps': 总成本（基点）
            }
        """
        # 市场冲击
        impact = self.calculate_impact(order_size, adv, price, execution_time)
        market_impact = impact['total_impact']

        # 佣金（假设0.03%）
        commission = order_size * price * 0.0003

        # 滑点（假设0.1%）
        slippage = order_size * price * 0.001

        total_cost = market_impact + commission + slippage
        total_cost_bps = (total_cost / (order_size * price)) * 10000

        return {
            'market_impact': float(market_impact),
            'commission': float(commission),
            'slippage': float(slippage),
            'total_cost': float(total_cost),
            'total_cost_bps': float(total_cost_bps)
        }
