"""
期货定价模型 - Team C
期货理论价格、基差、持有成本计算
"""
import sys
import os

import numpy as np
from typing import Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FuturesPricing:
    """
    期货定价模型

    基于持有成本理论:
    F = S * e^((r-q)*T)

    其中:
    F = 期货价格
    S = 现货价格
    r = 无风险利率
    q = 股息率
    T = 到期时间
    """

    def __init__(self, risk_free_rate: float = 0.03):
        """
        Args:
            risk_free_rate: 无风险利率（年化）
        """
        self.risk_free_rate = risk_free_rate
        logger.info(f"FuturesPricing initialized: r={risk_free_rate}")

    def fair_value(self,
                   spot_price: float,
                   dividend_yield: float,
                   time_to_maturity: float) -> float:
        """
        计算期货理论价格

        Args:
            spot_price: 现货价格
            dividend_yield: 股息率（年化）
            time_to_maturity: 到期时间（年）

        Returns:
            期货理论价格
        """
        fair_price = spot_price * np.exp(
            (self.risk_free_rate - dividend_yield) * time_to_maturity
        )

        logger.debug(
            f"Fair value: spot={spot_price}, T={time_to_maturity}, "
            f"fair={fair_price:.2f}"
        )

        return float(fair_price)

    def basis(self, futures_price: float, spot_price: float) -> float:
        """
        计算基差

        基差 = 期货价格 - 现货价格

        Args:
            futures_price: 期货价格
            spot_price: 现货价格

        Returns:
            基差
        """
        return float(futures_price - spot_price)

    def basis_percentage(self, futures_price: float, spot_price: float) -> float:
        """
        计算基差率

        基差率 = (期货价格 - 现货价格) / 现货价格

        Returns:
            基差率（百分比）
        """
        return float((futures_price - spot_price) / spot_price)

    def cost_of_carry(self,
                     futures_price: float,
                     spot_price: float,
                     time_to_maturity: float) -> float:
        """
        计算持有成本

        持有成本 = (F/S - 1) / T

        Args:
            futures_price: 期货价格
            spot_price: 现货价格
            time_to_maturity: 到期时间（年）

        Returns:
            持有成本（年化）
        """
        if time_to_maturity == 0:
            return 0.0

        carry_cost = (futures_price / spot_price - 1) / time_to_maturity

        return float(carry_cost)

    def implied_dividend_yield(self,
                               futures_price: float,
                               spot_price: float,
                               time_to_maturity: float) -> float:
        """
        计算隐含股息率

        从期货价格反推股息率:
        q = r - ln(F/S) / T

        Args:
            futures_price: 期货价格
            spot_price: 现货价格
            time_to_maturity: 到期时间（年）

        Returns:
            隐含股息率（年化）
        """
        if time_to_maturity == 0:
            return 0.0

        implied_q = self.risk_free_rate - np.log(futures_price / spot_price) / time_to_maturity

        return float(implied_q)

    def arbitrage_opportunity(self,
                             futures_price: float,
                             spot_price: float,
                             dividend_yield: float,
                             time_to_maturity: float,
                             transaction_cost: float = 0.001) -> Dict:
        """
        检测套利机会

        Args:
            futures_price: 实际期货价格
            spot_price: 现货价格
            dividend_yield: 股息率
            time_to_maturity: 到期时间
            transaction_cost: 交易成本（双边）

        Returns:
            {
                'has_arbitrage': bool,
                'type': str,  # 'cash_and_carry' or 'reverse_cash_and_carry'
                'profit': float,
                'profit_pct': float
            }
        """
        # 计算理论价格
        fair_price = self.fair_value(spot_price, dividend_yield, time_to_maturity)

        # 考虑交易成本
        upper_bound = fair_price * (1 + transaction_cost)
        lower_bound = fair_price * (1 - transaction_cost)

        has_arbitrage = False
        arb_type = None
        profit = 0.0

        if futures_price > upper_bound:
            # 期货高估：做空期货，买入现货（Cash and Carry）
            has_arbitrage = True
            arb_type = 'cash_and_carry'
            profit = futures_price - spot_price * np.exp(
                (self.risk_free_rate - dividend_yield) * time_to_maturity
            ) - spot_price * transaction_cost * 2

        elif futures_price < lower_bound:
            # 期货低估：买入期货，卖空现货（Reverse Cash and Carry）
            has_arbitrage = True
            arb_type = 'reverse_cash_and_carry'
            profit = spot_price * np.exp(
                (self.risk_free_rate - dividend_yield) * time_to_maturity
            ) - futures_price - spot_price * transaction_cost * 2

        profit_pct = profit / spot_price if spot_price > 0 else 0

        result = {
            'has_arbitrage': has_arbitrage,
            'type': arb_type,
            'profit': float(profit),
            'profit_pct': float(profit_pct),
            'fair_price': float(fair_price),
            'actual_price': float(futures_price),
            'mispricing': float(futures_price - fair_price)
        }

        if has_arbitrage:
            logger.info(
                f"Arbitrage opportunity: {arb_type}, "
                f"profit={profit:.2f} ({profit_pct:.2%})"
            )

        return result

    def calendar_spread_value(self,
                             near_futures: float,
                             far_futures: float,
                             near_maturity: float,
                             far_maturity: float) -> Dict:
        """
        跨期价差分析

        Args:
            near_futures: 近月合约价格
            far_futures: 远月合约价格
            near_maturity: 近月到期时间
            far_maturity: 远月到期时间

        Returns:
            {
                'spread': float,
                'spread_pct': float,
                'annualized_spread': float,
                'contango': bool  # True=升水, False=贴水
            }
        """
        spread = far_futures - near_futures
        spread_pct = spread / near_futures
        time_diff = far_maturity - near_maturity

        # 年化价差
        annualized_spread = spread_pct / time_diff if time_diff > 0 else 0

        # 升水(Contango)或贴水(Backwardation)
        contango = spread > 0

        return {
            'spread': float(spread),
            'spread_pct': float(spread_pct),
            'annualized_spread': float(annualized_spread),
            'contango': contango,
            'market_structure': 'Contango' if contango else 'Backwardation'
        }
