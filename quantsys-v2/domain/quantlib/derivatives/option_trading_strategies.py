"""
期权策略基类和核心策略

包含：
1. OptionStrategy基类
2. DeltaNeutralStrategy - Delta中性策略
3. VolatilityArbitrageStrategy - 波动率套利策略
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

from domain.quantlib.derivatives.greeks import GreeksCalculator
from domain.quantlib.derivatives.black_scholes import BlackScholesCalculator
from domain.quantlib.derivatives.implied_volatility import ImpliedVolatilityCalculator

logger = logging.getLogger(__name__)


class OptionStrategy:
    """期权策略基类 — 所有期权策略的基础类"""

    def __init__(self, name: str):
        self.name = name
        self.greeks_calculator = GreeksCalculator()
        self.bs_calculator = BlackScholesCalculator()
        self.iv_calculator = ImpliedVolatilityCalculator()
        self.positions = []

    def _calc_price(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
        """Calculate BS option price."""
        result = self.bs_calculator.calculate(S=S, K=K, T=T, r=r, sigma=sigma, option_type=option_type)
        return result['value']

    def _calc_greeks(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict[str, float]:
        """Calculate Greeks and return flat dict with price."""
        result = self.greeks_calculator.calculate(S, K, T, r, sigma, option_type)
        greeks = result['value'].copy()
        greeks['price'] = self._calc_price(S, K, T, r, sigma, option_type)
        return greeks

    def add_position(
        self,
        option_type: str,
        quantity: int,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float
    ):
        """添加期权头寸"""
        greeks = self._calc_greeks(S, K, T, r, sigma, option_type)

        position = {
            'option_type': option_type,
            'quantity': quantity,
            'S': S,
            'K': K,
            'T': T,
            'r': r,
            'sigma': sigma,
            'greeks': greeks
        }

        self.positions.append(position)

    def calculate_portfolio_greeks(self) -> Dict[str, float]:
        """计算组合的总Greeks"""
        total_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'value': 0.0
        }

        for position in self.positions:
            quantity = position['quantity']
            greeks = position['greeks']

            total_greeks['delta'] += quantity * greeks['delta']
            total_greeks['gamma'] += quantity * greeks['gamma']
            total_greeks['theta'] += quantity * greeks['theta']
            total_greeks['vega'] += quantity * greeks['vega']
            total_greeks['rho'] += quantity * greeks['rho']
            total_greeks['value'] += quantity * greeks['price']

        return total_greeks

    def generate_signal(self, market_data: Dict) -> Optional[Dict]:
        """生成交易信号 — 子类需要实现此方法"""
        raise NotImplementedError("Subclass must implement generate_signal()")

    def clear_positions(self):
        """清空所有头寸"""
        self.positions = []


class DeltaNeutralStrategy(OptionStrategy):
    """
    Delta中性策略

    策略逻辑：
    1. 持有期权头寸
    2. 通过持有标的资产对冲Delta
    3. 保持组合Delta接近0
    4. 赚取Gamma和Theta的收益
    """

    def __init__(
        self,
        delta_threshold: float = 0.1,
        rebalance_frequency: int = 1
    ):
        super().__init__("Delta Neutral Strategy")
        self.delta_threshold = delta_threshold
        self.rebalance_frequency = rebalance_frequency
        self.stock_position = 0

    def generate_signal(self, market_data: Dict) -> Optional[Dict]:
        """生成Delta中性信号"""
        S = market_data['S']
        K = market_data['K']
        T = market_data['T']
        r = market_data['r']
        sigma = market_data['sigma']
        option_type = market_data.get('option_type', 'call')

        greeks = self._calc_greeks(S, K, T, r, sigma, option_type)

        option_quantity = 100
        option_delta = greeks['delta'] * option_quantity

        required_stock_position = -option_delta
        current_delta = option_delta + self.stock_position

        if abs(current_delta) > self.delta_threshold:
            stock_adjustment = required_stock_position - self.stock_position

            signal = {
                'strategy': self.name,
                'timestamp': datetime.now(),
                'action': 'rebalance',
                'option_position': {
                    'type': option_type,
                    'quantity': option_quantity,
                    'delta': option_delta
                },
                'stock_adjustment': stock_adjustment,
                'new_stock_position': required_stock_position,
                'portfolio_greeks': {
                    'delta': current_delta,
                    'gamma': greeks['gamma'] * option_quantity,
                    'theta': greeks['theta'] * option_quantity,
                    'vega': greeks['vega'] * option_quantity
                }
            }

            self.stock_position = required_stock_position

            logger.info(
                f"Delta neutral rebalance: adjust stock by {stock_adjustment:.2f}"
            )
            return signal

        return None

    def calculate_pnl(
        self,
        initial_S: float,
        final_S: float,
        initial_greeks: Dict,
        final_greeks: Dict,
        option_quantity: int
    ) -> Dict[str, float]:
        """计算损益"""
        option_pnl = (
            final_greeks['price'] - initial_greeks['price']
        ) * option_quantity

        stock_pnl = (final_S - initial_S) * self.stock_position

        total_pnl = option_pnl + stock_pnl

        return {
            'option_pnl': option_pnl,
            'stock_pnl': stock_pnl,
            'total_pnl': total_pnl,
            'gamma_pnl': 0.5 * initial_greeks['gamma'] * option_quantity * (final_S - initial_S) ** 2,
            'theta_pnl': initial_greeks['theta'] * option_quantity
        }


class VolatilityArbitrageStrategy(OptionStrategy):
    """
    波动率套利策略

    策略逻辑：
    1. 比较隐含波动率(IV)和历史波动率(HV)
    2. IV > HV: 卖出期权（做空波动率）
    3. IV < HV: 买入期权（做多波动率）
    4. 通过Delta对冲保持市场中性
    """

    def __init__(
        self,
        iv_hv_threshold: float = 0.05,
        min_vega: float = 10.0
    ):
        super().__init__("Volatility Arbitrage Strategy")
        self.iv_hv_threshold = iv_hv_threshold
        self.min_vega = min_vega

    def calculate_historical_volatility(
        self,
        prices: np.ndarray,
        window: int = 20
    ) -> float:
        """计算历史波动率"""
        if len(prices) < window + 1:
            return 0.0

        returns = np.log(prices[1:] / prices[:-1])
        std = np.std(returns[-window:])
        annual_vol = std * np.sqrt(252)

        return annual_vol

    def _calc_iv(self, market_price: float, S: float, K: float, T: float, r: float, option_type: str) -> float:
        """Calculate implied volatility."""
        result = self.iv_calculator.calculate(
            option_price=market_price, S=S, K=K, T=T, r=r, option_type=option_type
        )
        return result['value']

    def generate_signal(self, market_data: Dict) -> Optional[Dict]:
        """生成波动率套利信号"""
        S = market_data['S']
        K = market_data['K']
        T = market_data['T']
        r = market_data['r']
        market_price = market_data['market_price']
        option_type = market_data.get('option_type', 'call')
        historical_prices = market_data.get('historical_prices', np.array([]))

        try:
            iv = self._calc_iv(market_price, S, K, T, r, option_type)
        except Exception:
            logger.warning("Failed to calculate implied volatility")
            return None

        hv = self.calculate_historical_volatility(historical_prices)

        if hv == 0:
            logger.warning("Failed to calculate historical volatility")
            return None

        greeks = self._calc_greeks(S, K, T, r, iv, option_type)

        iv_hv_diff = iv - hv
        vega = greeks['vega']

        if abs(iv_hv_diff) < self.iv_hv_threshold:
            return None

        if vega < self.min_vega:
            return None

        if iv_hv_diff > self.iv_hv_threshold:
            action = 'sell'
            quantity = -100
        else:
            action = 'buy'
            quantity = 100

        signal = {
            'strategy': self.name,
            'timestamp': datetime.now(),
            'action': action,
            'option_type': option_type,
            'quantity': quantity,
            'strike': K,
            'expiry': T,
            'implied_volatility': iv,
            'historical_volatility': hv,
            'iv_hv_diff': iv_hv_diff,
            'greeks': greeks,
            'hedge_ratio': -greeks['delta'] * quantity
        }

        logger.info(
            f"Volatility arbitrage signal: {action} {abs(quantity)} {option_type}, "
            f"IV={iv:.2%}, HV={hv:.2%}, diff={iv_hv_diff:.2%}"
        )

        return signal


# 使用示例
def example_usage():
    """使用示例"""
    print("=== Delta Neutral Strategy ===")
    delta_neutral = DeltaNeutralStrategy(delta_threshold=0.1)

    market_data = {
        'S': 100,
        'K': 100,
        'T': 0.25,
        'r': 0.05,
        'sigma': 0.2,
        'option_type': 'call'
    }

    signal = delta_neutral.generate_signal(market_data)
    if signal:
        print(f"Action: {signal['action']}")
        print(f"Stock adjustment: {signal['stock_adjustment']:.2f}")
        print(f"Portfolio Delta: {signal['portfolio_greeks']['delta']:.4f}")

    print("\n=== Volatility Arbitrage Strategy ===")
    vol_arb = VolatilityArbitrageStrategy(iv_hv_threshold=0.05)

    np.random.seed(42)
    historical_prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))

    market_data_vol = {
        'S': 100,
        'K': 100,
        'T': 0.25,
        'r': 0.05,
        'market_price': 6.0,
        'option_type': 'call',
        'historical_prices': historical_prices
    }

    signal_vol = vol_arb.generate_signal(market_data_vol)
    if signal_vol:
        print(f"Action: {signal_vol['action']}")
        print(f"Quantity: {signal_vol['quantity']}")
        print(f"IV: {signal_vol['implied_volatility']:.2%}")
        print(f"HV: {signal_vol['historical_volatility']:.2%}")
        print(f"Hedge ratio: {signal_vol['hedge_ratio']:.2f}")


if __name__ == "__main__":
    example_usage()
